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
# Pose images are this pack's own grey model renders, shipped in poses/img/<style>/ and
# poses/thumbs/<style>/ as WebP under the pose's file name. "grey_wide" is a wide-lens set that
# holds only the renders that differ from "grey", so it falls back to it.
POSE_STYLES = ("grey", "grey_wide")
DEFAULT_POSE_STYLE = "grey"
# Values of states saved while the gallery's line and depth images were still offered.
_LEGACY_POSE_STYLES = ("line", "depth")
_MEDIA_ROOTS = ("img", "thumbs")
_RENDER_SUFFIX = ".webp"
PLACEHOLDER_SIZE = 64  # side of the blank image a node sends where it has no picture
_STYLE_ORDER = {"grey": ("grey",), "grey_wide": ("grey_wide", "grey")}
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


def normalize_pose_style(value) -> str:
    """A valid pose style; nothing, or a style from before the grey renders, means the default."""
    if value is None or value == "" or value in _LEGACY_POSE_STYLES:
        return DEFAULT_POSE_STYLE
    if value not in POSE_STYLES:
        raise ValueError(f"style must be one of {', '.join(POSE_STYLES)}, got {value!r}")
    return value


def _style_rel(clean: str, style: str) -> str:
    """The render of the pose image ``clean`` in ``style``; other paths come back unchanged."""
    root, _, rest = clean.partition("/")
    if root not in _MEDIA_ROOTS or not rest or rest.split("/", 1)[0] in POSE_STYLES:
        return clean
    return f"{root}/{style}/{rest.rsplit('.', 1)[0]}{_RENDER_SUFFIX}"


def pose_style_rels(rel: str, style: str = DEFAULT_POSE_STYLE) -> list[str]:
    """Paths under ``poses/`` to try, in order, for the render or thumbnail of a pose in ``style``.

    ``rel`` is the pose's path in the gallery data, which only supplies the file name.
    """
    clean = str(rel or "").lstrip("/")
    return [_style_rel(clean, step) for step in _STYLE_ORDER[normalize_pose_style(style)]]


def pose_render_path(catalog: Catalog, rel: str, style: str = DEFAULT_POSE_STYLE):
    """The render file for a pose: the first candidate that exists; the last one's error otherwise."""
    rels = pose_style_rels(rel, style)
    for candidate in rels[:-1]:
        try:
            return catalog.pose_path(candidate)
        except FileNotFoundError:
            continue
    return catalog.pose_path(rels[-1])


def has_pose_render(catalog: Catalog, item: dict, style: str = DEFAULT_POSE_STYLE) -> bool:
    """Whether ``style`` has its own render of this pose (fallbacks do not count)."""
    try:
        catalog.pose_path(pose_style_rels(str(item.get("原图", "")), style)[0])
    except (FileNotFoundError, ValueError):
        return False
    return True


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
        url, headers={"User-Agent": "ComfyUI-KikoCharSheet", "Accept": "image/jpeg,image/png,image/webp"}
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


def open_item_image(catalog: Catalog, lib: str, item: dict, *, style: str = DEFAULT_POSE_STYLE, opener=None):
    from PIL import Image

    rel = str(item.get("原图", ""))
    if uploads.parse_upload_id(rel) is not None:
        return _open_upload(lib, rel)
    if rel.startswith("https://"):
        return _fetch_remote(catalog, item, rel, opener)
    if lib == "pose":
        return Image.open(pose_render_path(catalog, rel, style))
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


def is_placeholder(tensor) -> bool:
    """True for the blank white ``PLACEHOLDER_SIZE`` square that stands for "no picture"."""
    shape = tuple(getattr(tensor, "shape", ()))
    if shape != (1, PLACEHOLDER_SIZE, PLACEHOLDER_SIZE, 3):
        return False
    return bool((tensor == 1.0).all())


def blank(width: int, height: int):
    from PIL import Image

    return Image.new("RGB", (int(width), int(height)), (255, 255, 255))
