"""HTTP routes under /charsheet/. The logic lives in plain ``handle_*`` functions; aiohttp wrappers are thin."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from urllib.parse import quote

from . import catalog as catalog_module
from . import uploads
from .catalog import AssetsMissingError, LIBS, is_nsfw, select_costume_view
from .nodes import normalize_selection
from .sheet import MIN_SIDE, parse_sheet_state, plan_layout, render_layout

LOCALES_DIR = Path(__file__).resolve().parents[1] / "web" / "locales"
LANGS = ("en", "zh")
PREVIEW_MAX_SIDE = 768
MEDIA_KINDS = {"thumb": "缩略图", "image": "原图"}
_ANIME_SOURCES = ("charadb", "gia-anime")
_FILTER_FIELDS = {
    "portrait": ("发长", "分区"),
    "costume": ("分类",),
    "pose": ("体系", "分类", "角度", "姿势名称"),
}
_TITLE_FIELDS = {
    "portrait": ("标题",),
    "costume": ("服装名称", "标题"),
    "pose": ("姿势名称", "标题"),
}


def _error(status: int, message: str):
    return status, {"error": message}


def _catalog_item(lib: str, item: dict) -> dict:
    thumb = str(item.get("缩略图", ""))
    online = thumb.startswith("https://")
    title = next((item[k] for k in _TITLE_FIELDS[lib] if item.get(k)), item["id"])
    out = {
        "id": item["id"],
        "title": title,
        "thumb": thumb if online else f"/charsheet/thumb/{lib}/{quote(item['id'], safe='')}",
        "nsfw": is_nsfw(lib, item),
        "online": online,
    }
    for field in _FILTER_FIELDS[lib]:
        out[field] = item.get(field, "")
    if lib == "costume":
        out["source"] = item.get("source") or "gia"
        out["一级分类"] = item.get("一级分类") or ("二次元" if out["source"] in _ANIME_SOURCES else "现实")
        out["views"] = [view["id"] for view in item.get("views", [])]
    out["search"] = item.get("检索", "")
    return out


def handle_catalog(lib: str):
    if lib not in LIBS:
        return _error(400, f"unknown library: {lib}")
    try:
        items = catalog_module.default_catalog().items(lib)
    except AssetsMissingError as exc:
        return _error(503, str(exc))
    return 200, [_catalog_item(lib, item) for item in items]


def handle_uploads_list(lib: str):
    if lib not in LIBS:
        return _error(400, f"unknown library: {lib}")
    return 200, {"items": uploads.list_uploads(uploads.input_dir(), lib)}


def handle_upload_delete(lib: str, name: str):
    if lib not in LIBS or not uploads.is_valid_upload_name(name):
        return _error(400, "invalid library or file name")
    if not uploads.delete_upload(uploads.input_dir(), lib, name):
        return _error(404, f"uploaded image not found: {name}")
    return 200, {"deleted": True}


def _depth_rel(rel: str) -> str:
    clean = rel.lstrip("/")
    for root in ("thumbs", "img"):
        if clean.startswith(f"{root}/") and not clean.startswith(f"{root}/depth/"):
            stem = clean[len(root) + 1:].rsplit(".", 1)[0]
            return f"{root}/depth/{stem}.webp"
    return clean


MEDIA_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def media_content_type(path) -> str:
    """Content-Type for a served gallery file, decided by suffix (not the process-wide mimetypes table)."""
    return MEDIA_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


def resolve_media(lib: str, item_id: str, kind: str, view=None, depth: bool = False):
    """Return ``(200, Path)`` for a gallery thumbnail or full image, else ``(status, {"error": ...})``."""
    if kind not in MEDIA_KINDS:
        return _error(400, f"unknown image kind: {kind}")
    if lib not in LIBS:
        return _error(404, f"unknown library: {lib}")
    if uploads.parse_upload_id(item_id) is not None:
        return _error(404, "uploaded images are served by ComfyUI's /view endpoint")
    try:
        catalog = catalog_module.default_catalog()
        item = catalog.find(lib, item_id)
        if lib == "costume":
            item = select_costume_view(item, view or "front")
        rel = str(item.get(MEDIA_KINDS[kind], ""))
        if rel.startswith("https://"):
            return _error(404, f"online-only image, load it from its source: {item_id}")
        if depth and lib == "pose":
            rel = _depth_rel(rel)
        return 200, catalog.image_path(rel)
    except AssetsMissingError as exc:
        return _error(503, str(exc))
    except (ValueError, FileNotFoundError) as exc:
        return _error(404, str(exc))


def _preview_state(state: dict, plan: dict) -> tuple[dict, tuple[int, int]]:
    """A state that renders the same grid at most PREVIEW_MAX_SIDE px on the long side."""
    scale = min(1.0, PREVIEW_MAX_SIDE / max(plan["width"], plan["height"]))
    target = (max(1, round(plan["width"] * scale)), max(1, round(plan["height"] * scale)))
    if scale == 1.0:
        return state, target
    small = {
        **state, "size_mode": "manual", "columns": plan["columns"],
        "width": max(MIN_SIDE, target[0]), "height": max(MIN_SIDE, target[1]),
    }
    return small, target


def handle_sheet_preview(body):
    if not isinstance(body, dict):
        return _error(400, "request body must be a JSON object")
    try:
        selection = normalize_selection(body, allow_empty=False)
        raw_state = body.get("state") or {}
        state = parse_sheet_state(raw_state if isinstance(raw_state, str) else json.dumps(raw_state))
        plan = plan_layout(len(selection["ids"]), state)
        preview_state, target = _preview_state(state, plan)
        flipped = set(selection["flip"])
        entries = [
            {"id": item_id, "flip": item_id in flipped, "use_depth": selection["use_depth"]}
            for item_id in selection["ids"]
        ]
        image = render_layout(catalog_module.default_catalog(), entries, preview_state)
        if image.size != target:
            from PIL import Image

            image = image.resize(target, Image.Resampling.LANCZOS)
    except AssetsMissingError as exc:
        return _error(503, str(exc))
    except (ValueError, TypeError, FileNotFoundError) as exc:
        return _error(400, str(exc))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return 200, {
        "width": plan["width"],
        "height": plan["height"],
        "megapixels": round(plan["width"] * plan["height"] / 1_000_000, 2),
        "warnings": plan["warnings"],
        "image": f"data:image/png;base64,{encoded}",
    }


def _read_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def handle_locales(lang: str):
    if lang not in LANGS:
        return _error(404, f"unsupported language: {lang}")
    try:
        strings = _read_json_file(LOCALES_DIR / f"{lang}.json")
        data = {}
        if lang == "en":
            data = _read_json_file(catalog_module.default_catalog().assets_dir / "locales" / "en" / "data.json")
    except (OSError, ValueError) as exc:
        return _error(500, f"locale file could not be read: {exc}")
    return 200, {"strings": strings, "data": data}


def register_routes() -> None:
    """Register the aiohttp routes on ComfyUI's PromptServer; does nothing outside ComfyUI."""
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return
    if getattr(PromptServer, "instance", None) is None:
        return

    import asyncio

    routes = PromptServer.instance.routes

    async def offload(func, *args):
        return await asyncio.get_running_loop().run_in_executor(None, func, *args)

    def respond(result, cache=None):
        status, payload = result
        headers = {"Cache-Control": cache} if cache and status == 200 else None
        return web.json_response(payload, status=status, headers=headers)

    @routes.get("/charsheet/catalog/{lib}")
    async def get_catalog(request):
        return respond(await offload(handle_catalog, request.match_info["lib"]), "public, max-age=300")

    async def serve_media(request, kind):
        query = request.query
        depth = query.get("depth", "") in ("1", "true")
        status, payload = await offload(
            lambda: resolve_media(
                request.match_info["lib"], request.match_info["id"], kind, query.get("view"), depth
            )
        )
        if status != 200:
            return web.json_response(payload, status=status)
        return web.FileResponse(
            payload,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Type": media_content_type(payload),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @routes.get("/charsheet/thumb/{lib}/{id}")
    async def get_thumb(request):
        return await serve_media(request, "thumb")

    @routes.get("/charsheet/image/{lib}/{id}")
    async def get_image(request):
        return await serve_media(request, "image")

    @routes.get("/charsheet/uploads")
    async def get_uploads(request):
        return respond(await offload(handle_uploads_list, request.query.get("lib", "")))

    @routes.delete("/charsheet/uploads/{lib}/{name}")
    async def delete_upload(request):
        return respond(handle_upload_delete(request.match_info["lib"], request.match_info["name"]))

    @routes.post("/charsheet/sheet/preview")
    async def post_preview(request):
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"error": "request body is not valid JSON"}, status=400)
        return respond(await offload(handle_sheet_preview, body))

    @routes.get("/charsheet/locales/{lang}.json")
    async def get_locales(request):
        return respond(handle_locales(request.match_info["lang"]), "no-cache")
