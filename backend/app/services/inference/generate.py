"""
Image generation service (real inference with diffusers).

Loads a Stable Diffusion base model and applies LoRA weights (UNet attention processors).
CPU-only inference is supported but can be very slow.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Callable

import torch
from PIL import Image

from diffusers import StableDiffusionPipeline
from peft import PeftModel

from app.core.logging import get_logger
from app.services.base_models import apply_runtime_offline_env, ensure_base_model_present

logger = get_logger(__name__)


def generate_image(
    prompt: str,
    negative_prompt: Optional[str] = None,
    model_version_id: int = None,
    lora_path: Optional[str] = None,
    steps: int = 30,
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
    output_path: str = None,
    base_model_name: str = "sd15",
    hf_token: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    logger.info("generation_started", prompt=prompt[:80], steps=steps, width=width, height=height)

    device = torch.device("cpu")

    apply_runtime_offline_env()
    base_model_dir = ensure_base_model_present(base_model_name)

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

    if lora_path:
        # Load PEFT adapter into UNet
        pipe.unet = PeftModel.from_pretrained(pipe.unet, lora_path)

    generator = None
    if seed is not None:
        generator = torch.Generator(device=device).manual_seed(int(seed))

    total_steps = int(steps)

    def _cb(step: int, timestep: int, latents) -> None:  # diffusers callback signature
        if progress_callback:
            progress_callback(int(step), total_steps)

    image: Image.Image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt if negative_prompt else None,
        num_inference_steps=int(steps),
        height=int(height),
        width=int(width),
        generator=generator,
        guidance_scale=7.5,
        callback=_cb if progress_callback else None,
        callback_steps=1 if progress_callback else None,
    ).images[0]

    output_file = Path(output_path) if output_path else Path(f"output_{model_version_id or 'x'}.png")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_file)

    logger.info("generation_completed", output_path=str(output_file))
    return str(output_file)


def generate_thumbnail(image_path: str, thumbnail_path: str, size: tuple = (256, 256)) -> str:
    """Generate thumbnail from image."""
    img = Image.open(image_path)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    img.save(thumbnail_path)
    return thumbnail_path


# TODO: Implement real generation using diffusers
# Example structure:
# def generate_image_real(prompt, lora_path, ...):
#     from diffusers import StableDiffusionPipeline
#     from peft import PeftModel
#     # Load base model
#     pipe = StableDiffusionPipeline.from_pretrained(base_model)
#     # Load LoRA
#     pipe.unet = PeftModel.from_pretrained(pipe.unet, lora_path)
#     # Generate
#     image = pipe(prompt, ...).images[0]
#     return image
