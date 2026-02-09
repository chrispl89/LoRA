"""
LoRA training service (CPU-friendly, minimal DreamBooth-style LoRA fine-tune).

Notes:
- This is a *real* (non-stub) training loop using diffusers.
- It is intentionally minimal (no prior preservation, no fancy schedulers).
- On CPU it will be very slow; keep steps low in train_config_json.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from typing import Callable, Optional

import torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

from diffusers import DDPMScheduler, StableDiffusionPipeline
from peft import LoraConfig, get_peft_model

from app.core.logging import get_logger
from app.services.base_models import apply_runtime_offline_env, ensure_base_model_present

logger = get_logger(__name__)


@dataclass
class TrainConfig:
    base_model_name: str
    trigger_token: str
    instance_prompt: str
    steps: int = 200
    learning_rate: float = 1e-4
    rank: int = 8
    lora_alpha: int = 16
    batch_size: int = 1
    resolution: int = 512
    gradient_accumulation_steps: int = 1
    hf_token: str | None = None


class ImagePromptDataset(Dataset):
    def __init__(self, image_paths: List[Path], prompt: str, resolution: int):
        self.image_paths = image_paths
        self.prompt = prompt
        self.transform = transforms.Compose(
            [
                # Augmentations help when many photos are full-body (face small in frame).
                # RandomResizedCrop occasionally "zooms in" and improves identity learning.
                transforms.RandomResizedCrop(
                    resolution,
                    scale=(0.75, 1.0),
                    ratio=(0.75, 1.333),
                    interpolation=transforms.InterpolationMode.BILINEAR,
                ),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.ToTensor(),
                transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
            ]
        )

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        path = self.image_paths[idx]
        img = Image.open(path).convert("RGB")
        return {"pixel_values": self.transform(img), "prompt": self.prompt}


def run_training(
    config: Dict[str, Any],
    dataset_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
) -> Dict[str, Any]:
    """
    Train LoRA for Stable Diffusion (CPU supported).

    Required keys (provided by worker):
    - base_model_name
    - trigger_token

    Optional keys:
    - steps, learning_rate, rank, batch_size, resolution, gradient_accumulation_steps
    - hf_token / HUGGINGFACE_HUB_TOKEN via env
    """
    base_model = config.get("base_model_name", "sd15")
    trigger_token = config.get("trigger_token", "sks person")
    instance_prompt = config.get("instance_prompt") or f"photo of {trigger_token}"
    rank = int(config.get("rank", 8))
    lora_alpha = int(config.get("lora_alpha", max(rank * 2, 1)))

    tc = TrainConfig(
        base_model_name=base_model,
        trigger_token=trigger_token,
        instance_prompt=instance_prompt,
        steps=int(config.get("steps", 200)),
        learning_rate=float(config.get("learning_rate", 1e-4)),
        rank=rank,
        lora_alpha=lora_alpha,
        batch_size=int(config.get("batch_size", 1)),
        resolution=int(config.get("resolution", 512)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 1)),
        hf_token=(config.get("hf_token") or os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")),
    )

    logger.info(
        "training_started",
        base_model=tc.base_model_name,
        trigger_token=tc.trigger_token,
        instance_prompt=tc.instance_prompt,
        steps=tc.steps,
        lr=tc.learning_rate,
        rank=tc.rank,
        lora_alpha=tc.lora_alpha,
        resolution=tc.resolution,
        dataset_path=dataset_path,
    )

    device = torch.device("cpu")

    apply_runtime_offline_env()
    base_model_dir = ensure_base_model_present(tc.base_model_name)

    # Load pipeline
    pipe = StableDiffusionPipeline.from_pretrained(
        str(base_model_dir),
        safety_checker=None,
        requires_safety_checker=False,
        torch_dtype=torch.float32,
        local_files_only=True,
    )
    pipe.to(device)
    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()

    # Freeze base weights
    pipe.vae.requires_grad_(False)
    pipe.text_encoder.requires_grad_(False)

    # Apply PEFT LoRA to UNet attention projections
    lora_config = LoraConfig(
        r=tc.rank,
        lora_alpha=tc.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
    )
    pipe.unet = get_peft_model(pipe.unet, lora_config)
    pipe.unet.train()

    optimizer = torch.optim.AdamW(pipe.unet.parameters(), lr=tc.learning_rate)
    noise_scheduler = DDPMScheduler.from_config(pipe.scheduler.config)

    # Dataset
    ds_dir = Path(dataset_path)
    image_files = sorted([*ds_dir.glob("*.jpg"), *ds_dir.glob("*.jpeg"), *ds_dir.glob("*.png")])
    if len(image_files) == 0:
        raise RuntimeError("No training images found in dataset_path")

    dataset = ImagePromptDataset(image_files, prompt=tc.instance_prompt, resolution=tc.resolution)
    dataloader = DataLoader(dataset, batch_size=tc.batch_size, shuffle=True, num_workers=0)

    # Train loop (very small, CPU-friendly)
    global_step = 0
    while global_step < tc.steps:
        for batch in dataloader:
            if global_step >= tc.steps:
                break

            pixel_values = batch["pixel_values"].to(device)

            # Encode images to latents
            with torch.no_grad():
                latents = pipe.vae.encode(pixel_values).latent_dist.sample()
                latents = latents * pipe.vae.config.scaling_factor

                # Sample noise + timesteps
                noise = torch.randn_like(latents)
                bsz = latents.shape[0]
                timesteps = torch.randint(0, noise_scheduler.config.num_train_timesteps, (bsz,), device=device).long()
                noisy_latents = noise_scheduler.add_noise(latents, noise, timesteps)

                # Encode prompt
                tokens = pipe.tokenizer(
                    [tc.instance_prompt] * bsz,
                    padding="max_length",
                    truncation=True,
                    max_length=pipe.tokenizer.model_max_length,
                    return_tensors="pt",
                )
                encoder_hidden_states = pipe.text_encoder(tokens.input_ids.to(device))[0]

            # Predict the noise residual
            model_pred = pipe.unet(noisy_latents, timesteps, encoder_hidden_states).sample
            loss = torch.nn.functional.mse_loss(model_pred.float(), noise.float(), reduction="mean")
            loss = loss / tc.gradient_accumulation_steps
            loss.backward()

            if (global_step + 1) % tc.gradient_accumulation_steps == 0:
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

            if global_step % 10 == 0:
                loss_value = float(loss.detach().cpu())
                logger.info("training_progress", step=global_step, total=tc.steps, loss=loss_value)
                if progress_callback:
                    progress_callback(global_step, tc.steps, loss_value)

            global_step += 1

    # Save artifacts
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    lora_dir = out_dir / "lora_dir"
    lora_dir.mkdir(parents=True, exist_ok=True)

    # Save PEFT adapter
    pipe.unet.save_pretrained(str(lora_dir), safe_serialization=True)

    config_path = out_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_model": tc.base_model_name,
                "trigger_token": tc.trigger_token,
                        "instance_prompt": tc.instance_prompt,
                "steps": tc.steps,
                "learning_rate": tc.learning_rate,
                "rank": tc.rank,
                        "lora_alpha": tc.lora_alpha,
                "resolution": tc.resolution,
                "note": "Trained LoRA attention processors (UNet) using diffusers",
            },
            f,
            indent=2,
        )

    logger.info("training_completed", output_path=str(out_dir))

    # Provide a canonical "weights path" (directory)
    return {
        "lora_dir": str(lora_dir),
        "config": str(config_path),
        "samples": [],
    }
