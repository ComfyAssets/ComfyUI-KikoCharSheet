"""Resolve picker IDs to items and load / fit / convert their reference images."""
from __future__ import annotations

import io
import urllib.error
import urllib.request

from . import uploads
from .catalog import Catalog, select_costume_view

RESIZE_MODES = ("original", "crop to size", "pad to size")
REMOTE_LIMIT_BYTES = 10 * 1024 * 1024
MAX_REMOTE_PIXELS = 20_000_000
MAX_UPLOAD_PIXELS = 50_000_000
REMOTE_SOURCES = {"charadb": {"JPEG"}, "gia-anime": {"PNG", "WEBP"}}
_CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("remote image URL must not redirect")


def resolve_item(catalog: Catalog, lib: str, item_id: str, view: str = "front") -> dict:
    clean_id = (item_id or "").strip()
    name = uploads.parse_upload_id(clean_id)
    if name is not None:
        if uploads.resolve_upload_path(uploads.input_dir(), lib, name) is None:
            raise ValueError(f"uploaded image not found: {clean_id}")
        return {"id": clean_id, "source": "upload", "原图": clean_id}
    item = catalog.find(lib, clean_id)
    return select_costume_view(item, view) if lib == "costume" else item


def pose_image_rel_path(item: dict, use_depth: bool = False) -> str:
    if item.get("source") == "upload":
        return item["原图"]
    raw = str(item.get("原图", "")).lstrip("/")
    if use_depth and raw.startswith("img/") and not raw.startswith("img/depth/"):
        stem = raw[len("img/"):].rsplit(".", 1)[0]
        return f"img/depth/{stem}.webp"
    return raw


def _open_upload(lib: str, item_id: str):
    from PIL import Image

    name = uploads.parse_upload_id(item_id)
    path = uploads.resolve_upload_path(uploads.input_dir(), lib, name)
    if path is None:
        raise ValueError(f"uploaded image not found: {item_id}")
    try:
        image = Image.open(path)
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(f"uploaded image could not be read: {item_id}") from exc
    try:
        if image.width * image.height > MAX_UPLOAD_PIXELS:
            raise ValueError(f"uploaded image is too large (over {MAX_UPLOAD_PIXELS // 1_000_000} MP): {item_id}")
        image.load()
    except ValueError:
        image.close()
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        image.close()
        raise ValueError(f"uploaded image could not be read: {item_id}") from exc
    return image


def _fetch_remote(catalog: Catalog, item: dict, url: str, opener=None):
    """Fetch an allowlisted CharaDB / anime costume image into memory."""
    from PIL import Image

    label = item.get("id", url)
    allowed = {
        row["原图"]: REMOTE_SOURCES[row["source"]]
        for row in catalog.items("costume")
        if row.get("source") in REMOTE_SOURCES
    }
    if url not in allowed:
        raise ValueError(f"remote image is not in the costume catalogue: {label}")
    formats = allowed[url]
    opener = opener or urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(
        url, headers={"User-Agent": "comfyui-h3-charsheet", "Accept": "image/jpeg,image/png,image/webp"}
    )
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200 or response.headers.get_content_type() not in {
                _CONTENT_TYPES[f] for f in formats
            }:
                raise ValueError(f"remote image has the wrong type: {label}")
            if int(response.headers.get("Content-Length", 0) or 0) > REMOTE_LIMIT_BYTES:
                raise ValueError(f"remote image is over 10 MB: {label}")
            raw = response.read(REMOTE_LIMIT_BYTES + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise ValueError(f"costume {label} needs an internet connection to load its image ({exc})") from exc
    if len(raw) > REMOTE_LIMIT_BYTES:
        raise ValueError(f"remote image is over 10 MB: {label}")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in formats or image.width * image.height > MAX_REMOTE_PIXELS:
            raise ValueError(f"remote image has the wrong format or size: {label}")
        image.load()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"remote image could not be read: {label}") from exc
    return image


def open_item_image(catalog: Catalog, lib: str, item: dict, *, use_depth: bool = False, opener=None):
    from PIL import Image

    rel = pose_image_rel_path(item, use_depth) if lib == "pose" else str(item.get("原图", ""))
    if uploads.parse_upload_id(rel) is not None:
        return _open_upload(lib, rel)
    if rel.startswith("https://"):
        return _fetch_remote(catalog, item, rel, opener)
    return Image.open(catalog.image_path(rel))


def fit(img, mode: str, width: int, height: int, flip: bool = False):
    from PIL import Image, ImageOps

    if mode not in RESIZE_MODES:
        raise ValueError(f"unknown resize mode: {mode!r}")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if flip:
        img = ImageOps.mirror(img)
    if mode == "original":
        return img
    size = (int(width), int(height))
    if mode == "crop to size":
        return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
    return ImageOps.pad(img, size, method=Image.Resampling.LANCZOS, color=(255, 255, 255))


def to_tensor(img):
    import numpy as np
    import torch

    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def blank(width: int, height: int):
    from PIL import Image

    return Image.new("RGB", (int(width), int(height)), (255, 255, 255))
