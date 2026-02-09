import argparse
import time
from pathlib import Path


def run_one(
    *,
    prompt: str,
    negative_prompt: str,
    steps: int,
    width: int,
    height: int,
    seed: int,
    base_model_name: str,
    lora_path: str | None,
    output_path: Path,
) -> None:
    # Delay heavy imports until after we print progress.
    from app.services.inference.generate import generate_image

    generate_image(
        prompt=prompt,
        negative_prompt=negative_prompt,
        model_version_id=0,
        lora_path=lora_path,
        steps=steps,
        width=width,
        height=height,
        seed=seed,
        output_path=str(output_path),
        base_model_name=base_model_name,
        progress_callback=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug: compare base vs LoRA generation with same seed.")
    parser.add_argument("--prompt", default="portrait photo of sks person, studio lighting")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--base-model", default="sd15")
    parser.add_argument(
        "--lora-dir",
        default=str((Path(__file__).resolve().parents[2] / "_debug" / "lora7").resolve()),
        help="Directory with adapter_config.json + adapter_model.safetensors",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = (repo_root / "_debug" / "compare_fast").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_out = out_dir / "base.png"
    lora_out = out_dir / "lora.png"

    print("output_dir", out_dir)
    print("base_only start")
    t0 = time.time()
    run_one(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        steps=args.steps,
        width=args.width,
        height=args.height,
        seed=args.seed,
        base_model_name=args.base_model,
        lora_path=None,
        output_path=base_out,
    )
    print("base_only done_s", round(time.time() - t0, 2), "path", base_out)

    print("lora start", "lora_dir", args.lora_dir)
    t0 = time.time()
    run_one(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        steps=args.steps,
        width=args.width,
        height=args.height,
        seed=args.seed,
        base_model_name=args.base_model,
        lora_path=args.lora_dir,
        output_path=lora_out,
    )
    print("lora done_s", round(time.time() - t0, 2), "path", lora_out)


if __name__ == "__main__":
    # Allow running the script directly: `python -u backend/scripts/debug_compare_lora.py`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()

