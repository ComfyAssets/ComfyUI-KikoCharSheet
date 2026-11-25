import io
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from charsheet import images, uploads  # noqa: E402
from charsheet.catalog import Catalog  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"
POSES_FIXTURE = REPO / "tests" / "fixtures" / "poses"
CHARADB_URL = "https://example.invalid/o.jpg"
GIA_URL = "https://example.invalid/o2.jpg"


def lr_image(width=40, height=20):
    """Left half red, right half blue."""
    img = Image.new("RGB", (width, height), (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, width // 2, height))
    return img


def encode(img, fmt):
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


class FakeResponse:
    def __init__(self, body, content_type="image/jpeg", status=200, length=None):
        self._body = body
        self.status = status
        self.headers = mock.Mock()
        self.headers.get_content_type.return_value = content_type
        self.headers.get.side_effect = lambda k, d=None: str(len(body) if length is None else length) if k == "Content-Length" else d

    def read(self, n=-1):
        return self._body[:n] if n >= 0 else self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def open(self, request, timeout=None):
        self.calls.append(request.full_url)
        if self.error:
            raise self.error
        return self.response


class UploadEnvTestCase(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog(FIXTURE)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.input_dir = Path(tmp.name)
        patcher = mock.patch.object(uploads, "input_dir", lambda: self.input_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, lib, name, data: bytes):
        path = uploads.upload_dir(self.input_dir, lib) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class ResolveItemTests(UploadEnvTestCase):
    def test_gallery_item(self):
        self.assertEqual(images.resolve_item(self.cat, "pose", "pose-safe")["id"], "pose-safe")

    def test_unknown_id_names_id(self):
        with self.assertRaises(ValueError) as cm:
            images.resolve_item(self.cat, "pose", "nope")
        self.assertIn("nope", str(cm.exception))

    def test_costume_view_applied(self):
        item = images.resolve_item(self.cat, "costume", "shisei-C001", "back")
        self.assertEqual(item["selectedView"], "back")
        self.assertEqual(item["原图"], "img/costume/shisei-C001-back.png")

    def test_missing_upload_names_id(self):
        with self.assertRaises(ValueError) as cm:
            images.resolve_item(self.cat, "pose", "upload:gone.png")
        self.assertEqual(str(cm.exception), "uploaded image not found: upload:gone.png")

    def test_existing_upload_is_synthetic_item(self):
        self.put("pose", "me.png", encode(lr_image(), "PNG"))
        self.assertEqual(
            images.resolve_item(self.cat, "pose", "upload:me.png"),
            {"id": "upload:me.png", "source": "upload", "原图": "upload:me.png"},
        )


class PoseRelPathTests(unittest.TestCase):
    def test_grey_is_the_default_and_has_one_candidate(self):
        rel = "/img/pose/a/b.png"
        self.assertEqual(images.pose_style_rels(rel), ["img/grey/pose/a/b.webp"])
        self.assertEqual(images.pose_style_rels(rel, "grey"), ["img/grey/pose/a/b.webp"])
        self.assertEqual(images.pose_style_rels("img/full_P001_front.png", "grey"), ["img/grey/full_P001_front.webp"])

    def test_wide_falls_back_to_grey(self):
        self.assertEqual(
            images.pose_style_rels("img/pose/a/b.png", "grey_wide"),
            ["img/grey_wide/pose/a/b.webp", "img/grey/pose/a/b.webp"],
        )

    def test_thumbs_are_webp(self):
        self.assertEqual(
            images.pose_style_rels("thumbs/pose/a.jpg", "grey_wide"),
            ["thumbs/grey_wide/pose/a.webp", "thumbs/grey/pose/a.webp"],
        )

    def test_a_path_already_in_a_render_set_is_kept(self):
        self.assertEqual(images.pose_style_rels("img/grey/x.webp", "grey"), ["img/grey/x.webp"])

    def test_styles_from_before_the_grey_renders_mean_grey(self):
        for old in (None, "", "line", "depth"):
            with self.subTest(old=old):
                self.assertEqual(images.normalize_pose_style(old), "grey")
        self.assertEqual(images.normalize_pose_style("grey_wide"), "grey_wide")

    def test_unknown_style_is_rejected(self):
        for bad in ("clay", 3, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                images.normalize_pose_style(bad)
        with self.assertRaises(ValueError):
            images.pose_style_rels("img/a.png", "clay")


class PoseStyleFilesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assets = Path(tmp.name) / "assets"
        shutil.copytree(FIXTURE, self.assets)
        self.poses = Path(tmp.name) / "poses"
        shutil.copytree(POSES_FIXTURE, self.poses)
        self.cat = Catalog(self.assets)
        self.item = self.cat.find("pose", "pose-safe")

    def put(self, rel, size, base=None):
        path = (base or self.poses) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, (128, 128, 128)).save(path)

    def size(self, style):
        with images.open_item_image(self.cat, "pose", self.item, style=style) as image:
            return image.size

    def test_wide_uses_its_own_file_else_the_grey_one(self):
        self.put("img/grey/pose/pose-safe.webp", (11, 12))
        self.assertEqual(self.size("grey_wide"), (11, 12))
        self.put("img/grey_wide/pose/pose-safe.webp", (21, 22))
        self.assertEqual(self.size("grey_wide"), (21, 22))
        self.assertEqual(self.size("grey"), (11, 12))
        self.assertEqual(self.size(None), (11, 12))

    def test_a_pose_without_a_grey_render_is_an_error(self):
        (self.poses / "img/grey/pose/pose-safe.webp").unlink()
        self.put("img/pose/pose-safe.png", (5, 5), self.assets)  # a gallery line drawing is never used
        self.put("img/grey/pose/pose-safe.webp", (5, 5), self.assets)  # nor anything under assets/
        for style in ("grey", "grey_wide"):
            with self.subTest(style=style), self.assertRaises(FileNotFoundError):
                self.size(style)

    def test_has_pose_render_does_not_count_fallbacks(self):
        self.assertTrue(images.has_pose_render(self.cat, self.item))
        self.assertFalse(images.has_pose_render(self.cat, self.item, "grey_wide"))
        self.put("img/grey_wide/pose/pose-safe.webp", (4, 4))
        self.assertTrue(images.has_pose_render(self.cat, self.item, "grey_wide"))


class OpenItemImageTests(UploadEnvTestCase):
    def test_local_file(self):
        item = self.cat.find("pose", "pose-safe")
        with images.open_item_image(self.cat, "pose", item) as img:
            self.assertGreater(img.width, 0)

    def test_upload(self):
        self.put("portrait", "me.png", encode(lr_image(), "PNG"))
        item = images.resolve_item(self.cat, "portrait", "upload:me.png")
        self.assertEqual(images.open_item_image(self.cat, "portrait", item).size, (40, 20))

    def test_corrupt_upload_names_id(self):
        self.put("portrait", "bad.png", b"not an image")
        item = images.resolve_item(self.cat, "portrait", "upload:bad.png")
        with self.assertRaises(ValueError) as cm:
            images.open_item_image(self.cat, "portrait", item)
        self.assertIn("upload:bad.png", str(cm.exception))

    def test_oversize_upload_names_id(self):
        self.put("portrait", "big.png", encode(lr_image(), "PNG"))
        item = images.resolve_item(self.cat, "portrait", "upload:big.png")
        with mock.patch.object(images, "MAX_UPLOAD_PIXELS", 100):
            with self.assertRaises(ValueError) as cm:
                images.open_item_image(self.cat, "portrait", item)
        self.assertIn("upload:big.png", str(cm.exception))
        self.assertIn("too large", str(cm.exception))


class RemoteFetchTests(UploadEnvTestCase):
    def open_remote(self, opener, cid="charadb-1"):
        item = self.cat.find("costume", cid)
        return images.open_item_image(self.cat, "costume", item, opener=opener)

    def test_fetches_allowlisted_url(self):
        opener = FakeOpener(FakeResponse(encode(lr_image(), "JPEG")))
        self.assertEqual(self.open_remote(opener).size, (40, 20))
        self.assertEqual(opener.calls, [CHARADB_URL])

    def test_url_not_in_allowlist_rejected_without_network(self):
        opener = FakeOpener(FakeResponse(b""))
        item = {"id": "evil", "原图": "https://evil.invalid/x.jpg"}
        with self.assertRaises(ValueError) as cm:
            images.open_item_image(self.cat, "costume", item, opener=opener)
        self.assertIn("evil", str(cm.exception))
        self.assertEqual(opener.calls, [])

    def test_default_opener_not_built_for_disallowed_url(self):
        with mock.patch("urllib.request.build_opener", side_effect=AssertionError("network")):
            with self.assertRaises(ValueError):
                images.open_item_image(self.cat, "costume", {"id": "x", "原图": "https://evil.invalid/x.png"})

    def test_wrong_content_type(self):
        opener = FakeOpener(FakeResponse(encode(lr_image(), "JPEG"), content_type="text/html"))
        with self.assertRaises(ValueError):
            self.open_remote(opener)

    def test_wrong_image_format(self):
        opener = FakeOpener(FakeResponse(encode(lr_image(), "PNG")))  # charadb must be JPEG
        with self.assertRaises(ValueError):
            self.open_remote(opener)

    def test_too_large_by_header_and_body(self):
        with self.assertRaises(ValueError):
            self.open_remote(FakeOpener(FakeResponse(b"x", length=images.REMOTE_LIMIT_BYTES + 1)))
        with mock.patch.object(images, "REMOTE_LIMIT_BYTES", 10):
            with self.assertRaises(ValueError):
                self.open_remote(FakeOpener(FakeResponse(b"x" * 50, length=1)))

    def test_too_many_pixels(self):
        opener = FakeOpener(FakeResponse(encode(lr_image(), "JPEG")))
        with mock.patch.object(images, "MAX_REMOTE_PIXELS", 10):
            with self.assertRaises(ValueError):
                self.open_remote(opener)

    def test_offline_names_item_and_internet(self):
        opener = FakeOpener(error=urllib.error.URLError("no route"))
        with self.assertRaises(ValueError) as cm:
            self.open_remote(opener)
        msg = str(cm.exception)
        self.assertIn("charadb-1", msg)
        self.assertIn("internet", msg)

    def test_redirect_handler_refuses(self):
        with self.assertRaises(ValueError):
            images._NoRedirect().redirect_request(None, None, 302, "", {}, "https://x.invalid")


class FitTests(unittest.TestCase):
    def test_original_ignores_size(self):
        self.assertEqual(images.fit(lr_image(), "original", 10, 10).size, (40, 20))

    def test_crop_and_pad_exact_sizes(self):
        for mode in ("crop to size", "pad to size"):
            for size in ((64, 80), (100, 30), (20, 20)):
                self.assertEqual(images.fit(lr_image(), mode, *size).size, size, (mode, size))

    def test_pad_uses_white(self):
        out = images.fit(lr_image(40, 20), "pad to size", 40, 40)
        self.assertEqual(out.getpixel((20, 0)), (255, 255, 255))
        self.assertEqual(out.getpixel((20, 39)), (255, 255, 255))

    def test_flip_mirrors_left_right(self):
        plain = images.fit(lr_image(), "original", 0, 0)
        flipped = images.fit(lr_image(), "original", 0, 0, flip=True)
        self.assertEqual(plain.getpixel((2, 10)), (255, 0, 0))
        self.assertEqual(flipped.getpixel((2, 10)), (0, 0, 255))
        self.assertEqual(flipped.getpixel((37, 10)), (255, 0, 0))

    def test_flip_with_crop(self):
        out = images.fit(lr_image(), "crop to size", 20, 20, flip=True)
        self.assertEqual(out.getpixel((1, 10)), (0, 0, 255))

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            images.fit(lr_image(), "stretch", 10, 10)


class TensorTests(unittest.TestCase):
    def test_shape_and_range(self):
        t = images.to_tensor(lr_image(40, 20))
        self.assertEqual(tuple(t.shape), (1, 20, 40, 3))
        self.assertEqual(str(t.dtype), "torch.float32")
        self.assertEqual(float(t.min()), 0.0)
        self.assertEqual(float(t.max()), 1.0)

    def test_blank_is_white(self):
        img = images.blank(30, 50)
        self.assertEqual(img.size, (30, 50))
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(float(images.to_tensor(img).min()), 1.0)


if __name__ == "__main__":
    unittest.main()
