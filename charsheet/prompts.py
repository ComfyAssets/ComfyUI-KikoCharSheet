"""English and Chinese item descriptions for picker prompts."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# English names for the gallery's Chinese data values (pose names, categories, costume tags...).
# It ships with the pack, so users get the translations without downloading anything extra.
DATA_MAP = Path(__file__).resolve().parents[1] / "locales" / "en" / "data.json"

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
def _table(path: Path) -> dict:
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return table if isinstance(table, dict) else {}


def make_translator(data_map: Path | None = None):
    """Return value -> English; unknown or empty entries fall back to the original."""
    table = _table(Path(data_map or DATA_MAP))

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


def describe(lib: str, item: dict, lang: str, mirrored: bool = False, data_map=None) -> str:
    if lib not in _BUILDERS:
        raise ValueError(f"unknown library: {lib}")
    if lang not in _MIRRORED:
        raise ValueError(f"unsupported language: {lang!r}")
    if item.get("source") == "upload":
        text = _UPLOAD_TEXT[lang][lib]
    elif isinstance(item.get("prompt"), dict):  # a built-in item carries its own wording
        text = item["prompt"][lang]
    else:
        td = make_translator(data_map)
        text = _BUILDERS[lib](item, lang, td)
    return text + (_MIRRORED[lang] if mirrored else "")


_FOOTWEAR = {
    "en": {True: "include the footwear shown in the outfit picture, worn on both feet",
           False: "leave out the footwear, the person wears no shoes"},
    "zh": {True: "包含服装图中的鞋子，双脚都要穿上", False: "不要鞋子，人物不穿鞋"},
}


def with_footwear(text: str, include: bool, lang: str) -> str:
    """Append the footwear instruction to a costume description."""
    if lang not in _FOOTWEAR:
        raise ValueError(f"unsupported language: {lang!r}")
    base = (text or "").strip().rstrip(".。;；")
    note = _FOOTWEAR[lang][bool(include)]
    if not base:
        return note[0].upper() + note[1:]
    return base + ("；" if lang == "zh" else "; ") + note


_OUTFIT = {
    "en": {
        "picture": "<Picture {n}> is the outfit. Dress the character in the complete outfit from <Picture {n}>, "
                   "copying every garment, colour and material exactly from that picture.",
        "words": "The character is {text}.",
        "join": " ",
        "stop": ".",
    },
    "zh": {
        "picture": "<Picture {n}>是服装。让人物穿上<Picture {n}>中的完整服装，每件衣物的款式、颜色和材质都须与该图完全一致。",
        "words": "人物{text}。",
        "join": "",
        "stop": "。",
    },
}


def outfit_instruction(item: dict, lang: str, picture: int, include_footwear: bool) -> str:
    """The outfit sentences for a prompt written by hand, where the outfit is ``<Picture picture>``.

    A costume with a picture is copied from that picture, with the footwear instruction after it.
    A costume with no picture is put in words and names no picture.
    """
    if lang not in _OUTFIT:
        raise ValueError(f"unsupported language: {lang!r}")
    if isinstance(picture, bool) or not isinstance(picture, int) or picture < 1:
        raise ValueError(f"the outfit picture number must be 1 or more, got {picture!r}")
    t = _OUTFIT[lang]
    if isinstance(item.get("prompt"), dict):
        return t["words"].format(text=item["prompt"][lang].strip().rstrip(".。"))
    return t["picture"].format(n=picture) + t["join"] + with_footwear("", include_footwear, lang) + t["stop"]
