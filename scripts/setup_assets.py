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
# Original-size files that the fork's scripts/download.py fetches and its .gitignore keeps out of
# git (about 6 GB). The nodes read the WebP copies that come with a clone, so these are not copied.
SKIPPED_ORIGINALS = {
    "img/costume": ".png",
    "img/portrait": ".png",
    "img/depth": ".png",
    "thumbs/depth": ".jpg",
}


class SourceMissingError(FileNotFoundError):
    pass


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _skip_originals(source: Path, skipped: list):
    """A ``copytree`` ignore function that leaves out ``SKIPPED_ORIGINALS`` and counts them."""

    def ignore(directory: str, names: list) -> list:
        try:
            rel = Path(directory).resolve().relative_to(source.resolve()).as_posix()
        except ValueError:
            return []
        suffix = SKIPPED_ORIGINALS.get(rel)
        if suffix is None:
            return []
        left_out = [n for n in names if n.lower().endswith(suffix)]
        skipped.extend(left_out)
        return left_out

    return ignore


def setup(source: Path, dest: Path, force: bool) -> dict:
    source, dest = Path(source), Path(dest)
    missing = [n for n in FOLDERS if not (source / n).is_dir()]
    if missing:
        raise SourceMissingError(
            f"Source {source} is missing: {', '.join(missing)}. Clone the ai-pose-gallery fork "
            "(the images come with the clone) and pass its path with --from."
        )
    targets = [dest / n for n in FOLDERS] + [dest / LOCALE_REL]
    existing = [t for t in targets if os.path.lexists(t)]
    if existing and not force:
        raise FileExistsError(f"{existing[0]} already exists; use --force to overwrite")
    dest.mkdir(parents=True, exist_ok=True)
    for t in existing:
        _remove(t)
    skipped: list = []
    for name in FOLDERS:
        shutil.copytree(source / name, dest / name, ignore=_skip_originals(source, skipped))
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
        "skipped_originals": len(skipped),
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
    if res["skipped_originals"]:
        print(f"left out {res['skipped_originals']} original-size files (not used by the nodes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
