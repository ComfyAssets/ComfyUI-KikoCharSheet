#!/usr/bin/env python3
"""Put the gallery data and images the nodes need into ``assets/``.

``--download`` fetches them from the gallery project (ai-pose-gallery-zh) on GitHub: only the
folders the nodes use, about 470 MB, with git. ``--from`` copies them from a clone you already have.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_DEST = Path(__file__).resolve().parents[1] / "assets"
FOLDERS = ("data", "img", "thumbs")
# Original-size files that the fork's scripts/download.py fetches and its .gitignore keeps out of
# git (about 6 GB). The nodes read the WebP copies that come with a clone, so these are not copied.
SKIPPED_ORIGINALS = {
    "img/costume": ".png",
    "img/portrait": ".png",
}
# The gallery's pose images (line drawings directly in img/ and thumbs/, depth images in a depth/
# folder) are not copied: the Pose Picker uses this pack's own renders in poses/ instead.
POSE_ROOTS = ("img", "thumbs")
POSE_DEPTH_DIR = "depth"


GALLERY_URL = "https://github.com/anhao/ai-pose-gallery-zh.git"
# The gallery commit this pack was last checked against. --ref HEAD takes the newest one instead.
GALLERY_REF = "8b6243fb8d5329f4ed12efa1b1f1137908d49c92"
# What --download fetches: the data, the costumes and the portraits. Listing folders one by one
# keeps the gallery's pose images, which sit directly in img/ and thumbs/, out of the download.
DOWNLOAD_PATHS = (
    "/data/",
    "/img/costume/", "/img/costumes/", "/img/portrait/",
    "/thumbs/costume/", "/thumbs/costumes/", "/thumbs/portrait/",
)


class SourceMissingError(FileNotFoundError):
    pass


class DownloadError(RuntimeError):
    pass


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _count_files(path: Path) -> int:
    return sum(1 for p in path.rglob("*") if p.is_file())


def _skip_unused(source: Path, originals: list, poses: list):
    """A ``copytree`` ignore function: leaves out original-size files and gallery pose images, counting both."""

    def ignore(directory: str, names: list) -> list:
        here = Path(directory)
        try:
            rel = here.resolve().relative_to(source.resolve()).as_posix()
        except ValueError:
            return []
        if rel in POSE_ROOTS:
            left_out = [n for n in names if (here / n).is_file() or n == POSE_DEPTH_DIR]
            poses.extend(n for n in left_out if n != POSE_DEPTH_DIR)
            if POSE_DEPTH_DIR in left_out:
                poses.extend([POSE_DEPTH_DIR] * _count_files(here / POSE_DEPTH_DIR))
            return left_out
        suffix = SKIPPED_ORIGINALS.get(rel)
        if suffix is None:
            return []
        left_out = [n for n in names if n.lower().endswith(suffix)]
        originals.extend(left_out)
        return left_out

    return ignore


def _existing_targets(dest: Path) -> list:
    return [t for t in (dest / n for n in FOLDERS) if os.path.lexists(t)]


def download(workdir: Path, ref: str = GALLERY_REF, run=None) -> Path:
    """Fetch ``DOWNLOAD_PATHS`` of the gallery project at ``ref`` into ``workdir`` (an empty folder)."""
    run = run or subprocess.run
    steps = (
        ["init", "--quiet", "."],
        ["remote", "add", "origin", GALLERY_URL],
        ["sparse-checkout", "set", "--no-cone", *DOWNLOAD_PATHS],
        ["fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", ref],
        ["checkout", "--quiet", "FETCH_HEAD"],
    )
    try:
        for step in steps:
            run(["git", *step], cwd=str(workdir), check=True)
    except FileNotFoundError as exc:
        raise DownloadError(
            "git was not found. Install git, or clone the gallery project another way and pass its path with --from."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise DownloadError(
            f"git {exc.cmd[1]} failed while downloading from {GALLERY_URL}. Check your internet connection, "
            "or clone the gallery project yourself and pass its path with --from."
        ) from exc
    return Path(workdir)


def setup(source: Path, dest: Path, force: bool) -> dict:
    source, dest = Path(source), Path(dest)
    missing = [n for n in FOLDERS if not (source / n).is_dir()]
    if missing:
        raise SourceMissingError(
            f"Source {source} is missing: {', '.join(missing)}. Clone "
            "https://github.com/anhao/ai-pose-gallery-zh (the images come with the clone) "
            "and pass its path with --from."
        )
    existing = _existing_targets(dest)
    if existing and not force:
        raise FileExistsError(f"{existing[0]} already exists; use --force to overwrite")
    dest.mkdir(parents=True, exist_ok=True)
    for t in existing:
        _remove(t)
    originals: list = []
    poses: list = []
    for name in FOLDERS:
        shutil.copytree(source / name, dest / name, ignore=_skip_unused(source, originals, poses))
    return {
        "mode": "copy",
        "source": str(source),
        "dest": str(dest),
        "folders": list(FOLDERS),
        "skipped_originals": len(originals),
        "skipped_poses": len(poses),
    }


def _run(args) -> dict:
    if not args.download:
        return setup(args.source.expanduser(), args.dest, args.force)
    existing = _existing_targets(args.dest)
    if existing and not args.force:  # checked first, so nothing is downloaded for nothing
        raise FileExistsError(f"{existing[0]} already exists; use --force to overwrite")
    args.dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".gallery-download-", dir=args.dest.parent) as work:
        print(f"downloading from {GALLERY_URL} (about 470 MB) ...", flush=True)
        return setup(download(Path(work), args.ref), args.dest, args.force)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--download", action="store_true", help="fetch what the nodes need from the gallery project")
    source.add_argument("--from", dest="source", type=Path, help="path to a clone of ai-pose-gallery-zh you already have")
    ap.add_argument("--ref", default=GALLERY_REF, help="with --download: gallery commit or branch (default: the tested one)")
    ap.add_argument("--force", action="store_true", help="overwrite existing assets")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        res = _run(args)
    except (SourceMissingError, DownloadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    origin = GALLERY_URL if args.download else res["source"]
    print(f"{res['mode']}: {', '.join(res['folders'])} from {origin} -> {res['dest']}")
    if res["skipped_originals"]:
        print(f"left out {res['skipped_originals']} original-size files (not used by the nodes)")
    if res["skipped_poses"]:
        print(f"left out {res['skipped_poses']} gallery pose images (the Pose Picker uses this pack's own renders)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
