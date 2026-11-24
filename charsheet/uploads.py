"""Helpers for user-uploaded picker images stored under ComfyUI's input dir."""
from __future__ import annotations

from pathlib import Path

UPLOAD_PREFIX = "upload:"
LIBS = ("portrait", "costume", "pose")
ALLOWED_EXTS = (".png", ".jpg", ".jpeg", ".webp")
SUBFOLDER = "charsheet"
MAX_NAME_LENGTH = 200


def input_dir() -> Path:
    """ComfyUI's input directory (imported lazily so the package works without ComfyUI)."""
    import folder_paths

    return Path(folder_paths.get_input_directory())


def parse_upload_id(item_id):
    """Return the file name for an `upload:<name>` id, otherwise None."""
    if not isinstance(item_id, str) or not item_id.startswith(UPLOAD_PREFIX):
        return None
    return item_id[len(UPLOAD_PREFIX):]


def is_valid_upload_name(name):
    if not isinstance(name, str) or not name or name.startswith("."):
        return False
    if any(c in "/\\" or ord(c) < 32 or ord(c) == 127 for c in name) or ".." in name:
        return False
    if not name.lower().endswith(ALLOWED_EXTS):
        return False
    return len(name) <= MAX_NAME_LENGTH


def upload_dir(input_dir, lib):
    if lib not in LIBS:
        raise ValueError(f"unknown library: {lib!r}")
    return Path(input_dir) / SUBFOLDER / lib


def resolve_upload_path(input_dir, lib, name):
    if lib not in LIBS or not is_valid_upload_name(name):
        return None
    folder = upload_dir(input_dir, lib)
    candidate = (folder / name).resolve()
    if not candidate.is_relative_to(folder.resolve()):
        return None
    return candidate if candidate.is_file() else None


def list_uploads(input_dir, lib):
    from PIL import Image

    folder = upload_dir(input_dir, lib)
    if not folder.is_dir():
        return []
    items = []
    for entry in folder.iterdir():
        path = resolve_upload_path(input_dir, lib, entry.name)
        if path is None:
            continue
        try:
            with Image.open(path) as img:
                width, height = img.size
            mtime = path.stat().st_mtime
        except (OSError, ValueError):
            continue
        items.append({"name": entry.name, "width": width, "height": height, "mtime": mtime})
    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items


def delete_upload(input_dir, lib, name):
    path = resolve_upload_path(input_dir, lib, name)
    if path is None:
        return False
    path.unlink()
    return True
