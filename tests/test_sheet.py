import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from charsheet import sheet  # noqa: E402
from charsheet.catalog import Catalog  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"
WHITE = (255, 255, 255)


def state(**kw):
    return {**sheet.parse_sheet_state(""), **kw}


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class ParseStateTests(unittest.TestCase):
    def test_empty_and_braces_give_defaults(self):
        expected = {
            "columns": "auto", "panel_aspect": "1:2", "size_mode": "auto",
            "width": 2048, "height": 2048, "labels": False, "background": "white",
        }
        self.assertEqual(sheet.parse_sheet_state(""), expected)
        self.assertEqual(sheet.parse_sheet_state("{}"), expected)

    def test_valid_values_are_kept(self):
        raw = json.dumps({"columns": 3, "panel_aspect": "2:3", "size_mode": "manual",
                          "width": 1024, "height": 1536, "labels": True, "background": "lightgray"})
        got = sheet.parse_sheet_state(raw)
        self.assertEqual((got["columns"], got["panel_aspect"], got["width"], got["labels"]), (3, "2:3", 1024, True))

    def test_rejects_bad_values(self):
        for bad in (
            {"columns": 8}, {"columns": 0}, {"columns": "x"}, {"columns": True},
            {"panel_aspect": "3:4"}, {"size_mode": "big"}, {"width": "wide"}, {"width": 0},
            {"height": 99999}, {"labels": "yes"}, {"background": "red"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sheet.parse_sheet_state(json.dumps(bad))

    def test_rejects_non_object_and_bad_json(self):
        for bad in ("[]", "not json", "3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sheet.parse_sheet_state(bad)


class PlanLayoutTests(unittest.TestCase):
    def test_auto_layouts(self):
        for n in (1, 2, 5, 7, 13):
            with self.subTest(n=n):
                plan = sheet.plan_layout(n, state())
                self.assertEqual(plan["width"] % 32, 0)
                self.assertEqual(plan["height"] % 32, 0)
                area = plan["width"] * plan["height"]
                self.assertTrue(0.9 * sheet.AUTO_AREA <= area <= 1.1 * sheet.AUTO_AREA, area)
                self.assertEqual(len(plan["panels"]), n)
                self.assertEqual(plan["warnings"], [])
                self.assertEqual(plan["sheet_warnings"], [])
                self.assertLessEqual(plan["columns"], 7)
                self.assertEqual(plan["rows"], -(-n // plan["columns"]))
                for (x, y, w, h) in plan["panels"]:
                    self.assertTrue(x >= 0 and y >= 0 and x + w <= plan["width"] and y + h <= plan["height"])
                    self.assertGreaterEqual(min(w, h), sheet.MIN_PANEL)
                for i, a in enumerate(plan["panels"]):
                    for b in plan["panels"][i + 1:]:
                        self.assertFalse(overlap(a, b))
                order = [(p[1], p[0]) for p in plan["panels"]]
                self.assertEqual(order, sorted(order))

    def test_auto_columns_pick_fewest_cells_and_tie_prefers_fewer_rows(self):
        self.assertEqual(sheet.plan_layout(5, state())["columns"], 5)
        self.assertEqual(sheet.plan_layout(7, state())["columns"], 4)
        # n=4: 4x1 and 2x2 both use four cells; fewer rows wins.
        plan = sheet.plan_layout(4, state())
        self.assertEqual((plan["columns"], plan["rows"]), (4, 1))
        # n=13: 7x2 (14 cells) beats 5x3 (15 cells)
        self.assertEqual(sheet.plan_layout(13, state())["columns"], 7)

    def test_auto_canvas_aspect_is_capped(self):
        self.assertEqual(sheet.MAX_CANVAS_RATIO, 2.5)
        for aspect in ("1:2", "2:3", "1:1"):
            for n in range(1, 14):
                with self.subTest(aspect=aspect, n=n):
                    plan = sheet.plan_layout(n, state(panel_aspect=aspect))
                    ratio = max(plan["width"], plan["height"]) / min(plan["width"], plan["height"])
                    self.assertLessEqual(ratio, 2.6)  # 2.5 plus rounding to steps of 32

    def test_fixed_columns_beyond_the_cap_still_plan(self):
        plan = sheet.plan_layout(7, state(columns=7))
        self.assertEqual((plan["columns"], plan["rows"]), (7, 1))

    def test_fixed_columns_and_centred_last_row(self):
        plan = sheet.plan_layout(5, state(columns=3))
        self.assertEqual((plan["columns"], plan["rows"]), (3, 2))
        first, last = plan["panels"][0], plan["panels"][-1]
        row2 = plan["panels"][3:]
        left_gap = row2[0][0]
        right_gap = plan["width"] - (row2[-1][0] + row2[-1][2])
        self.assertLessEqual(abs(left_gap - right_gap), 1)
        self.assertGreater(left_gap, first[0])
        self.assertGreater(last[1], first[1])

    def test_fixed_columns_larger_than_n_are_clamped(self):
        plan = sheet.plan_layout(2, state(columns=7))
        self.assertEqual((plan["columns"], plan["rows"]), (2, 1))

    def test_panels_have_gaps(self):
        plan = sheet.plan_layout(2, state())
        a, b = plan["panels"]
        self.assertGreater(b[0] - (a[0] + a[2]), 0)

    def test_manual_size_is_rounded_to_steps(self):
        plan = sheet.plan_layout(2, state(size_mode="manual", width=1010, height=1500))
        self.assertEqual((plan["width"], plan["height"]), (1024, 1504))

    def test_manual_small_canvas_warns(self):
        plan = sheet.plan_layout(13, state(size_mode="manual", width=1024, height=1024))
        self.assertEqual(len(plan["warnings"]), 1)
        self.assertIn("Panels are only", plan["warnings"][0])
        self.assertEqual(plan["warnings"], plan["sheet_warnings"])

    def test_rejects_bad_counts(self):
        for n in (0, 14):
            with self.subTest(n=n), self.assertRaises(ValueError):
                sheet.plan_layout(n, state())


class RenderLayoutTests(unittest.TestCase):
    def test_fixture_poses_fill_panel_centres_and_keep_gaps_white(self):
        cat = Catalog(FIXTURE)
        entries = [{"id": "pose-safe", "flip": False, "use_depth": False},
                   {"id": "pose-nsfw", "flip": True, "use_depth": False}]
        st = state()
        plan = sheet.plan_layout(2, st)
        img = sheet.render_layout(cat, entries, st)
        self.assertEqual(img.size, (plan["width"], plan["height"]))
        for (x, y, w, h) in plan["panels"]:
            self.assertEqual(img.getpixel((x + w // 2, y + h // 2)), (255, 0, 0))
        a, b = plan["panels"]
        gap_x = (a[0] + a[2] + b[0]) // 2
        self.assertEqual(img.getpixel((gap_x, plan["height"] // 2)), WHITE)
        self.assertEqual(img.getpixel((0, 0)), WHITE)

    def test_lightgray_background_only_changes_the_gaps(self):
        cat = Catalog(FIXTURE)
        entries = [{"id": "pose-safe", "flip": False, "use_depth": False}]
        img = sheet.render_layout(cat, entries, state(background="lightgray"))
        self.assertNotEqual(img.getpixel((0, 0)), WHITE)

    def test_labels_mark_the_panel_corner(self):
        cat = Catalog(FIXTURE)
        entries = [{"id": "pose-safe", "flip": False, "use_depth": False}]
        plain = sheet.render_layout(cat, entries, state())
        labelled = sheet.render_layout(cat, entries, state(labels=True))
        x, y, w, h = sheet.plan_layout(1, state())["panels"][0]
        box = (x, y, x + 300, y + 300)
        self.assertNotEqual(plain.crop(box).tobytes(), labelled.crop(box).tobytes())
        self.assertEqual(plain.crop((x + w // 2, y + h // 2, x + w // 2 + 4, y + h // 2 + 4)).tobytes(),
                         labelled.crop((x + w // 2, y + h // 2, x + w // 2 + 4, y + h // 2 + 4)).tobytes())

    def test_each_figure_fills_its_own_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "data").mkdir()
            (assets / "img" / "pose").mkdir(parents=True)
            rows = []
            for name, canvas, box in (("tall", (60, 60), (25, 5, 35, 45)), ("wide", (200, 100), (60, 30, 100, 50))):
                im = Image.new("RGB", canvas, WHITE)
                im.paste((0, 0, 0), box)
                im.save(assets / "img" / "pose" / f"{name}.png")
                rows.append({"id": name, "原图": f"img/pose/{name}.png", "体系": "x", "分类": "y"})
            (assets / "data" / "pose-zh.json").write_text(json.dumps(rows), encoding="utf-8")
            entries = [{"id": n, "flip": False, "use_depth": False} for n in ("tall", "wide")]
            st = state()
            plan = sheet.plan_layout(2, st)
            img = sheet.render_layout(Catalog(assets), entries, st)
            pad = max(2, round(0.04 * min(plan["panels"][0][2], plan["panels"][0][3])))
            for (x, y, w, h), (fig_w, fig_h) in zip(plan["panels"], ((10, 40), (40, 20))):
                inner = img.crop((x + 3, y + 3, x + w - 3, y + h - 3)).convert("L").point(lambda v: 255 if v < 100 else 0)
                bbox = inner.getbbox()
                self.assertIsNotNone(bbox)
                self.assertAlmostEqual((bbox[0] + bbox[2]) / 2, (w - 6) / 2, delta=2)
                self.assertAlmostEqual((bbox[1] + bbox[3]) / 2, (h - 6) / 2, delta=2)
                # The figure touches the padded panel on its tighter axis: a wide pose no longer shrinks a tall one.
                scale = min((w - 2 * pad) / fig_w, (h - 2 * pad) / fig_h)
                self.assertAlmostEqual(bbox[2] - bbox[0], fig_w * scale, delta=3)
                self.assertAlmostEqual(bbox[3] - bbox[1], fig_h * scale, delta=3)

    def test_trim_uses_the_corner_colour_so_dark_backgrounds_are_trimmed(self):
        dark = Image.new("RGB", (100, 100), (15, 15, 15))
        dark.paste((230, 230, 230), (40, 10, 50, 70))
        self.assertEqual(sheet._trim_background(dark).size, (10, 60))
        light = Image.new("RGB", (100, 100), WHITE)
        light.paste((0, 0, 0), (40, 10, 50, 70))
        self.assertEqual(sheet._trim_background(light).size, (10, 60))
        self.assertEqual(sheet._trim_background(Image.new("RGB", (20, 30), (15, 15, 15))).size, (20, 30))

    def test_dark_background_drawing_is_scaled_by_its_figure(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "data").mkdir()
            (assets / "img" / "pose").mkdir(parents=True)
            im = Image.new("RGB", (200, 200), (10, 10, 10))
            im.paste((240, 240, 240), (90, 20, 110, 180))
            im.save(assets / "img" / "pose" / "d.png")
            rows = [{"id": "d", "原图": "img/pose/d.png", "体系": "x", "分类": "y"}]
            (assets / "data" / "pose-zh.json").write_text(json.dumps(rows), encoding="utf-8")
            st = state()
            x, y, w, h = sheet.plan_layout(1, st)["panels"][0]
            img = sheet.render_layout(Catalog(assets), [{"id": "d"}], st)
            panel = img.crop((x + 3, y + 3, x + w - 3, y + h - 3)).convert("L").point(lambda v: 255 if v > 128 and v < 250 else 0)
            box = panel.getbbox()
            self.assertGreater((box[3] - box[1]) / h, 0.85)

    def test_rejects_unknown_pose(self):
        with self.assertRaisesRegex(ValueError, "nope"):
            sheet.render_layout(Catalog(FIXTURE), [{"id": "nope", "flip": False, "use_depth": False}], state())

    def test_rejects_empty_entries(self):
        with self.assertRaises(ValueError):
            sheet.render_layout(Catalog(FIXTURE), [], state())


COMMON_EN = ("match the pose and camera angle of the mannequin in that panel of <Picture {L}>; the mannequin is only "
             "a pose guide, not an appearance reference.")
TAIL_EN = ("Keep the face, hairstyle, skin tone and body proportions identical in every panel. "
           "Panel 1: standing. Panel 2: sitting. "
           "Full body from head to toe in each panel, white gaps between panels, plain white background, no text or numbers.")
TAIL_EN_1 = ("Keep the face, hairstyle, skin tone and body proportions identical in every panel. "
             "Panel 1: standing. "
             "Full body from head to toe in each panel, white gaps between panels, plain white background, no text or numbers.")
TAIL_ZH = ("每个格子中人物的面部、发型、肤色和身材比例保持完全一致。第1格：站立。第2格：坐下。"
           "每个格子均为从头到脚的全身像，格子之间留有白色间隙，纯白背景，不要文字或数字。")


class SheetPromptTests(unittest.TestCase):
    texts = ["standing", "sitting"]

    def test_english_character_and_outfit(self):
        got = sheet.sheet_prompt(2, True, True, self.texts, "en")
        want = ("Create one character reference sheet of the person from <Picture 1>, shown 2 times in the 2 panels of "
                "<Picture 2>, in order left to right, top to bottom. In each panel, " + COMMON_EN.format(L=2) +
                " Dress the person in the complete outfit from <Picture 3> in every panel, copying every garment, colour and material exactly from that picture. " + TAIL_EN)
        self.assertEqual(got, want)

    def test_english_character_only(self):
        got = sheet.sheet_prompt(2, True, False, self.texts, "en")
        want = ("Create one character reference sheet of the person from <Picture 1>, shown 2 times in the 2 panels of "
                "<Picture 2>, in order left to right, top to bottom. In each panel, " + COMMON_EN.format(L=2) + " " + TAIL_EN)
        self.assertEqual(got, want)

    def test_english_outfit_only(self):
        got = sheet.sheet_prompt(2, False, True, self.texts, "en")
        want = ("Create one character reference sheet of one person, shown 2 times in the 2 panels of "
                "<Picture 1>, in order left to right, top to bottom. In each panel, " + COMMON_EN.format(L=1) +
                " Dress the person in the complete outfit from <Picture 2> in every panel, copying every garment, colour and material exactly from that picture. " + TAIL_EN)
        self.assertEqual(got, want)

    def test_english_neither(self):
        got = sheet.sheet_prompt(2, False, False, self.texts, "en")
        want = ("Create one character reference sheet of one person, shown 2 times in the 2 panels of "
                "<Picture 1>, in order left to right, top to bottom. In each panel, " + COMMON_EN.format(L=1) + " " + TAIL_EN)
        self.assertEqual(got, want)

    def test_english_single_panel(self):
        got = sheet.sheet_prompt(1, True, True, ["standing"], "en")
        want = ("Create one character reference sheet of the person from <Picture 1>, shown once in the single panel of "
                "<Picture 2>. In the panel, " + COMMON_EN.format(L=2) +
                " Dress the person in the complete outfit from <Picture 3>, copying every garment, colour and material exactly from that picture. " + TAIL_EN_1)
        self.assertEqual(got, want)

    def test_english_extra_descriptions(self):
        got = sheet.sheet_prompt(2, True, True, self.texts, "en", character_prompt="tall, short red hair",
                                 outfit_prompt="a blue trench coat")
        self.assertIn("top to bottom. The person: tall, short red hair. In each panel,", got)
        self.assertIn("exactly from that picture. The outfit's garments, with colours taken from <Picture 3>: "
                      "a blue trench coat. Keep the face,", got)

    def test_style_goes_before_the_closing_sentence(self):
        got = sheet.sheet_prompt(1, True, True, ["standing"], "en", style=sheet.DEFAULT_STYLE["en"])
        self.assertIn("Panel 1: standing. Photorealistic studio photograph, real person, natural skin texture, "
                      "soft even lighting. Full body from head to toe", got)
        self.assertEqual(sheet.sheet_prompt(1, True, True, ["standing"], "en", style="  "),
                         sheet.sheet_prompt(1, True, True, ["standing"], "en"))

    def test_default_style_is_translated_and_custom_style_is_kept(self):
        zh = sheet.sheet_prompt(1, True, True, ["站立"], "zh", style=sheet.DEFAULT_STYLE["en"])
        self.assertIn("第1格：站立。写实风格的棚拍照片，真人，自然的皮肤质感，柔和均匀的光线。每个格子", zh)
        self.assertIn("第1格：站立。flat anime cel shading。每个格子",
                      sheet.sheet_prompt(1, True, True, ["站立"], "zh", style="flat anime cel shading"))
        self.assertIn("standing. flat anime cel shading. Full body",
                      sheet.sheet_prompt(1, True, True, ["standing"], "en", style="flat anime cel shading"))

    def test_outfit_description_is_skipped_without_outfit(self):
        got = sheet.sheet_prompt(2, True, False, self.texts, "en", outfit_prompt="a blue trench coat")
        self.assertNotIn("blue trench coat", got)
        self.assertNotIn("garments", got)

    def test_chinese_all_four_combinations(self):
        head = "生成一张角色设定参考图：{who}，在<Picture {L}>的2个分格中依次出现2次，顺序为从左到右、从上到下。"
        mid = "每个格子中，人物的姿势和镜头角度须与<Picture {L}>对应格子里的人偶一致；人偶仅作姿势参考，不是外观参考。"
        dress = "每个格子里都让人物穿上<Picture {O}>中的完整服装，每件衣物的款式、颜色和材质都须与该图完全一致。"
        cases = {
            (True, True): (head.format(who="<Picture 1>中的人物", L=2) + mid.format(L=2) + dress.format(O=3) + TAIL_ZH),
            (True, False): (head.format(who="<Picture 1>中的人物", L=2) + mid.format(L=2) + TAIL_ZH),
            (False, True): (head.format(who="一位人物", L=1) + mid.format(L=1) + dress.format(O=2) + TAIL_ZH),
            (False, False): (head.format(who="一位人物", L=1) + mid.format(L=1) + TAIL_ZH),
        }
        zh_texts = ["站立", "坐下"]
        for (ch, out), want in cases.items():
            with self.subTest(character=ch, outfit=out):
                self.assertEqual(sheet.sheet_prompt(2, ch, out, zh_texts, "zh"), want)

    def test_chinese_single_panel_and_extras(self):
        got = sheet.sheet_prompt(1, True, True, ["站立"], "zh", character_prompt="短发", outfit_prompt="风衣")
        self.assertIn("出现一次，位于<Picture 2>的单个分格中。人物描述：短发。在这个格子中，", got)
        self.assertNotIn("从左到右", got)
        self.assertIn("人物描述：短发。", got)
        self.assertIn("须与该图完全一致。服装包含（颜色以<Picture 3>为准）：风衣。", got)
        self.assertIn("第1格：站立。", got)

    def test_validation(self):
        with self.assertRaises(ValueError):
            sheet.sheet_prompt(2, True, True, ["only one"], "en")
        with self.assertRaises(ValueError):
            sheet.sheet_prompt(0, True, True, [], "en")
        with self.assertRaises(ValueError):
            sheet.sheet_prompt(14, True, True, ["x"] * 14, "en")
        with self.assertRaises(ValueError):
            sheet.sheet_prompt(1, True, True, ["x"], "fr")


if __name__ == "__main__":
    unittest.main()
