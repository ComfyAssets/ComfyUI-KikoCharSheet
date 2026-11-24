import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import setup_assets  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"


def make_source(root: Path) -> Path:
    src = root / "fork"
    (src / "data").mkdir(parents=True)
    (src / "data" / "pose-zh.json").write_text("[]", encoding="utf-8")
    (src / "img").mkdir()
    (src / "img" / "a.png").write_bytes(b"x")
    (src / "thumbs").mkdir()
    (src / "thumbs" / "a.png").write_bytes(b"x")
    (src / "locales" / "en").mkdir(parents=True)
    (src / "locales" / "en" / "data.json").write_text(json.dumps({"a": "b"}), encoding="utf-8")
    return src


class SetupAssetsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.src = make_source(self.tmp)
        self.dest = self.tmp / "assets"

    def tearDown(self):
        self._tmp.cleanup()

    def test_copy(self):
        res = setup_assets.setup(self.src, self.dest, force=False)
        self.assertTrue((self.dest / "data" / "pose-zh.json").is_file())
        self.assertFalse((self.dest / "img").is_symlink())
        self.assertTrue((self.dest / "img" / "a.png").is_file())
        self.assertTrue((self.dest / "thumbs" / "a.png").is_file())
        self.assertEqual(
            json.loads((self.dest / "locales" / "en" / "data.json").read_text(encoding="utf-8")), {"a": "b"}
        )
        self.assertEqual(res["mode"], "copy")

    def test_refuses_without_force(self):
        setup_assets.setup(self.src, self.dest, force=False)
        with self.assertRaises(FileExistsError):
            setup_assets.setup(self.src, self.dest, force=False)

    def test_force_overwrites(self):
        setup_assets.setup(self.src, self.dest, force=False)
        (self.dest / "img" / "stale.png").write_bytes(b"s")
        setup_assets.setup(self.src, self.dest, force=True)
        self.assertFalse((self.dest / "img" / "stale.png").exists())
        self.assertTrue((self.dest / "img" / "a.png").is_file())

    def test_missing_source(self):
        with self.assertRaises(setup_assets.SourceMissingError) as cm:
            setup_assets.setup(self.tmp / "nope", self.dest, force=False)
        self.assertIn("images come with the clone", str(cm.exception))
        self.assertNotIn("download.py", str(cm.exception))

    def test_original_size_downloads_are_left_out(self):
        # What scripts/download.py adds to a fork clone: full-size files next to the WebP copies.
        kept = ["img/costume/a.webp", "img/portrait/p.webp", "img/depth/d.webp", "thumbs/depth/d.webp",
                "img/costumes/shisei/c.png", "thumbs/costume/t.jpg"]
        left_out = ["img/costume/a.png", "img/portrait/p.PNG", "img/depth/d.png", "thumbs/depth/d.jpg"]
        for rel in kept + left_out:
            path = self.src / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
        res = setup_assets.setup(self.src, self.dest, force=False)
        for rel in kept + ["img/a.png", "thumbs/a.png"]:
            self.assertTrue((self.dest / rel).is_file(), rel)
        for rel in left_out:
            self.assertFalse((self.dest / rel).exists(), rel)
        self.assertEqual(res["skipped_originals"], 4)

    def test_plain_clone_reports_nothing_left_out(self):
        self.assertEqual(setup_assets.setup(self.src, self.dest, force=False)["skipped_originals"], 0)

    def test_cli_missing_source_exit_2(self):
        code = setup_assets.main(["--from", str(self.tmp / "nope"), "--dest", str(self.dest)])
        self.assertEqual(code, 2)

    def test_cli_copy(self):
        code = setup_assets.main(["--from", str(self.src), "--dest", str(self.dest)])
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "data").is_dir())


if __name__ == "__main__":
    unittest.main()
