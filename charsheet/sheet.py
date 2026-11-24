"""Pose sheet: grid layout math, the layout image for MiniMax H3, and the sheet prompt."""
from __future__ import annotations

import json
import math

from .images import fit, open_item_image, resolve_item

MAX_POSES = 13
AUTO_AREA = 2048 * 2048
STEP = 32
MIN_PANEL = 256
MAX_COLUMNS = 7
MAX_CANVAS_RATIO = 4  # longest side : shortest side of an Auto canvas; stops 13 poses becoming a 1x13 strip
MIN_SIDE = 64
MAX_SIDE = 8192
GAP_RATIO = 0.02
PANEL_ASPECTS = {"1:2": 0.5, "2:3": 2 / 3, "1:1": 1.0}
BACKGROUNDS = {"white": (255, 255, 255), "lightgray": (225, 225, 225)}
SIZE_MODES = ("auto", "manual")
_PANEL_FILL = (255, 255, 255)
_FRAME = (170, 170, 170)
_LABEL = (60, 60, 60)
_INK_THRESHOLD = 20
_PAD_RATIO = 0.04

_DEFAULTS = {
    "columns": "auto",
    "panel_aspect": "1:2",
    "size_mode": "auto",
    "width": 2048,
    "height": 2048,
    "labels": False,
    "background": "white",
}


def _check_dimension(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_SIDE <= value <= MAX_SIDE:
        raise ValueError(f"{name} must be a whole number from {MIN_SIDE} to {MAX_SIDE}, got {value!r}")
    return value


def parse_sheet_state(raw: str) -> dict:
    """Validate the Pose Sheet node's ``state_json`` and fill in defaults."""
    text = (raw or "").strip()
    try:
        data = json.loads(text) if text else {}
    except ValueError as exc:
        raise ValueError(f"sheet settings are not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("sheet settings must be a JSON object")
    state = {**_DEFAULTS, **{k: v for k, v in data.items() if k in _DEFAULTS}}

    columns = state["columns"]
    if columns != "auto" and (
        isinstance(columns, bool) or not isinstance(columns, int) or not 1 <= columns <= MAX_COLUMNS
    ):
        raise ValueError(f'columns must be "auto" or a number from 1 to {MAX_COLUMNS}, got {columns!r}')
    if state["panel_aspect"] not in PANEL_ASPECTS:
        raise ValueError(f"panel_aspect must be one of {', '.join(PANEL_ASPECTS)}, got {state['panel_aspect']!r}")
    if state["size_mode"] not in SIZE_MODES:
        raise ValueError(f"size_mode must be \"auto\" or \"manual\", got {state['size_mode']!r}")
    state["width"] = _check_dimension("width", state["width"])
    state["height"] = _check_dimension("height", state["height"])
    if not isinstance(state["labels"], bool):
        raise ValueError(f"labels must be true or false, got {state['labels']!r}")
    if state["background"] not in BACKGROUNDS:
        raise ValueError(f"background must be \"white\" or \"lightgray\", got {state['background']!r}")
    return state


def _round_step(value: float) -> int:
    return max(STEP, int(round(value / STEP)) * STEP)


def _grid(n: int, columns: int, width: int, height: int) -> tuple[list[tuple[int, int, int, int]], int]:
    """Panels in reading order on a width x height canvas; the last row is centred."""
    rows = math.ceil(n / columns)
    gap = max(2, round(GAP_RATIO * min(width, height)))
    panel_w = (width - 2 * gap - (columns - 1) * gap) // columns
    panel_h = (height - 2 * gap - (rows - 1) * gap) // rows
    top = (height - rows * panel_h - (rows - 1) * gap) // 2
    panels = []
    for index in range(n):
        row, col = divmod(index, columns)
        in_row = min(columns, n - row * columns)
        left = (width - in_row * panel_w - (in_row - 1) * gap) // 2
        panels.append((left + col * (panel_w + gap), top + row * (panel_h + gap), panel_w, panel_h))
    return panels, rows


def _auto_canvas(columns: int, rows: int, aspect: float) -> tuple[int, int]:
    ratio = columns * aspect / rows
    return _round_step(math.sqrt(AUTO_AREA * ratio)), _round_step(math.sqrt(AUTO_AREA / ratio))


def _candidate_columns(n: int, state: dict) -> list[int]:
    fixed = state["columns"]
    if fixed != "auto":
        return [min(fixed, n)]
    return list(range(1, min(n, MAX_COLUMNS) + 1))


def plan_layout(n: int, state: dict) -> dict:
    """Choose columns, canvas size and panel rectangles for ``n`` poses."""
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_POSES:
        raise ValueError(f"a pose sheet needs 1 to {MAX_POSES} poses, got {n!r}")
    aspect = PANEL_ASPECTS[state["panel_aspect"]]
    manual = state["size_mode"] == "manual"
    best = None
    for columns in _candidate_columns(n, state):
        rows = math.ceil(n / columns)
        width, height = (
            (_round_step(state["width"]), _round_step(state["height"])) if manual else _auto_canvas(columns, rows, aspect)
        )
        if not manual and max(width, height) / min(width, height) > MAX_CANVAS_RATIO:
            continue
        panels, rows = _grid(n, columns, width, height)
        # Auto size: panel area is AUTO_AREA / cells, so fewest cells wins. Manual: compare real panel area.
        score = -(panels[0][2] * panels[0][3]) if manual else columns * rows
        key = (score, rows)
        if best is None or key < best[0]:
            best = (key, columns, rows, width, height, panels)
    if best is None:
        raise ValueError(f"no grid fits {n} poses; choose a column count")
    _, columns, rows, width, height, panels = best
    warnings = []
    short_side = min(min(w, h) for _, _, w, h in panels)
    if short_side < MIN_PANEL:
        w, h = panels[0][2], panels[0][3]
        warnings.append(f"Panels are only {w}×{h} px; pick fewer poses or a larger size.")
    return {
        "width": width, "height": height, "columns": columns, "rows": rows,
        "panels": panels, "warnings": warnings, "sheet_warnings": warnings,
    }


def _trim_white(img):
    from PIL import Image, ImageChops

    diff = ImageChops.difference(img, Image.new("RGB", img.size, (255, 255, 255))).convert("L")
    box = diff.point(lambda v: 255 if v > _INK_THRESHOLD else 0).getbbox()
    return img.crop(box) if box else img


def _load_figure(catalog, entry: dict):
    item = resolve_item(catalog, "pose", entry["id"])
    source = open_item_image(catalog, "pose", item, use_depth=bool(entry.get("use_depth")))
    try:
        flipped = fit(source, "original", 0, 0, flip=bool(entry.get("flip")))
    finally:
        source.close()
    return _trim_white(flipped)


def _label_font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_layout(catalog, pose_entries: list[dict], state: dict):
    """Draw the pose layout image: one equally scaled figure per panel."""
    from PIL import Image, ImageDraw

    if not pose_entries:
        raise ValueError("the layout needs at least one pose")
    plan = plan_layout(len(pose_entries), state)
    figures = [_load_figure(catalog, entry) for entry in pose_entries]
    panel_w = min(p[2] for p in plan["panels"])
    panel_h = min(p[3] for p in plan["panels"])
    pad = max(2, round(_PAD_RATIO * min(panel_w, panel_h)))
    inner_w, inner_h = max(1, panel_w - 2 * pad), max(1, panel_h - 2 * pad)
    target_h = min([inner_h] + [inner_w * fig.height / fig.width for fig in figures])

    canvas = Image.new("RGB", (plan["width"], plan["height"]), BACKGROUNDS[state["background"]])
    draw = ImageDraw.Draw(canvas)
    font = _label_font(max(14, panel_h // 18)) if state["labels"] else None
    for number, (fig, (x, y, w, h)) in enumerate(zip(figures, plan["panels"]), start=1):
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=_PANEL_FILL, outline=_FRAME)
        scale = target_h / fig.height
        size = (max(1, round(fig.width * scale)), max(1, round(target_h)))
        resized = fig.resize(size, Image.Resampling.LANCZOS)
        canvas.paste(resized, (x + (w - size[0]) // 2, y + (h - size[1]) // 2))
        if font:
            draw.text((x + pad, y + pad), str(number), fill=_LABEL, font=font)
    return canvas


_PROMPT = {
    "en": {
        "make": "Create one character reference sheet of {who}, shown {times} of <Picture {L}>, in order left to right, top to bottom.",
        "who_person": "the person from <Picture 1>",
        "who_generic": "one person",
        "times_many": "{n} times in the {n} panels",
        "times_one": "once in the single panel",
        "person": " The person: {text}.",
        "match": " {scope}, match the pose and camera angle of the mannequin in that panel of <Picture {L}>; the mannequin is only a pose guide, not an appearance reference.",
        "scope_many": "In each panel",
        "scope_one": "In the panel",
        "dress_many": " Dress the person in the complete outfit from <Picture {O}> in every panel.",
        "dress_one": " Dress the person in the complete outfit from <Picture {O}>.",
        "outfit": " The outfit: {text}.",
        "keep": " Keep the face, hairstyle, skin tone and body proportions identical in every panel.",
        "panel": " Panel {i}: {text}.",
        "end": " Full body from head to toe in each panel, white gaps between panels, plain white background, no text or numbers.",
    },
    "zh": {
        "make": "生成一张角色设定参考图：{who}，{times}<Picture {L}>的{scope_tail}，顺序为从左到右、从上到下。",
        "who_person": "<Picture 1>中的人物",
        "who_generic": "一位人物",
        "times_many": "在",
        "times_one": "出现一次，位于",
        "person": "人物描述：{text}。",
        "match": "{scope}，人物的姿势和镜头角度须与<Picture {L}>对应格子里的人偶一致；人偶仅作姿势参考，不是外观参考。",
        "scope_many": "每个格子中",
        "scope_one": "在这个格子中",
        "dress_many": "每个格子里都让人物穿上<Picture {O}>中的完整服装。",
        "dress_one": "让人物穿上<Picture {O}>中的完整服装。",
        "outfit": "服装描述：{text}。",
        "keep": "每个格子中人物的面部、发型、肤色和身材比例保持完全一致。",
        "panel": "第{i}格：{text}。",
        "end": "每个格子均为从头到脚的全身像，格子之间留有白色间隙，纯白背景，不要文字或数字。",
    },
}


def _first_sentence(lang: str, n: int, who: str, layout_no: int) -> str:
    t = _PROMPT[lang]
    if lang == "en":
        times = t["times_one"] if n == 1 else t["times_many"].format(n=n)
        return t["make"].format(who=who, times=times, L=layout_no)
    if n == 1:
        times, tail = t["times_one"], "单个分格中"
    else:
        times, tail = t["times_many"], f"{n}个分格中依次出现{n}次"
    # zh word order: "…，在<Picture 2>的2个分格中依次出现2次，…" / "…，出现一次，位于<Picture 2>的单个分格中，…"
    return t["make"].format(who=who, times=times, L=layout_no, scope_tail=tail)


def sheet_prompt(
    n: int,
    has_character: bool,
    has_outfit: bool,
    pose_texts: list[str],
    lang: str,
    character_prompt: str = "",
    outfit_prompt: str = "",
) -> str:
    """The MiniMax H3 prompt for a pose sheet; pictures are character, layout, outfit."""
    if lang not in _PROMPT:
        raise ValueError(f"unsupported language: {lang!r}")
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_POSES:
        raise ValueError(f"a pose sheet needs 1 to {MAX_POSES} poses, got {n!r}")
    if len(pose_texts) != n:
        raise ValueError(f"expected {n} pose descriptions, got {len(pose_texts)}")
    t = _PROMPT[lang]
    layout_no = 2 if has_character else 1
    outfit_no = layout_no + 1
    many = n > 1
    who = t["who_person"] if has_character else t["who_generic"]

    parts = [_first_sentence(lang, n, who, layout_no)]
    if character_prompt.strip():
        parts.append(t["person"].format(text=character_prompt.strip()))
    parts.append(t["match"].format(scope=t["scope_many" if many else "scope_one"], L=layout_no))
    if has_outfit:
        parts.append(t["dress_many" if many else "dress_one"].format(O=outfit_no))
        if outfit_prompt.strip():
            parts.append(t["outfit"].format(text=outfit_prompt.strip()))
    parts.append(t["keep"])
    for index, text in enumerate(pose_texts, start=1):
        parts.append(t["panel"].format(i=index, text=text.strip().rstrip(".。")))
    parts.append(t["end"])
    return "".join(parts) if lang == "zh" else "".join(parts).lstrip()
