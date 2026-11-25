import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch  # noqa: E402
from PIL import Image  # noqa: E402

from charsheet import nodes, uploads  # noqa: E402
from charsheet.catalog import Catalog  # noqa: E402
from charsheet.sheet import plan_layout, parse_sheet_state, sheet_prompt  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"


class NodeTestCase(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog(FIXTURE)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.input_dir = Path(tmp.name)
        for target, value in (
            ("charsheet.catalog.default_catalog", lambda: self.cat),
            ("charsheet.uploads.input_dir", lambda: self.input_dir),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def put_upload(self, lib, name, size=(30, 20), color=(10, 20, 30)):
        path = uploads.upload_dir(self.input_dir, lib) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(path)
        return path


class PickStateTests(unittest.TestCase):
    def test_portrait_defaults_and_value(self):
        self.assertEqual(nodes.parse_pick_state("", "portrait"), {"id": "f71f980dde3"})
        self.assertEqual(nodes.parse_pick_state("{}", "portrait"), {"id": "f71f980dde3"})
        self.assertEqual(nodes.parse_pick_state('{"id": " por-a "}', "portrait"), {"id": "por-a"})

    def test_costume_defaults_and_view(self):
        self.assertEqual(nodes.parse_pick_state("", "costume"), {"id": "SPR-0001", "view": "front"})
        self.assertEqual(nodes.parse_pick_state('{"id": "x", "view": "back"}', "costume")["view"], "back")

    def test_costume_views_match_the_fork(self):
        self.assertEqual(nodes.COSTUME_VIEWS, ("front", "diag", "side", "back"))
        for view in nodes.COSTUME_VIEWS:
            with self.subTest(view=view):
                self.assertEqual(nodes.parse_pick_state(f'{{"id": "x", "view": "{view}"}}', "costume")["view"], view)

    def test_empty_id_uses_default(self):
        self.assertEqual(nodes.parse_pick_state('{"id": ""}', "costume")["id"], "SPR-0001")

    def test_rejects_bad_input(self):
        for bad in ("[]", "nope", '{"id": 3}', '{"view": "top"}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                nodes.parse_pick_state(bad, "costume")


class PoseStateTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(nodes.parse_pose_state(""), {"ids": [], "flip": [], "style": "grey"})

    def test_values(self):
        got = nodes.parse_pose_state('{"ids": ["a", "b"], "flip": ["b"], "style": "grey_wide"}')
        self.assertEqual(got, {"ids": ["a", "b"], "flip": ["b"], "style": "grey_wide"})

    def test_states_from_before_the_grey_renders_use_grey(self):
        for old in ('{"ids": ["a"], "use_depth": true}', '{"ids": ["a"], "use_depth": false, "style": "line"}',
                    '{"ids": ["a"], "use_depth": true, "style": "depth"}'):
            with self.subTest(old=old):
                self.assertEqual(nodes.parse_pose_state(old), {"ids": ["a"], "flip": [], "style": "grey"})

    def test_rejects_unknown_style(self):
        for bad in ('{"style": "clay"}', '{"style": 3}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                nodes.parse_pose_state(bad)

    def test_thirteen_ok_fourteen_fails(self):
        nodes.parse_pose_state(json.dumps({"ids": [f"p{i}" for i in range(13)]}))
        with self.assertRaises(ValueError) as cm:
            nodes.parse_pose_state(json.dumps({"ids": [f"p{i}" for i in range(14)]}))
        self.assertIn("13", str(cm.exception))

    def test_rejects_bad_shapes(self):
        for bad in ("[]", "nope", '{"ids": "a"}', '{"ids": [1]}', '{"flip": [2]}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                nodes.parse_pose_state(bad)


class ValidateTests(unittest.TestCase):
    def test_validate_inputs(self):
        for cls in (nodes.CharSheetPortrait, nodes.CharSheetCostume, nodes.CharSheetPose, nodes.CharSheetPoseSheet):
            self.assertIs(cls.VALIDATE_INPUTS(state_json=""), True)
            self.assertIsInstance(cls.VALIDATE_INPUTS(state_json="not json"), str)
        too_many = json.dumps({"ids": [f"p{i}" for i in range(14)]})
        self.assertIn("13", nodes.CharSheetPose.VALIDATE_INPUTS(state_json=too_many))
        self.assertIsInstance(nodes.CharSheetPoseSheet.VALIDATE_INPUTS(state_json='{"columns": 9}'), str)


class PickerNodeTests(NodeTestCase):
    def test_portrait_output(self):
        image, en, zh, item_id = nodes.CharSheetPortrait().run('{"id": "por-a"}', "crop to size", 64, 80)
        self.assertEqual(tuple(image.shape), (1, 80, 64, 3))
        self.assertEqual(item_id, "por-a")
        self.assertIn("hairstyle", en)
        self.assertIn("人物面部与发型", zh)

    def test_costume_view_and_defaults(self):
        node = nodes.CharSheetCostume()
        image, en, zh, item_id, *_ = node.run('{"id": "shisei-C001", "view": "back"}', "pad to size", 50, 60)
        self.assertEqual(tuple(image.shape), (1, 60, 50, 3))
        self.assertEqual(item_id, "shisei-C001")
        self.assertEqual(node.run("", "original", 10, 10)[3], "SPR-0001")

    def test_costume_footwear_option(self):
        node = nodes.CharSheetCostume()
        self.assertTrue(nodes.CharSheetCostume.INPUT_TYPES()["optional"]["include_footwear"][1]["default"])
        self.assertNotIn("optional", nodes.CharSheetPortrait.INPUT_TYPES())
        self.assertEqual(nodes.CharSheetCostume.RETURN_NAMES[:4], nodes.CharSheetPortrait.RETURN_NAMES)
        self.assertEqual(nodes.CharSheetCostume.RETURN_NAMES[4:], ("footwear_en", "footwear_zh"))
        self.assertEqual(node.run("", "original", 10, 10)[4:],
                         ("Include the footwear shown in the outfit picture, worn on both feet", "包含服装图中的鞋子，双脚都要穿上"))
        self.assertEqual(node.run("", "original", 10, 10, include_footwear=False)[4:],
                         ("Leave out the footwear, the person wears no shoes", "不要鞋子，人物不穿鞋"))
        _, en, zh, _ = node.run("", "original", 10, 10)[:4]
        self.assertTrue(en.lower().endswith("include the footwear shown in the outfit picture, worn on both feet"))
        self.assertTrue(zh.endswith("包含服装图中的鞋子，双脚都要穿上"))
        _, en, zh, _ = node.run("", "original", 10, 10, include_footwear=False)[:4]
        self.assertTrue(en.lower().endswith("leave out the footwear, the person wears no shoes"))
        self.assertTrue(zh.endswith("不要鞋子，人物不穿鞋"))

    def test_unknown_id_names_it(self):
        with self.assertRaises(ValueError) as cm:
            nodes.CharSheetPortrait().run('{"id": "nope"}', "original", 64, 64)
        self.assertIn("nope", str(cm.exception))

    def test_upload_prompts(self):
        self.put_upload("portrait", "me.png")
        _, en, zh, item_id = nodes.CharSheetPortrait().run('{"id": "upload:me.png"}', "original", 64, 64)
        self.assertEqual(en, "the person in the uploaded portrait photo")
        self.assertEqual(zh, "参考上传的人像照片")
        self.assertEqual(item_id, "upload:me.png")

    def test_missing_upload_names_id(self):
        with self.assertRaises(ValueError) as cm:
            nodes.CharSheetCostume().run('{"id": "upload:gone.png"}', "original", 64, 64)
        self.assertIn("upload:gone.png", str(cm.exception))

    def test_is_changed(self):
        self.assertEqual(nodes.CharSheetPortrait.IS_CHANGED(state_json='{"id": "por-a"}'), "")
        path = self.put_upload("portrait", "me.png")
        first = nodes.CharSheetPortrait.IS_CHANGED(state_json='{"id": "upload:me.png"}')
        self.assertNotEqual(first, "")
        st = path.stat()
        Image.new("RGB", (60, 40)).save(path)
        import os
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        self.assertNotEqual(first, nodes.CharSheetPortrait.IS_CHANGED(state_json='{"id": "upload:me.png"}'))

    def test_is_changed_never_raises_on_bad_state(self):
        self.assertEqual(nodes.CharSheetPose.IS_CHANGED(state_json="not json"), "")


class PoseNodeTests(NodeTestCase):
    def run_pose(self, state):
        return nodes.CharSheetPose().run(json.dumps(state), "crop to size", 32, 48)

    def test_output_flags(self):
        self.assertEqual(nodes.CharSheetPose.OUTPUT_IS_LIST, (True, True, True, False, False, False, False))
        self.assertEqual(len(nodes.CharSheetPose.RETURN_TYPES), 7)

    def test_empty_selection(self):
        poses, en, zh, p1, p2, selection, count = self.run_pose({})
        self.assertEqual((len(poses), en, zh, count), (1, [""], [""], 0))
        self.assertEqual(tuple(poses[0].shape), (1, 48, 32, 3))
        self.assertTrue(torch.all(p1 == 1.0) and tuple(p1.shape) == (1, 48, 32, 3))
        self.assertEqual(selection, {"ids": [], "flip": [], "style": "grey"})

    def test_one_two_three_poses(self):
        for ids in (["pose-safe"], ["pose-safe", "pose-nsfw"], ["pose-safe", "pose-nsfw", "pose-safe"]):
            with self.subTest(n=len(ids)):
                poses, en, zh, p1, p2, selection, count = self.run_pose({"ids": ids})
                self.assertEqual((len(poses), len(en), len(zh), count), (len(ids),) * 4)
                self.assertEqual(selection["ids"], ids)
                self.assertEqual(tuple(p1.shape), (1, 48, 32, 3))
                if len(ids) == 1:
                    self.assertTrue(torch.all(p2 == 1.0))
                else:
                    self.assertTrue(torch.equal(p2, poses[1]))

    def test_flip_mirrors_image_and_prompt(self):
        path = self.put_upload("pose", "lr.png", (40, 20))
        img = Image.new("RGB", (40, 20), (0, 0, 255))
        img.paste((255, 0, 0), (0, 0, 20, 20))
        img.save(path)
        state = {"ids": ["upload:lr.png", "pose-safe"], "flip": ["upload:lr.png"]}
        poses, en, zh, *_ = nodes.CharSheetPose().run(json.dumps(state), "original", 40, 20)
        self.assertGreater(float(poses[0][0, 10, 5, 2]), 0.9)  # left is now blue
        self.assertTrue(en[0].endswith("(mirrored)"))
        self.assertTrue(zh[0].endswith("（镜像）"))
        self.assertNotIn("mirrored", en[1])

    def test_unknown_id_names_it(self):
        with self.assertRaises(ValueError) as cm:
            self.run_pose({"ids": ["pose-safe", "ghost"]})
        self.assertIn("ghost", str(cm.exception))

    def test_is_changed_covers_every_upload(self):
        self.put_upload("pose", "a.png")
        state = json.dumps({"ids": ["pose-safe", "upload:a.png"]})
        self.assertNotEqual(nodes.CharSheetPose.IS_CHANGED(state_json=state), "")


class PoseSheetNodeTests(NodeTestCase):
    SELECTION = {"ids": ["pose-safe", "pose-nsfw"], "flip": [], "style": "grey"}

    def run_sheet(self, selection=None, state="", **kw):
        return nodes.CharSheetPoseSheet().run(selection or self.SELECTION, state, **kw)

    def texts(self, flips=()):
        from charsheet import prompts
        return [
            prompts.describe("pose", self.cat.find("pose", i), "en", mirrored=i in flips)
            for i in ("pose-safe", "pose-nsfw")
        ]

    def test_style_reaches_both_prompts(self):
        from charsheet.sheet import DEFAULT_STYLE
        out = self.run_sheet(style=DEFAULT_STYLE["en"])["result"]
        self.assertIn(DEFAULT_STYLE["en"], out[0])
        self.assertIn(DEFAULT_STYLE["zh"], out[1])

    def test_without_character_or_outfit(self):
        out = self.run_sheet()["result"]
        prompt, prompt_zh, width, height, layout, i1, i2, i3, count = out
        plan = plan_layout(2, parse_sheet_state(""))
        self.assertEqual((width, height), (plan["width"], plan["height"]))
        self.assertEqual(tuple(layout.shape), (1, height, width, 3))
        self.assertEqual(count, 1)
        self.assertTrue(torch.equal(i1, layout))
        for blank in (i2, i3):
            self.assertEqual(tuple(blank.shape), (1, 64, 64, 3))
            self.assertTrue(torch.all(blank == 1.0))
        self.assertEqual(prompt, sheet_prompt(2, False, False, self.texts(), "en"))
        self.assertIn("<Picture 1>", prompt)
        self.assertNotIn("<Picture 2>", prompt)
        self.assertIn("第1格", prompt_zh)

    def test_character_only(self):
        char = torch.full((1, 8, 8, 3), 0.25)
        out = self.run_sheet(character_image=char, character_prompt="tall")["result"]
        prompt, _, _, _, layout, i1, i2, i3, count = out
        self.assertEqual(count, 2)
        self.assertTrue(torch.equal(i1, char))
        self.assertTrue(torch.equal(i2, layout))
        self.assertTrue(torch.all(i3 == 1.0))
        self.assertEqual(prompt, sheet_prompt(2, True, False, self.texts(), "en", character_prompt="tall"))

    def test_outfit_only_renumbers(self):
        outfit = torch.full((1, 8, 8, 3), 0.5)
        out = self.run_sheet(outfit_image=outfit, outfit_prompt="coat")["result"]
        prompt, *_, i1, i2, i3, count = out
        self.assertEqual(count, 2)
        self.assertTrue(torch.equal(i2, outfit))
        self.assertEqual(prompt, sheet_prompt(2, False, True, self.texts(), "en", outfit_prompt="coat"))

    def test_both_and_ui_selection(self):
        char, outfit = torch.zeros((1, 8, 8, 3)), torch.ones((1, 8, 8, 3)) * 0.5
        sel = {**self.SELECTION, "flip": ["pose-nsfw"]}
        result = self.run_sheet(sel, character_image=char, outfit_image=outfit)
        *_, i1, i2, i3, count = result["result"]
        self.assertEqual(count, 3)
        self.assertTrue(torch.equal(i1, char) and torch.equal(i3, outfit))
        self.assertEqual(result["result"][0], sheet_prompt(2, True, True, self.texts({"pose-nsfw"}), "en"))
        self.assertEqual(json.loads(result["ui"]["selection"][0]), sel)

    def test_manual_size(self):
        state = json.dumps({"size_mode": "manual", "width": 640, "height": 960})
        _, _, width, height, layout, *_ = self.run_sheet(state=state)["result"]
        self.assertEqual((width, height), (640, 960))
        self.assertEqual(tuple(layout.shape), (1, 960, 640, 3))

    def test_empty_selection_raises(self):
        with self.assertRaises(ValueError):
            self.run_sheet({"ids": [], "flip": [], "style": "grey"})

    def test_unknown_pose_names_it(self):
        with self.assertRaises(ValueError) as cm:
            self.run_sheet({"ids": ["ghost"], "flip": [], "style": "grey"})
        self.assertIn("ghost", str(cm.exception))

    def test_bad_selection_type(self):
        with self.assertRaises(ValueError):
            self.run_sheet("nope")


class RegistrationTests(unittest.TestCase):
    def test_mappings(self):
        self.assertEqual(
            set(nodes.NODE_CLASS_MAPPINGS),
            {"CharSheetPortrait", "CharSheetCostume", "CharSheetPose", "CharSheetPoseSheet"},
        )
        self.assertEqual(nodes.NODE_DISPLAY_NAME_MAPPINGS["CharSheetPoseSheet"], "Pose Sheet Designer (Char Sheet)")
        for cls in nodes.NODE_CLASS_MAPPINGS.values():
            self.assertEqual(cls.CATEGORY, "CharSheet")

    def test_input_types(self):
        req = nodes.CharSheetPortrait.INPUT_TYPES()["required"]
        self.assertEqual(req["resize_mode"][1]["default"], "crop to size")
        self.assertEqual((req["width"][1]["default"], req["height"][1]["default"]), (1024, 1280))
        self.assertTrue(req["state_json"][1]["multiline"])
        sheet = nodes.CharSheetPoseSheet.INPUT_TYPES()
        self.assertEqual(sheet["required"]["selection"][0], "CHARSHEET_POSES")
        self.assertEqual(
            set(sheet["optional"]), {"character_image", "outfit_image", "character_prompt", "outfit_prompt", "style"}
        )
        # The two prompt inputs are sockets only; a multiline widget would leave a gap above the panel.
        for name in ("character_prompt", "outfit_prompt"):
            self.assertTrue(sheet["optional"][name][1]["forceInput"])
        self.assertIn("Photorealistic", sheet["optional"]["style"][1]["default"])



if __name__ == "__main__":
    unittest.main()
