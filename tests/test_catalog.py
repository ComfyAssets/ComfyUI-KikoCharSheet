import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from charsheet.catalog import (  # noqa: E402
    ASSETS_DIR,
    LIBS,
    AssetsMissingError,
    Catalog,
    default_catalog,
    is_nsfw,
    select_costume_view,
)

FIXTURE = REPO / "tests" / "fixtures" / "assets"


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog(FIXTURE)

    def test_constants(self):
        self.assertEqual(LIBS, ("portrait", "costume", "pose"))
        self.assertEqual(ASSETS_DIR, REPO / "assets")

    def test_items_counts(self):
        self.assertEqual(len(self.cat.items("pose")), 2)
        self.assertEqual(len(self.cat.items("portrait")), 2)
        self.assertEqual(len(self.cat.items("costume")), 5)

    def test_costume_merge_order(self):
        ids = [c["id"] for c in self.cat.items("costume")]
        self.assertEqual(ids, ["SPR-0001", "LNG-0001", "shisei-C001", "charadb-1", "gia-anime-1"])

    def test_items_cached_per_instance(self):
        self.assertIs(self.cat.items("pose"), self.cat.items("pose"))

    def test_unknown_lib(self):
        with self.assertRaises(ValueError):
            self.cat.items("nope")

    def test_find_known(self):
        self.assertEqual(self.cat.find("pose", " pose-safe ")["id"], "pose-safe")

    def test_find_unknown_names_id(self):
        with self.assertRaises(ValueError) as cm:
            self.cat.find("pose", "nope")
        self.assertEqual(str(cm.exception), "unknown pose id: nope")

    def test_find_unknown_external_prefix(self):
        for prefix in ("charadb-", "gia-anime-", "shisei-"):
            with self.assertRaises(ValueError) as cm:
                self.cat.find("costume", prefix + "zzz")
            self.assertEqual(str(cm.exception), f"unknown external-source costume id: {prefix}zzz")

    def test_pose_path_reads_the_poses_folder_next_to_assets(self):
        self.assertEqual(self.cat.poses_dir, FIXTURE.parent / "poses")
        self.assertTrue(self.cat.pose_path("img/grey/pose/pose-safe.webp").is_file())
        self.assertTrue(self.cat.pose_path("thumbs/grey/pose/pose-safe.webp").is_file())
        with self.assertRaises(FileNotFoundError):
            self.cat.pose_path("img/costume/SPR-0001.png")  # an assets file is not a pose render
        for rel in ("../assets/img/costume/SPR-0001.png", "img/../../x", "README.md", "/etc/passwd"):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                self.cat.pose_path(rel)

    def test_poses_dir_can_be_given(self):
        self.assertEqual(Catalog(FIXTURE, poses_dir=FIXTURE).poses_dir, FIXTURE)

    def test_image_path_ok(self):
        p = self.cat.image_path("img/costume/SPR-0001.png")
        self.assertTrue(p.is_file())
        self.assertTrue(self.cat.image_path("thumbs/costume/SPR-0001.png").is_file())

    def test_image_path_traversal(self):
        for rel in ("../x", "img/../../x", "data/pose-zh.json", "/etc/passwd"):
            with self.assertRaises(ValueError, msg=rel):
                self.cat.image_path(rel)

    def test_image_path_missing(self):
        with self.assertRaises(FileNotFoundError):
            self.cat.image_path("img/pose/absent.png")

    def test_image_path_with_symlinked_img_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            os.symlink(FIXTURE / "img", assets / "img")
            os.symlink(FIXTURE / "thumbs", assets / "thumbs")
            cat = Catalog(assets)
            self.assertTrue(cat.image_path("img/costume/SPR-0001.png").is_file())
            self.assertTrue(cat.image_path("thumbs/costume/SPR-0001.png").is_file())
            with self.assertRaises(ValueError):
                cat.image_path("img/../../etc/passwd")

    def test_missing_assets_dir(self):
        cat = Catalog(Path("/nonexistent/assets"))  # lazy: construction is fine
        with self.assertRaises(AssetsMissingError) as cm:
            cat.items("pose")
        self.assertIn("setup_assets.py", str(cm.exception))
        self.assertIsInstance(cm.exception, RuntimeError)

    def test_select_costume_view_front_fallback_to_first(self):
        item = self.cat.find("costume", "shisei-C001")
        out = select_costume_view(item, "front")
        self.assertEqual(out["selectedView"], "front")
        self.assertTrue(out["原图"].endswith("front.png"))

    def test_select_costume_view_back_and_missing(self):
        item = self.cat.find("costume", "shisei-C001")
        self.assertEqual(select_costume_view(item, "back")["selectedView"], "back")
        with self.assertRaises(ValueError):
            select_costume_view(item, "side")

    def test_select_costume_view_front_falls_back_when_no_front(self):
        item = {"id": "x", "views": [{"id": "back", "缩略图": "a", "预览图": "b", "原图": "c"}]}
        self.assertEqual(select_costume_view(item, "front")["selectedView"], "back")

    def test_select_costume_view_no_views_and_upload(self):
        plain = self.cat.find("costume", "SPR-0001")
        self.assertIs(select_costume_view(plain, "front"), plain)
        up = {"id": "upload:a.png", "source": "upload", "views": [{"id": "front"}]}
        self.assertIs(select_costume_view(up, "front"), up)

    def test_select_costume_view_non_front_on_single_view_costume(self):
        plain = self.cat.find("costume", "SPR-0001")
        for view in ("back", "side"):
            with self.assertRaises(ValueError) as cm:
                select_costume_view(plain, view)
            self.assertEqual(str(cm.exception), f"costume SPR-0001 has no {view} view")

    def test_select_costume_view_error_names_item(self):
        item = self.cat.find("costume", "shisei-C001")
        with self.assertRaises(ValueError) as cm:
            select_costume_view(item, "side")
        self.assertEqual(str(cm.exception), "costume shisei-C001 has no side view")

    def test_is_nsfw(self):
        pose = {p["id"]: p for p in self.cat.items("pose")}
        self.assertFalse(is_nsfw("pose", pose["pose-safe"]))
        self.assertTrue(is_nsfw("pose", pose["pose-nsfw"]))
        cos = {c["id"]: c for c in self.cat.items("costume")}
        self.assertFalse(is_nsfw("costume", cos["SPR-0001"]))
        self.assertTrue(is_nsfw("costume", cos["LNG-0001"]))  # category
        self.assertTrue(is_nsfw("costume", cos["charadb-1"]))  # 敏感 flag
        self.assertFalse(is_nsfw("portrait", self.cat.items("portrait")[0]))

    def test_default_catalog_cached(self):
        self.assertIs(default_catalog(), default_catalog())


if __name__ == "__main__":
    unittest.main()
