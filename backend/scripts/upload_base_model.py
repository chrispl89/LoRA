from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path
import sys

# Ensure `backend/` is on sys.path when running as a script from `backend/scripts/`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger  # noqa: E402
from app.services.s3 import s3_service  # noqa: E402
from app.services.base_models import resolve_base_model_dir  # noqa: E402

logger = get_logger(__name__)


def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            # snapshot_download may create a local metadata cache under `.cache/` inside local_dir
            if ".cache" in p.parts:
                continue
            yield p


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a local diffusers base model directory to MinIO.")
    parser.add_argument(
        "--base-model-name",
        required=True,
        help='Alias/repo-id used by the app (e.g. "sd15" or "runwayml/stable-diffusion-v1-5").',
    )
    parser.add_argument(
        "--local-dir",
        default=None,
        help="Local directory with diffusers model. If omitted, uses resolved models/base/<slug>.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing objects under models/base/<slug>/ before upload (recommended).",
    )
    args = parser.parse_args()

    base_model_name = args.base_model_name.strip()
    src_dir = Path(args.local_dir).expanduser().resolve() if args.local_dir else resolve_base_model_dir(base_model_name)
    if not src_dir.exists() or not src_dir.is_dir():
        raise SystemExit(f"Directory not found: {src_dir}")

    # Keep prefix compatible with runtime downloader
    slug_dir = resolve_base_model_dir(base_model_name).name
    prefix = f"models/base/{slug_dir}/"

    files = list(iter_files(src_dir))
    if not files:
        raise SystemExit(f"No files found under: {src_dir}")

    if args.clean:
        logger.info("upload_base_model_cleaning_prefix", prefix=prefix)
        s3_service.delete_prefix(prefix)

    logger.info("upload_base_model_started", base_model_name=base_model_name, src=str(src_dir), prefix=prefix, count=len(files))

    for p in files:
        rel = p.relative_to(src_dir).as_posix()
        key = prefix + rel
        ctype, _ = mimetypes.guess_type(str(p))
        s3_service.upload_file(str(p), key, content_type=ctype or "application/octet-stream")

    logger.info("upload_base_model_completed", prefix=prefix)
    print(prefix)


if __name__ == "__main__":
    main()
