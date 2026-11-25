import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from PIL import Image  # noqa: E402

import add_pose_set  # noqa: E402


class AddPoseSetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.src = self.root / "renders"
        self.src.mkdir()
        for name in ("full_P001_front.png", "full_P001_side.PNG"):
            Image.new("RGB", (900, 1200), (128, 128, 128)).save(self.src / name, "PNG")
        (self.src / "notes.txt").write_text("not an image", encoding="utf-8")
        self.dest = self.root / "poses"

    def test_writes_webp_renders_and_small_thumbs(self):
        result = add_pose_set.add_pose_set(self.src, self.dest, "grey")
        self.assertEqual(result, {"style": "grey", "images": 2})
        self.assertEqual(
            sorted(p.name for p in (self.dest / "img" / "grey").iterdir()),
            ["full_P001_front.webp", "full_P001_side.webp"],
        )
        with Image.open(self.dest / "img" / "grey" / "full_P001_side.webp") as render:
            self.assertEqual((render.format, render.size), ("WEBP", (900, 1200)))
        with Image.open(self.dest / "thumbs" / "grey" / "full_P001_side.webp") as thumb:
            self.assertEqual((thumb.format, thumb.size), ("WEBP", (300, 400)))

    def test_second_run_replaces_files(self):
        add_pose_set.add_pose_set(self.src, self.dest, "grey_wide")
        Image.new("RGB", (90, 120)).save(self.src / "full_P001_front.png")
        add_pose_set.add_pose_set(self.src, self.dest, "grey_wide")
        with Image.open(self.dest / "img" / "grey_wide" / "full_P001_front.webp") as image:
            self.assertEqual(image.size, (90, 120))

    def test_rejects_unknown_style_and_empty_source(self):
        with self.assertRaises(ValueError):
            add_pose_set.add_pose_set(self.src, self.dest, "depth")
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            add_pose_set.add_pose_set(empty, self.dest, "grey")
        with self.assertRaises(FileNotFoundError):
            add_pose_set.add_pose_set(self.root / "nope", self.dest, "grey")

    def test_main_reports_errors_with_exit_code(self):
        self.assertEqual(add_pose_set.main(["--from", str(self.root / "nope"), "--style", "grey", "--dest", str(self.dest)]), 2)
        self.assertEqual(add_pose_set.main(["--from", str(self.src), "--style", "grey", "--dest", str(self.dest)]), 0)


if __name__ == "__main__":
    unittest.main()
