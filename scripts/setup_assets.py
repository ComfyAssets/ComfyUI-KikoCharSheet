#!/usr/bin/env python3
"""Copy the gallery data and images from the ai-pose-gallery fork into ``assets/``."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DEFAULT_DEST = Path(__file__).resolve().parents[1] / "assets"
FOLDERS = ("data", "img", "thumbs")
LOCALE_REL = Path("locales") / "en" / "data.json"


class SourceMissingError(FileNotFoundError):
    pass


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def setup(source: Path, dest: Path, force: bool) -> dict:
    source, dest = Path(source), Path(dest)
    missing = [n for n in FOLDERS if not (source / n).is_dir()]
    if missing:
        raise SourceMissingError(
            f"Source {source} is missing: {', '.join(missing)}. Clone the ai-pose-gallery fork "
            "and run its scripts/download.py to fetch the images, then pass its path with --from."
        )
    targets = [dest / n for n in FOLDERS] + [dest / LOCALE_REL]
    existing = [t for t in targets if os.path.lexists(t)]
    if existing and not force:
        raise FileExistsError(f"{existing[0]} already exists; use --force to overwrite")
    dest.mkdir(parents=True, exist_ok=True)
    for t in existing:
        _remove(t)
    for name in FOLDERS:
        shutil.copytree(source / name, dest / name)
    locale_src = source / LOCALE_REL
    locale_copied = locale_src.is_file()
    if locale_copied:
        (dest / LOCALE_REL).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(locale_src, dest / LOCALE_REL)
    return {
        "mode": "copy",
        "source": str(source),
        "dest": str(dest),
        "folders": list(FOLDERS),
        "locale": locale_copied,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="source", required=True, type=Path, help="path to the ai-pose-gallery fork")
    ap.add_argument("--force", action="store_true", help="overwrite existing assets")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        res = setup(args.source.expanduser(), args.dest, args.force)
    except SourceMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    note = "" if res["locale"] else " (no locales/en/data.json found in source; English data names unavailable)"
    print(f"{res['mode']}: {', '.join(res['folders'])} from {res['source']} -> {res['dest']}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
