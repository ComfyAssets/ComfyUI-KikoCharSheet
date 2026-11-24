"""Read-only catalog of the gallery data and images under ``assets/``."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
LIBS = ("portrait", "costume", "pose")

_LIB_FILES = {
    "pose": ("pose-zh.json",),
    "portrait": ("portrait-zh.json",),
    "costume": (
        "costume-zh.json",
        "costume-shisei-zh.json",
        "costume-anime-zh.json",
        "costume-gia-anime-zh.json",
    ),
}
_EXTERNAL_PREFIXES = ("charadb-", "gia-anime-", "shisei-")
_NSFW_POSE_SYSTEMS = frozenset({"全身单人・性感系", "双人缠绵"})
_NSFW_COSTUME_CATEGORIES = frozenset({"内衣・睡衣", "性感穿搭"})
_COSTUME_VIEW_KEYS = ("缩略图", "预览图", "原图")


class AssetsMissingError(RuntimeError):
    """Raised when the gallery data under ``assets/`` has not been set up."""


class Catalog:
    def __init__(self, assets_dir: Path = ASSETS_DIR):
        self.assets_dir = Path(assets_dir)
        self._cache: dict[str, list[dict]] = {}

    def _read_json(self, name: str) -> list[dict]:
        path = self.assets_dir / "data" / name
        if not path.is_file():
            raise AssetsMissingError(
                f"Gallery data not found: {path}. Run `python3 scripts/setup_assets.py --from <fork path>` first."
            )
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def items(self, lib: str) -> list[dict]:
        if lib not in _LIB_FILES:
            raise ValueError(f"unknown library: {lib}")
        if lib not in self._cache:
            merged: list[dict] = []
            for name in _LIB_FILES[lib]:
                merged.extend(self._read_json(name))
            self._cache[lib] = merged
        return self._cache[lib]

    def find(self, lib: str, item_id: str) -> dict:
        clean_id = (item_id or "").strip()
        for item in self.items(lib):
            if item.get("id") == clean_id:
                return item
        if clean_id.startswith(_EXTERNAL_PREFIXES):
            raise ValueError("unknown external-source costume ID")
        raise ValueError(f"unknown {lib} id: {clean_id}")

    def image_path(self, rel: str) -> Path:
        clean = (rel or "").strip().replace("\\", "/").lstrip("/")
        candidate = (self.assets_dir / clean).resolve()
        roots = ((self.assets_dir / "img").resolve(), (self.assets_dir / "thumbs").resolve())
        if not any(candidate.is_relative_to(root) for root in roots):
            raise ValueError(f"illegal image path: {rel}")
        if not candidate.is_file():
            raise FileNotFoundError(f"image file not found: {clean}")
        return candidate


def select_costume_view(item: dict, view: str = "front") -> dict:
    if item.get("source") == "upload":
        return item
    views = item.get("views", [])
    if not views:
        return item
    selected = next((v for v in views if v["id"] == view), None)
    if selected is None:
        if view != "front":
            raise ValueError(f"costume has no such view: {view}")
        selected = views[0]
    return dict(item, selectedView=selected["id"], **{k: selected[k] for k in _COSTUME_VIEW_KEYS})


def is_nsfw(lib: str, item: dict) -> bool:
    if lib == "pose":
        return item.get("体系") in _NSFW_POSE_SYSTEMS
    if lib == "costume":
        return bool(item.get("敏感")) or item.get("分类") in _NSFW_COSTUME_CATEGORIES
    return False


@lru_cache(maxsize=1)
def default_catalog() -> Catalog:
    return Catalog()
