#!/usr/bin/env python3
"""Convert a folder of pose renders into the pose pictures this pack ships in ``poses/``.

The PNG files must be named after the pose ids (for example ``full_single_P018_front.png``). Each
one is written to ``poses/img/<style>/`` as WebP, with a small thumbnail in ``poses/thumbs/<style>/``.
Run it with the Python that runs ComfyUI, because it needs Pillow.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_DEST = Path(__file__).resolve().parents[1] / "poses"
STYLES = ("grey", "grey_wide")
IMAGE_QUALITY = 90
THUMB_SIZE = (300, 400)
THUMB_QUALITY = 85
WEBP_METHOD = 6  # slowest, smallest files


def add_pose_set(source: Path, dest: Path, style: str) -> dict:
    """Convert every PNG in ``source`` into the ``style`` set under ``dest``; existing files are replaced."""
    from PIL import Image

    if style not in STYLES:
        raise ValueError(f"style must be one of {', '.join(STYLES)}, got {style!r}")
    source, dest = Path(source), Path(dest)
    if not source.is_dir():
        raise FileNotFoundError(f"source folder not found: {source}")
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    if not files:
        raise FileNotFoundError(f"no PNG files in {source}")
    img_dir, thumb_dir = dest / "img" / style, dest / "thumbs" / style
    img_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        with Image.open(path) as image:
            render = image.convert("RGB")
            render.save(img_dir / f"{path.stem}.webp", "WEBP", quality=IMAGE_QUALITY, method=WEBP_METHOD)
            render.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            render.save(thumb_dir / f"{path.stem}.webp", "WEBP", quality=THUMB_QUALITY, method=WEBP_METHOD)
    return {"style": style, "images": len(files)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="source", required=True, type=Path, help="folder with the PNG renders")
    ap.add_argument("--style", required=True, choices=STYLES, help="which render set these are: grey (standard) or grey_wide (wide lens)")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        res = add_pose_set(args.source.expanduser(), args.dest, args.style)
    except ImportError:
        print("error: Pillow is missing; run this with the Python that runs ComfyUI", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{res['style']}: {res['images']} images -> {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
