import base64
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from charsheet import routes, uploads  # noqa: E402
from charsheet.catalog import AssetsMissingError, Catalog  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.assets = self.root / "assets"
        shutil.copytree(FIXTURE, self.assets)
        self.poses = self.root / "poses"
        shutil.copytree(FIXTURE.parent / "poses", self.poses)
        self.input_dir = self.root / "input"
        self.input_dir.mkdir()
        self.cat = Catalog(self.assets)
        for target, value in (
            ("charsheet.catalog.default_catalog", lambda: self.cat),
            ("charsheet.uploads.input_dir", lambda: self.input_dir),
        ):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_wide_falls_back_to_grey_and_unknown_style_is_400(self):
        grey = (self.poses / "thumbs/grey/pose/pose-safe.webp").resolve()
        for style in (None, "grey", "grey_wide", "line", "depth"):
            with self.subTest(style=style):
                self.assertEqual(routes.resolve_media("pose", "pose-safe", "thumb", style=style), (200, grey))
        wide = self.poses / "img/grey_wide/pose/pose-safe.webp"
        wide.parent.mkdir(parents=True)
        Image.new("RGB", (4, 4)).save(wide)
        self.assertEqual(routes.resolve_media("pose", "pose-safe", "image", style="grey_wide")[1], wide.resolve())
        self.assertEqual(
            routes.resolve_media("pose", "pose-safe", "image")[1], (self.poses / "img/grey/pose/pose-safe.webp").resolve())
        self.assertEqual(routes.resolve_media("pose", "pose-safe", "image", style="clay")[0], 400)

    def put_upload(self, lib, name):
        path = uploads.upload_dir(self.input_dir, lib) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (30, 20)).save(path)


class CatalogTests(RouteTestCase):
    def items(self, lib):
        status, payload = routes.handle_catalog(lib)
        self.assertEqual(status, 200)
        return {item["id"]: item for item in payload}

    def test_unknown_lib(self):
        status, payload = routes.handle_catalog("bogus")
        self.assertEqual(status, 400)
        self.assertIn("bogus", payload["error"])

    def test_portrait_shape(self):
        item = self.items("portrait")["por-a"]
        self.assertEqual(
            item,
            {"id": "por-a", "title": "por-a", "thumb": "/charsheet/thumb/portrait/por-a", "nsfw": False,
             "online": False, "发长": "", "分区": "正脸参考", "search": ""},
        )

    def test_pose_shape_and_nsfw(self):
        items = self.items("pose")
        self.assertEqual(set(items["pose-safe"]), {
            "id", "title", "thumb", "nsfw", "online", "体系", "分类", "角度", "姿势名称", "search", "wide"})
        self.assertFalse(items["pose-safe"]["wide"])
        self.assertEqual(items["pose-safe"]["thumb"], "/charsheet/thumb/pose/pose-safe?style=grey")
        path = self.poses / "img/grey_wide/pose/pose-safe.webp"
        path.parent.mkdir(parents=True)
        Image.new("RGB", (4, 4)).save(path)
        self.assertTrue(self.items("pose")["pose-safe"]["wide"])
        self.assertFalse(self.items("pose")["pose-nsfw"]["wide"])
        self.assertFalse(items["pose-safe"]["nsfw"])
        self.assertTrue(items["pose-nsfw"]["nsfw"])

    def test_poses_without_a_grey_render_are_left_out(self):
        (self.poses / "img/grey/pose/pose-nsfw.webp").unlink()
        self.assertEqual(set(self.items("pose")), {"pose-safe"})

    def test_costume_local_online_and_views(self):
        items = self.items("costume")
        local = items["SPR-0001"]
        self.assertEqual(local["thumb"], "/charsheet/thumb/costume/SPR-0001")
        self.assertEqual((local["source"], local["一级分类"], local["online"], local["views"]), ("gia", "现实", False, []))
        self.assertTrue(items["LNG-0001"]["nsfw"])
        self.assertEqual(items["shisei-C001"]["views"], ["front", "back"])
        self.assertEqual(items["shisei-C001"]["source"], "shisei")
        online = items["charadb-1"]
        self.assertEqual(online["thumb"], "https://example.invalid/t.jpg")
        self.assertTrue(online["online"] and online["nsfw"])

    def test_anime_default_primary_category(self):
        items = self.items("costume")
        self.assertEqual(items["charadb-1"]["一级分类"], "二次元")
        self.assertEqual(items["gia-anime-1"]["一级分类"], "二次元")

    def test_missing_assets(self):
        self.cat = Catalog(self.root / "nowhere")
        status, payload = routes.handle_catalog("pose")
        self.assertEqual(status, 503)
        self.assertIn("setup_assets.py", payload["error"])


class MediaTests(RouteTestCase):
    def test_thumb_and_image(self):
        status, path = routes.resolve_media("pose", "pose-safe", "thumb")
        self.assertEqual((status, path), (200, (self.poses / "thumbs/grey/pose/pose-safe.webp").resolve()))
        status, path = routes.resolve_media("portrait", "por-a", "image")
        self.assertEqual((status, path), (200, (self.assets / "img/portrait/por-a.png").resolve()))

    def test_unknown_id_and_lib_and_kind(self):
        self.assertEqual(routes.resolve_media("pose", "ghost", "thumb")[0], 404)
        self.assertEqual(routes.resolve_media("bogus", "x", "thumb")[0], 404)
        self.assertEqual(routes.resolve_media("pose", "pose-safe", "huge")[0], 400)

    def test_uploads_are_not_served(self):
        self.put_upload("pose", "me.png")
        status, payload = routes.resolve_media("pose", "upload:me.png", "thumb")
        self.assertEqual(status, 404)
        self.assertIn("/view", payload["error"])

    def test_online_costume_is_404(self):
        self.assertEqual(routes.resolve_media("costume", "charadb-1", "thumb")[0], 404)
        self.assertEqual(routes.resolve_media("costume", "gia-anime-1", "image")[0], 404)

    def test_single_view_costume_rejects_other_views(self):
        self.assertEqual(routes.resolve_media("costume", "SPR-0001", "thumb", view="back")[0], 404)
        self.assertEqual(routes.resolve_media("costume", "SPR-0001", "thumb", view="front")[0], 200)

    def test_costume_view(self):
        status, path = routes.resolve_media("costume", "shisei-C001", "thumb", view="back")
        self.assertEqual((status, path.name), (200, "shisei-C001-back.png"))
        self.assertEqual(routes.resolve_media("costume", "shisei-C001", "thumb", view="top")[0], 404)

    def test_media_content_type(self):
        cases = {
            "a.webp": "image/webp",
            "a.WEBP": "image/webp",
            "a.png": "image/png",
            "a.jpg": "image/jpeg",
            "a.jpeg": "image/jpeg",
            "a.gif": "application/octet-stream",
            "noext": "application/octet-stream",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(routes.media_content_type(Path("/x") / name), expected)


class UploadRouteTests(RouteTestCase):
    def test_list(self):
        self.put_upload("pose", "a.png")
        status, payload = routes.handle_uploads_list("pose")
        self.assertEqual(status, 200)
        self.assertEqual([i["name"] for i in payload["items"]], ["a.png"])
        self.assertEqual(routes.handle_uploads_list("bogus")[0], 400)

    def test_delete(self):
        self.put_upload("pose", "a.png")
        self.assertEqual(routes.handle_upload_delete("pose", "a.png"), (200, {"deleted": True}))
        self.assertEqual(routes.handle_upload_delete("pose", "a.png")[0], 404)
        self.assertEqual(routes.handle_upload_delete("bogus", "a.png")[0], 400)
        self.assertEqual(routes.handle_upload_delete("pose", "../a.png")[0], 400)
        self.assertEqual(routes.handle_upload_delete("pose", "a.txt")[0], 400)


class PreviewTests(RouteTestCase):
    def preview(self, **body):
        body.setdefault("ids", ["pose-safe", "pose-nsfw"])
        return routes.handle_sheet_preview(body)

    def test_success(self):
        status, payload = self.preview(state={"size_mode": "manual", "width": 1536, "height": 1024})
        self.assertEqual(status, 200)
        self.assertEqual((payload["width"], payload["height"]), (1536, 1024))
        self.assertEqual(payload["megapixels"], 1.57)
        self.assertEqual(payload["warnings"], [])
        prefix = "data:image/png;base64,"
        self.assertTrue(payload["image"].startswith(prefix))
        img = Image.open(io.BytesIO(base64.b64decode(payload["image"][len(prefix):])))
        self.assertEqual(img.size, (768, 512))

    def test_default_state_uses_auto_size(self):
        status, payload = self.preview()
        self.assertEqual(status, 200)
        self.assertGreater(payload["width"] * payload["height"], 3_000_000)
        img = Image.open(io.BytesIO(base64.b64decode(payload["image"].split(",", 1)[1])))
        self.assertEqual(max(img.size), 768)

    def test_warning_from_full_size_plan(self):
        status, payload = self.preview(state={"size_mode": "manual", "width": 256, "height": 256})
        self.assertEqual(status, 200)
        self.assertTrue(payload["warnings"])

    def test_flip_and_style_accepted(self):
        self.assertEqual(self.preview(flip=["pose-safe"], use_depth=False)[0], 200)
        self.assertEqual(self.preview(style="grey_wide")[0], 200)
        self.assertEqual(self.preview(style="clay")[0], 400)

    def test_bad_requests(self):
        for body in (
            {"ids": []}, {"ids": "a"}, {"ids": [1]}, {"ids": [f"p{i}" for i in range(14)]},
            {"ids": ["pose-safe"], "flip": "x"}, {"ids": ["pose-safe"], "style": "clay"},
            {"ids": ["pose-safe"], "state": {"columns": 9}}, {"ids": ["ghost"]},
        ):
            with self.subTest(body=body):
                status, payload = routes.handle_sheet_preview(body)
                self.assertEqual(status, 400)
                self.assertIn("error", payload)
        self.assertEqual(routes.handle_sheet_preview("nope")[0], 400)

    def test_missing_assets(self):
        self.cat = Catalog(self.root / "nowhere")
        status, payload = self.preview()
        self.assertEqual(status, 503)
        self.assertIn("setup_assets.py", payload["error"])


class LocaleTests(RouteTestCase):
    def setUp(self):
        super().setUp()
        self.web = self.root / "web" / "locales"
        self.web.mkdir(parents=True)
        self.data_map = self.root / "data.json"
        for target, name, value in ((routes, "LOCALES_DIR", self.web), (routes.prompts_module, "DATA_MAP", self.data_map)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_en_includes_data_map(self):
        (self.web / "en.json").write_text('{"hello": "Hello"}', encoding="utf-8")
        self.data_map.write_text('{"站姿": "Standing"}', encoding="utf-8")
        self.assertEqual(
            routes.handle_locales("en"), (200, {"strings": {"hello": "Hello"}, "data": {"站姿": "Standing"}}))

    def test_zh_has_no_data_and_missing_file_is_empty(self):
        self.assertEqual(routes.handle_locales("zh"), (200, {"strings": {}, "data": {}}))

    def test_unsupported_lang(self):
        self.assertEqual(routes.handle_locales("fr")[0], 404)
        self.assertEqual(routes.handle_locales("../x")[0], 404)

    def test_missing_data_file_is_empty(self):
        self.assertEqual(routes.handle_locales("en"), (200, {"strings": {}, "data": {}}))


class RegisterTests(unittest.TestCase):
    def test_noop_outside_comfyui(self):
        self.assertIsNone(routes.register_routes())


if __name__ == "__main__":
    unittest.main()


class BuiltinCostumeRouteTests(RouteTestCase):
    def test_catalogue_row(self):
        status, payload = routes.handle_catalog("costume")
        self.assertEqual((status, payload[0]["id"]), (200, "nude"))
        nude = payload[0]
        self.assertEqual(nude["thumb"], "/charsheet/thumb/costume/nude")
        self.assertEqual((nude["source"], nude["title"], nude["分类"]), ("builtin", "裸体", "仅提示词"))
        self.assertTrue(nude["nsfw"])
        self.assertFalse(nude["online"])
        self.assertEqual(nude["views"], [])

    def test_thumb_and_image_are_the_icon(self):
        for kind in ("thumb", "image"):
            status, path = routes.resolve_media("costume", "nude", kind)
            self.assertEqual((status, path.name), (200, "nude.png"))
        self.assertEqual(routes.resolve_media("costume", "nude", "thumb", view="back")[0], 404)
