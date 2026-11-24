import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from charsheet import uploads  # noqa: E402


def make_image(path: Path, size=(4, 3), fmt="PNG"):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 10, 10)).save(path, fmt)


class ParseAndValidateTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(uploads.UPLOAD_PREFIX, "upload:")
        self.assertEqual(uploads.SUBFOLDER, "charsheet")
        self.assertEqual(uploads.LIBS, ("portrait", "costume", "pose"))
        self.assertEqual(uploads.ALLOWED_EXTS, (".png", ".jpg", ".jpeg", ".webp"))
        self.assertEqual(uploads.MAX_NAME_LENGTH, 200)

    def test_parse_upload_id_splits_on_first_colon_only(self):
        self.assertEqual(uploads.parse_upload_id("upload:我的 头像 (1).JPG"), "我的 头像 (1).JPG")
        self.assertEqual(uploads.parse_upload_id("upload:a:b.png"), "a:b.png")
        self.assertIsNone(uploads.parse_upload_id("f71f980dde3"))
        self.assertIsNone(uploads.parse_upload_id(None))

    def test_valid_names(self):
        for name in ("me.png", "我的 头像 (1).JPG", "x.webp", "a" * 195 + ".jpeg"):
            self.assertTrue(uploads.is_valid_upload_name(name), name)

    def test_invalid_names(self):
        for name in ("../a.png", "a/b.png", "a\\b.png", ".hidden.png", "a.gif",
                     "a\x00.png", "a\nb.png", "a\tb.png", "a\x7f.png",
                     "a" * 201 + ".png", "a" * 196 + ".jpeg", "", None, 5):
            self.assertFalse(uploads.is_valid_upload_name(name), repr(name))


class UploadFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.input_dir = Path(self._tmp.name) / "input"
        self.input_dir.mkdir()

    def folder(self, lib="pose"):
        return uploads.upload_dir(self.input_dir, lib)

    def test_upload_dir_uses_charsheet_subfolder(self):
        self.assertEqual(self.folder("costume"), self.input_dir / "charsheet" / "costume")

    def test_upload_dir_unknown_lib_raises(self):
        with self.assertRaises(ValueError):
            uploads.upload_dir(self.input_dir, "nope")

    def test_resolve_existing_file(self):
        make_image(self.folder() / "me.png")
        got = uploads.resolve_upload_path(self.input_dir, "pose", "me.png")
        self.assertEqual(got, (self.folder() / "me.png").resolve())

    def test_resolve_returns_none_for_bad_input(self):
        make_image(self.folder() / "me.png")
        self.assertIsNone(uploads.resolve_upload_path(self.input_dir, "pose", "gone.png"))
        self.assertIsNone(uploads.resolve_upload_path(self.input_dir, "pose", "../me.png"))
        self.assertIsNone(uploads.resolve_upload_path(self.input_dir, "bogus", "me.png"))

    def test_resolve_rejects_symlink_escaping_folder(self):
        outside = Path(self._tmp.name) / "secret.png"
        make_image(outside)
        self.folder().mkdir(parents=True, exist_ok=True)
        os.symlink(outside, self.folder() / "link.png")
        self.assertIsNone(uploads.resolve_upload_path(self.input_dir, "pose", "link.png"))

    def test_list_uploads_newest_first_with_sizes(self):
        make_image(self.folder() / "old.png", (4, 3))
        make_image(self.folder() / "new.jpg", (8, 6), "JPEG")
        os.utime(self.folder() / "old.png", (1000, 1000))
        os.utime(self.folder() / "new.jpg", (2000, 2000))
        (self.folder() / "notes.txt").write_text("hi")
        (self.folder() / "bad.png").write_bytes(b"not an image")
        items = uploads.list_uploads(self.input_dir, "pose")
        self.assertEqual([i["name"] for i in items], ["new.jpg", "old.png"])
        self.assertEqual((items[0]["width"], items[0]["height"]), (8, 6))
        self.assertEqual(items[0]["mtime"], 2000)

    def test_list_uploads_missing_folder(self):
        self.assertEqual(uploads.list_uploads(self.input_dir, "pose"), [])

    def test_delete_upload(self):
        make_image(self.folder() / "me.png")
        self.assertTrue(uploads.delete_upload(self.input_dir, "pose", "me.png"))
        self.assertFalse((self.folder() / "me.png").exists())
        self.assertFalse(uploads.delete_upload(self.input_dir, "pose", "me.png"))

    def test_delete_rejects_traversal(self):
        victim = self.input_dir / "x.png"
        make_image(victim)
        self.assertFalse(uploads.delete_upload(self.input_dir, "pose", "../x.png"))
        self.assertTrue(victim.exists())

    def test_input_dir_is_a_callable(self):
        self.assertTrue(callable(uploads.input_dir))


if __name__ == "__main__":
    unittest.main()
