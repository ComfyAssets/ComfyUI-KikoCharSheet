"""The four ComfyUI nodes: Portrait / Costume / Pose pickers and the Pose Sheet designer."""
from __future__ import annotations

import json

from . import catalog as catalog_module
from . import images, prompts, uploads
from .sheet import DEFAULT_STYLE, MAX_POSES, parse_sheet_state, plan_layout, render_layout, sheet_prompt

CATEGORY = "CharSheet"
POSES_TYPE = "CHARSHEET_POSES"
DEFAULT_IDS = {"portrait": "f71f980dde3", "costume": "SPR-0001"}
COSTUME_VIEWS = ("front", "diag", "side", "back")  # the fork's view set
DEFAULT_RESIZE_MODE = "crop to size"
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1024, 1280
PLACEHOLDER_SIZE = 64


def _load_object(raw, what: str) -> dict:
    text = (raw or "").strip() if isinstance(raw, str) else ""
    if not isinstance(raw, str) and raw is not None:
        raise ValueError(f"{what} must be a JSON string")
    try:
        data = json.loads(text) if text else {}
    except ValueError as exc:
        raise ValueError(f"{what} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{what} must be a JSON object")
    return data


def parse_pick_state(raw, lib: str) -> dict:
    """Validate a Portrait / Costume node's ``state_json``; an empty id falls back to the default."""
    data = _load_object(raw, "picker state")
    item_id = data.get("id", "")
    if not isinstance(item_id, str):
        raise ValueError(f"id must be a string, got {item_id!r}")
    state = {"id": item_id.strip() or DEFAULT_IDS[lib]}
    if lib == "costume":
        view = data.get("view", "front")
        if view not in COSTUME_VIEWS:
            raise ValueError(f"view must be one of {', '.join(COSTUME_VIEWS)}, got {view!r}")
        state["view"] = view
    return state


def normalize_selection(data: dict, *, allow_empty: bool = True) -> dict:
    """Validate ``{"ids", "flip", "use_depth"}`` and fill in defaults."""
    ids = data.get("ids", [])
    flip = data.get("flip", [])
    use_depth = data.get("use_depth", False)
    for name, value in (("ids", ids), ("flip", flip)):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{name} must be a list of strings")
    if not isinstance(use_depth, bool):
        raise ValueError(f"use_depth must be true or false, got {use_depth!r}")
    if len(ids) > MAX_POSES:
        raise ValueError(f"at most {MAX_POSES} poses can be selected, got {len(ids)}")
    if not ids and not allow_empty:
        raise ValueError("select at least one pose")
    return {"ids": list(ids), "flip": list(flip), "use_depth": use_depth}


def parse_pose_state(raw) -> dict:
    """Validate a Pose node's ``state_json``."""
    return normalize_selection(_load_object(raw, "pose state"))


def _upload_cache_key(lib: str, item_id) -> str:
    name = uploads.parse_upload_id(item_id)
    if name is None:
        return ""
    path = uploads.resolve_upload_path(uploads.input_dir(), lib, name)
    if path is None:
        return ""
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _validate(parse, *args):
    try:
        parse(*args)
    except ValueError as exc:
        return str(exc)
    return True


def _picker_inputs() -> dict:
    return {
        "required": {
            "state_json": ("STRING", {"multiline": True, "default": ""}),
            "resize_mode": (list(images.RESIZE_MODES), {"default": DEFAULT_RESIZE_MODE}),
            "width": ("INT", {"default": DEFAULT_WIDTH, "min": 64, "max": 8192, "step": 8}),
            "height": ("INT", {"default": DEFAULT_HEIGHT, "min": 64, "max": 8192, "step": 8}),
        }
    }


def _open_fitted(lib, item_id, view, mode, width, height, *, flip=False, use_depth=False):
    """Resolve one gallery or uploaded item and return (catalog, item, fitted PIL image)."""
    catalog = catalog_module.default_catalog()
    item = images.resolve_item(catalog, lib, item_id, view)
    source = images.open_item_image(catalog, lib, item, use_depth=use_depth)
    try:
        return catalog, item, images.fit(source, mode, width, height, flip=flip)
    finally:
        source.close()


class _PickerNode:
    LIB = ""
    FUNCTION = "run"
    CATEGORY = CATEGORY
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("image", "prompt_en", "prompt_zh", "id")

    @classmethod
    def INPUT_TYPES(cls):
        return _picker_inputs()

    @classmethod
    def VALIDATE_INPUTS(cls, state_json):
        return _validate(parse_pick_state, state_json, cls.LIB)

    @classmethod
    def IS_CHANGED(cls, state_json="", **kwargs):
        try:
            return _upload_cache_key(cls.LIB, parse_pick_state(state_json, cls.LIB)["id"])
        except ValueError:
            return ""

    def run(self, state_json, resize_mode, width, height):
        state = parse_pick_state(state_json, self.LIB)
        catalog, item, image = _open_fitted(
            self.LIB, state["id"], state.get("view", "front"), resize_mode, width, height
        )
        describe = lambda lang: prompts.describe(self.LIB, item, lang)  # noqa: E731
        return (images.to_tensor(image), describe("en"), describe("zh"), state["id"])


class CharSheetPortrait(_PickerNode):
    LIB = "portrait"


class CharSheetCostume(_PickerNode):
    LIB = "costume"
    # The footwear outputs carry only the footwear instruction, for prompts that leave the garment list out.
    RETURN_TYPES = _PickerNode.RETURN_TYPES + ("STRING", "STRING")
    RETURN_NAMES = _PickerNode.RETURN_NAMES + ("footwear_en", "footwear_zh")

    @classmethod
    def INPUT_TYPES(cls):
        inputs = _picker_inputs()
        inputs["optional"] = {"include_footwear": ("BOOLEAN", {"default": True})}
        return inputs

    def run(self, state_json, resize_mode, width, height, include_footwear=True):
        image, prompt_en, prompt_zh, item_id = super().run(state_json, resize_mode, width, height)
        return (
            image,
            prompts.with_footwear(prompt_en, include_footwear, "en"),
            prompts.with_footwear(prompt_zh, include_footwear, "zh"),
            item_id,
            prompts.with_footwear("", include_footwear, "en"),
            prompts.with_footwear("", include_footwear, "zh"),
        )


class CharSheetPose:
    FUNCTION = "run"
    CATEGORY = CATEGORY
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "IMAGE", "IMAGE", POSES_TYPE, "INT")
    RETURN_NAMES = ("poses", "pose_prompts_en", "pose_prompts_zh", "pose_1", "pose_2", "selection", "count")
    OUTPUT_IS_LIST = (True, True, True, False, False, False, False)

    @classmethod
    def INPUT_TYPES(cls):
        return _picker_inputs()

    @classmethod
    def VALIDATE_INPUTS(cls, state_json):
        return _validate(parse_pose_state, state_json)

    @classmethod
    def IS_CHANGED(cls, state_json="", **kwargs):
        try:
            ids = parse_pose_state(state_json)["ids"]
        except ValueError:
            return ""
        return "|".join(_upload_cache_key("pose", item_id) for item_id in ids)

    def run(self, state_json, resize_mode, width, height):
        selection = parse_pose_state(state_json)
        flipped = set(selection["flip"])
        tensors, texts_en, texts_zh = [], [], []
        for item_id in selection["ids"]:
            mirrored = item_id in flipped
            catalog, item, image = _open_fitted(
                "pose", item_id, "front", resize_mode, width, height,
                flip=mirrored, use_depth=selection["use_depth"],
            )
            tensors.append(images.to_tensor(image))
            for target, lang in ((texts_en, "en"), (texts_zh, "zh")):
                target.append(prompts.describe("pose", item, lang, mirrored=mirrored))
        count = len(tensors)
        blank = lambda: images.to_tensor(images.blank(width, height))  # noqa: E731
        pose_1 = tensors[0] if count > 0 else blank()
        pose_2 = tensors[1] if count > 1 else blank()
        if not tensors:
            tensors, texts_en, texts_zh = [blank()], [""], [""]
        return (tensors, texts_en, texts_zh, pose_1, pose_2, selection, count)


class CharSheetPoseSheet:
    FUNCTION = "run"
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "INT")
    RETURN_NAMES = (
        "prompt", "prompt_zh", "width", "height", "layout_image", "image_1", "image_2", "image_3", "picture_count",
    )
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "selection": (POSES_TYPE,),
                "state_json": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "character_image": ("IMAGE",),
                "outfit_image": ("IMAGE",),
                "character_prompt": ("STRING", {"forceInput": True}),
                "outfit_prompt": ("STRING", {"forceInput": True}),
                "style": ("STRING", {"multiline": False, "default": DEFAULT_STYLE["en"]}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, state_json):
        return _validate(parse_sheet_state, state_json)

    def run(self, selection, state_json, character_image=None, outfit_image=None,
            character_prompt="", outfit_prompt="", style=""):
        if not isinstance(selection, dict):
            raise ValueError("selection must come from a Pose Picker (Char Sheet) node")
        selection = normalize_selection(selection, allow_empty=False)
        state = parse_sheet_state(state_json)
        catalog = catalog_module.default_catalog()
        flipped = set(selection["flip"])
        items = [images.resolve_item(catalog, "pose", item_id) for item_id in selection["ids"]]
        texts = {
            lang: [
                prompts.describe("pose", item, lang, mirrored=item_id in flipped)
                for item_id, item in zip(selection["ids"], items)
            ]
            for lang in ("en", "zh")
        }
        entries = [
            {"id": item_id, "flip": item_id in flipped, "use_depth": selection["use_depth"]}
            for item_id in selection["ids"]
        ]
        plan = plan_layout(len(entries), state)
        layout = images.to_tensor(render_layout(catalog, entries, state))

        has_character, has_outfit = character_image is not None, outfit_image is not None
        pictures = [p for p in (character_image, layout, outfit_image) if p is not None]
        placeholder = images.to_tensor(images.blank(PLACEHOLDER_SIZE, PLACEHOLDER_SIZE))
        slots = pictures + [placeholder] * (3 - len(pictures))

        def prompt(lang):
            return sheet_prompt(
                len(entries), has_character, has_outfit, texts[lang], lang,
                character_prompt=character_prompt or "", outfit_prompt=outfit_prompt or "",
                style=style or "",
            )

        result = (
            prompt("en"), prompt("zh"), plan["width"], plan["height"], layout, *slots, len(pictures),
        )
        ui = {"selection": [json.dumps(selection)], "warnings": list(plan["warnings"])}
        return {"ui": ui, "result": result}


NODE_CLASS_MAPPINGS = {
    "CharSheetPortrait": CharSheetPortrait,
    "CharSheetCostume": CharSheetCostume,
    "CharSheetPose": CharSheetPose,
    "CharSheetPoseSheet": CharSheetPoseSheet,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CharSheetPortrait": "Portrait Picker (Char Sheet)",
    "CharSheetCostume": "Costume Picker (Char Sheet)",
    "CharSheetPose": "Pose Picker (Char Sheet)",
    "CharSheetPoseSheet": "Pose Sheet Designer (Char Sheet)",
}
