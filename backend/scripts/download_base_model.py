from __future__ import annotations

import argparse
from pathlib import Path
import sys
import os

from huggingface_hub import snapshot_download

# Ensure `backend/` is on sys.path when running as a script from `backend/scripts/`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.base_models import resolve_base_model_dir  # noqa: E402


def read_token_from_dotenv(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    try:
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("HUGGINGFACE_HUB_TOKEN="):
                val = line.split("=", 1)[1].strip().strip("\"'").strip()
                return val or None
    except Exception:
        return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time bootstrap: download a HF repo (diffusers model) into the app's local models/base/<slug> dir."
    )
    parser.add_argument(
        "--repo-id",
        required=True,
        help='HF repo id, e.g. "runwayml/stable-diffusion-v1-5" or "hf-internal-testing/tiny-stable-diffusion-pipe".',
    )
    parser.add_argument(
        "--base-model-name",
        default=None,
        help='What the app will store in DB as base_model_name. If omitted, uses repo-id (slugified).',
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Optional HF token (needed only for gated models).",
    )
    args = parser.parse_args()

    # This script is for *bootstrap downloads*. If you run it in a shell where
    # start-services.ps1 set offline env vars, override them so download works.
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)

    env_path = Path(__file__).resolve().parents[1] / ".env"
    token = args.token or read_token_from_dotenv(env_path) or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or None

    base_model_name = (args.base_model_name or args.repo_id).strip()
    dest_dir = resolve_base_model_dir(base_model_name)
    dest_dir.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=args.repo_id,
        local_dir=str(dest_dir),
        local_dir_use_symlinks=False,
        token=token,
    )

    print(str(dest_dir))


if __name__ == "__main__":
    main()
