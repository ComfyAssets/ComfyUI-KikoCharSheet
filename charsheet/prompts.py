"""English and Chinese item descriptions for picker prompts."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .catalog import default_catalog

_UPLOAD_TEXT = {
    "en": {
        "portrait": "the person in the uploaded portrait photo",
        "costume": "the outfit in the uploaded costume photo",
        "pose": "the pose in the uploaded pose photo",
    },
    "zh": {
        "portrait": "参考上传的人像照片",
        "costume": "参考上传的服装照片",
        "pose": "参考上传的姿势照片",
    },
}
_MIRRORED = {"en": " (mirrored)", "zh": "（镜像）"}


@lru_cache(maxsize=8)
def _table(assets_dir: Path) -> dict:
    path = Path(assets_dir) / "locales" / "en" / "data.json"
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return table if isinstance(table, dict) else {}


def make_translator(assets_dir: Path):
    """Return value -> English; unknown or empty entries fall back to the original."""
    table = _table(Path(assets_dir))

    def translate(value: str) -> str:
        if not value:
            return ""
        translated = table.get(value)
        return translated if isinstance(translated, str) and translated else value

    return translate


def _pose(item: dict, lang: str, td) -> str:
    title = item.get("姿势名称") or item.get("标题") or "标准姿势"
    angle = item.get("角度") or "正面"
    cat = item.get("分类", "")
    if lang == "en":
        return f"{td(angle)} view, pose: {td(title)} ({td(cat)})"
    return f"{item.get('角度', '正面')}视角，动作：{title}（{item.get('体系', '')}·{cat}）"


def _costume(item: dict, lang: str, td) -> str:
    title = item.get("服装名称") or item.get("标题") or ""
    if lang == "en":
        return item.get("关键词", "") or td(title)
    tags = "、".join(item.get("标签", [])[:8])
    return f"身穿{item.get('分类', '')}：{title}" + (f"（细节：{tags}）" if tags else "")


def _portrait(item: dict, lang: str, td) -> str:
    hair_len = item.get("发长", "")
    hair_style = item.get("发型名称") or item.get("发型") or ""
    if lang == "en":
        return f"character hairstyle and face reference: {td(hair_len)}, {td(hair_style)}"
    return f"人物面部与发型：{hair_len}、{hair_style}（{item.get('分区', '')}，{item.get('标题', '')}）"


_BUILDERS = {"pose": _pose, "costume": _costume, "portrait": _portrait}


def describe(lib: str, item: dict, lang: str, mirrored: bool = False, assets_dir=None) -> str:
    if lib not in _BUILDERS:
        raise ValueError(f"unknown library: {lib}")
    if lang not in _MIRRORED:
        raise ValueError(f"unsupported language: {lang!r}")
    if item.get("source") == "upload":
        text = _UPLOAD_TEXT[lang][lib]
    else:
        td = make_translator(assets_dir or default_catalog().assets_dir)
        text = _BUILDERS[lib](item, lang, td)
    return text + (_MIRRORED[lang] if mirrored else "")
