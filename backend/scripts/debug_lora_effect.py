import argparse
import sys
from pathlib import Path

import torch
from diffusers import StableDiffusionPipeline
from peft import PeftModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug: check if LoRA changes UNet outputs.")
    parser.add_argument("--base-model", default="sd15")
    parser.add_argument(
        "--lora-dir",
        default=str((Path(__file__).resolve().parents[2] / "_debug" / "lora7").resolve()),
        help="Directory with adapter_config.json + adapter_model.safetensors",
    )
    args = parser.parse_args()

    # Lazy imports from our app after sys.path fix.
    from app.services.base_models import apply_runtime_offline_env, ensure_base_model_present

    apply_runtime_offline_env()
    base_dir = ensure_base_model_present(args.base_model)

    device = torch.device("cpu")

    pipe = StableDiffusionPipeline.from_pretrained(
        str(base_dir),
        safety_checker=None,
        requires_safety_checker=False,
        torch_dtype=torch.float32,
        local_files_only=True,
    )
    pipe.to(device)
    pipe.unet.eval()

    # Small synthetic inputs (fast)
    latents = torch.randn(1, 4, 16, 16, device=device, dtype=torch.float32)
    timesteps = torch.tensor([500], device=device, dtype=torch.int64)
    encoder_hidden_states = torch.randn(1, 77, 768, device=device, dtype=torch.float32)

    with torch.no_grad():
        base_out = pipe.unet(latents, timesteps, encoder_hidden_states).sample

    # Apply LoRA
    lora_dir = Path(args.lora_dir)
    if not lora_dir.exists():
        raise SystemExit(f"LoRA dir not found: {lora_dir}")

    pipe.unet = PeftModel.from_pretrained(pipe.unet, str(lora_dir))
    pipe.unet.eval()

    with torch.no_grad():
        lora_out = pipe.unet(latents, timesteps, encoder_hidden_states).sample

    mean_abs = (base_out - lora_out).abs().mean().item()
    max_abs = (base_out - lora_out).abs().max().item()

    print("mean_abs_diff", mean_abs)
    print("max_abs_diff", max_abs)
    print("base_out_mean_abs", base_out.abs().mean().item())
    print("lora_out_mean_abs", lora_out.abs().mean().item())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()

