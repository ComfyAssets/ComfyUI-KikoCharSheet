import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from charsheet import prompts  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"

POSE = {"姿势名称": "站立", "角度": "侧面", "分类": "站姿", "体系": "全身单人・基础"}
COSTUME = {"服装名称": "连衣裙", "分类": "春季穿搭", "标签": ["a", "b"]}
PORTRAIT = {"标题": "正脸", "分区": "正脸参考", "发长": "长发", "发型名称": "直发"}
UPLOAD = {"id": "upload:x.png", "source": "upload", "原图": "upload:x.png"}


def d(lib, item, lang, mirrored=False):
    return prompts.describe(lib, item, lang, mirrored, assets_dir=FIXTURE)


class DescribeTests(unittest.TestCase):
    def test_pose(self):
        self.assertEqual(d("pose", POSE, "en"), "侧面 view, pose: 站立 (Standing)")
        self.assertEqual(d("pose", POSE, "zh"), "侧面视角，动作：站立（全身单人・基础·站姿）")

    def test_pose_defaults(self):
        self.assertEqual(d("pose", {"分类": "站姿"}, "en"), "正面 view, pose: 标准姿势 (Standing)")
        self.assertEqual(d("pose", {}, "zh"), "正面视角，动作：标准姿势（·）")

    def test_costume(self):
        self.assertEqual(d("costume", COSTUME, "en"), "连衣裙")
        self.assertEqual(d("costume", COSTUME, "zh"), "身穿春季穿搭：连衣裙（细节：a、b）")
        self.assertEqual(d("costume", {"服装名称": "x", "关键词": "red dress, lace"}, "en"), "red dress, lace")
        self.assertEqual(d("costume", {"服装名称": "x", "分类": "c"}, "zh"), "身穿c：x")

    def test_costume_tags_capped_at_eight(self):
        tags = [str(i) for i in range(10)]
        self.assertIn("0、1、2、3、4、5、6、7）", d("costume", {"标签": tags}, "zh"))

    def test_portrait(self):
        self.assertEqual(d("portrait", PORTRAIT, "en"), "character hairstyle and face reference: 长发, 直发")
        self.assertEqual(d("portrait", PORTRAIT, "zh"), "人物面部与发型：长发、直发（正脸参考，正脸）")

    def test_uploads(self):
        want = {
            "portrait": ("the person in the uploaded portrait photo", "参考上传的人像照片"),
            "costume": ("the outfit in the uploaded costume photo", "参考上传的服装照片"),
            "pose": ("the pose in the uploaded pose photo", "参考上传的姿势照片"),
        }
        for lib, (en, zh) in want.items():
            self.assertEqual(d(lib, UPLOAD, "en"), en)
            self.assertEqual(d(lib, UPLOAD, "zh"), zh)

    def test_mirrored(self):
        self.assertEqual(d("pose", POSE, "en", True), "侧面 view, pose: 站立 (Standing) (mirrored)")
        self.assertEqual(d("pose", POSE, "zh", True), "侧面视角，动作：站立（全身单人・基础·站姿）（镜像）")
        self.assertEqual(d("pose", UPLOAD, "en", True), "the pose in the uploaded pose photo (mirrored)")

    def test_bad_args(self):
        with self.assertRaises(ValueError):
            d("nope", POSE, "en")
        with self.assertRaises(ValueError):
            d("pose", POSE, "fr")

    def test_missing_translation_map_is_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = prompts.describe("pose", POSE, "en", assets_dir=Path(tmp))
        self.assertEqual(out, "侧面 view, pose: 站立 (站姿)")

    def test_default_assets_dir_is_catalog_default(self):
        self.assertEqual(prompts.describe("pose", UPLOAD, "en"), "the pose in the uploaded pose photo")

    @unittest.skipUnless((REPO / "assets" / "locales" / "en" / "data.json").is_file(), "assets/ not set up")
    def test_real_translation_map_loads(self):
        td = prompts.make_translator(REPO / "assets")
        self.assertTrue(td("站姿"))



class FootwearTests(unittest.TestCase):
    def test_footwear_instruction_is_appended(self):
        self.assertEqual(
            prompts.with_footwear("knit top skirt sneakers.", True, "en"),
            "knit top skirt sneakers; include the footwear shown in the outfit picture, worn on both feet",
        )
        self.assertEqual(
            prompts.with_footwear("knit top", False, "en"), "knit top; leave out the footwear, the person wears no shoes"
        )
        self.assertEqual(prompts.with_footwear("针织衫。", True, "zh"), "针织衫；包含服装图中的鞋子，双脚都要穿上")
        self.assertEqual(prompts.with_footwear("针织衫", False, "zh"), "针织衫；不要鞋子，人物不穿鞋")

    def test_footwear_instruction_stands_alone_without_a_description(self):
        self.assertEqual(
            prompts.with_footwear("  ", True, "en"), "Include the footwear shown in the outfit picture, worn on both feet"
        )
        self.assertEqual(prompts.with_footwear(None, False, "zh"), "不要鞋子，人物不穿鞋")
        with self.assertRaises(ValueError):
            prompts.with_footwear("x", True, "fr")


if __name__ == "__main__":
    unittest.main()
