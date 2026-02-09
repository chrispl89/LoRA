from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.core.config import get_models_dir, settings
from app.core.logging import get_logger
from app.services.s3 import s3_service

logger = get_logger(__name__)


def _slugify_base_model_id(base_model_name: str) -> str:
    """
    Convert any identifier (alias, HF repo id, path-ish string) to a safe folder slug.
    Examples:
      - "sd15" -> "sd15"
      - "runwayml/stable-diffusion-v1-5" -> "runwayml__stable-diffusion-v1-5"
    """
    name = (base_model_name or "").strip()
    if not name:
        return "unknown"
    name = name.replace("\\", "/")
    name = name.replace("/", "__")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:120]


def resolve_base_model_dir(base_model_name: str) -> Path:
    """
    Resolve base model directory on disk.
    If user passes an existing local directory path, use it directly.
    Otherwise, treat base_model_name as alias/repo-id and map to models/base/<slug>.
    """
    if base_model_name:
        p = Path(base_model_name).expanduser()
        if p.exists() and p.is_dir():
            return p.resolve()

    slug = _slugify_base_model_id(base_model_name)
    return (get_models_dir() / "base" / slug).resolve()


def _looks_like_diffusers_model(dir_path: Path) -> bool:
    """
    Check if a local folder looks like a *complete* diffusers pipeline.

    We intentionally require core components (UNet/VAE/Text encoder weights) so we don't
    start training on a partially downloaded base model.
    """
    if not (dir_path / "model_index.json").exists():
        return False

    # Required configs
    required = [
        dir_path / "unet" / "config.json",
        dir_path / "vae" / "config.json",
        dir_path / "text_encoder" / "config.json",
        dir_path / "tokenizer" / "tokenizer_config.json",
    ]
    if not all(p.exists() for p in required):
        return False

    def has_weights(p: Path) -> bool:
        return any((p / name).exists() for name in ("diffusion_pytorch_model.bin", "diffusion_pytorch_model.safetensors"))

    if not has_weights(dir_path / "unet"):
        return False
    if not has_weights(dir_path / "vae"):
        return False

    # Text encoder weights
    if not ((dir_path / "text_encoder" / "pytorch_model.bin").exists() or (dir_path / "text_encoder" / "model.safetensors").exists()):
        return False

    return True


def ensure_base_model_present(base_model_name: str) -> Path:
    """
    Ensure base model exists locally. Runtime never downloads from Hugging Face.
    If missing locally, it will be fetched from MinIO prefix:
      s3://<bucket>/models/base/<slug>/**
    """
    base_dir = resolve_base_model_dir(base_model_name)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Fast-path: already present
    has_any_file = any(base_dir.rglob("*"))
    if has_any_file and _looks_like_diffusers_model(base_dir):
        return base_dir

    slug = _slugify_base_model_id(base_model_name)
    prefix = f"models/base/{slug}/"
    keys = s3_service.list_files(prefix)
    if not keys:
        msg = (
            f"Base model not available offline.\n"
            f"- requested: {base_model_name!r}\n"
            f"- expected local dir: {str(base_dir)}\n"
            f"- expected MinIO prefix: {prefix}\n\n"
            f"Bootstrap it once using huggingface-cli to a local dir, then upload to MinIO."
        )
        raise RuntimeError(msg)

    logger.info("base_model_downloading_from_s3", requested=base_model_name, prefix=prefix, dest=str(base_dir))
    for key in keys:
        if key.endswith("/"):
            continue
        rel = key[len(prefix) :]
        out_path = base_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        s3_service.download_file(key, str(out_path))

    if not _looks_like_diffusers_model(base_dir):
        raise RuntimeError(f"Downloaded base model from MinIO but it doesn't look complete: {base_dir}")

    return base_dir


def apply_runtime_offline_env() -> None:
    """
    Best-effort enforcement: set offline env vars for this process.
    start-services.ps1 should set these for spawned processes, but this is a safeguard.
    """
    if not settings.HF_RUNTIME_OFFLINE:
        return

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
