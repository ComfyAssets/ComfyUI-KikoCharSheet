import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import setup_assets  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "assets"


def fill_source(src: Path) -> Path:
    (src / "data").mkdir(parents=True)
    (src / "data" / "pose-zh.json").write_text("[]", encoding="utf-8")
    for rel in ("img/costume/a.webp", "thumbs/costume/a.webp"):
        (src / rel).parent.mkdir(parents=True)
        (src / rel).write_bytes(b"x")
    return src


def make_source(root: Path) -> Path:
    return fill_source(root / "fork")


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
        self.assertTrue((self.dest / "img" / "costume" / "a.webp").is_file())
        self.assertTrue((self.dest / "thumbs" / "costume" / "a.webp").is_file())
        self.assertFalse((self.dest / "locales").exists())  # the English names ship with the pack
        self.assertEqual(res["mode"], "copy")

    def test_refuses_without_force(self):
        setup_assets.setup(self.src, self.dest, force=False)
        with self.assertRaises(FileExistsError):
            setup_assets.setup(self.src, self.dest, force=False)

    def test_force_overwrites(self):
        setup_assets.setup(self.src, self.dest, force=False)
        (self.dest / "img" / "costume" / "stale.webp").write_bytes(b"s")
        (self.dest / "img" / "old").mkdir()
        setup_assets.setup(self.src, self.dest, force=True)
        self.assertFalse((self.dest / "img" / "costume" / "stale.webp").exists())
        self.assertFalse((self.dest / "img" / "old").exists())
        self.assertTrue((self.dest / "img" / "costume" / "a.webp").is_file())

    def test_gallery_pose_images_are_left_out(self):
        # The gallery's line and depth pose images are not used: poses come from this pack's own renders.
        left_out = ["img/full_P001_front.png", "thumbs/full_P001_front.jpg", "img/depth/d.webp", "thumbs/depth/d.webp"]
        for rel in left_out:
            path = self.src / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
        res = setup_assets.setup(self.src, self.dest, force=False)
        for rel in left_out:
            self.assertFalse((self.dest / rel).exists(), rel)
        self.assertFalse((self.dest / "img" / "depth").exists())
        self.assertEqual(res["skipped_poses"], 4)
        self.assertTrue((self.dest / "img" / "costume" / "a.webp").is_file())

    def test_missing_source(self):
        with self.assertRaises(setup_assets.SourceMissingError) as cm:
            setup_assets.setup(self.tmp / "nope", self.dest, force=False)
        self.assertIn("images come with the clone", str(cm.exception))
        self.assertNotIn("download.py", str(cm.exception))

    def test_original_size_downloads_are_left_out(self):
        # What scripts/download.py adds to a fork clone: full-size files next to the WebP copies.
        kept = ["img/costume/a.webp", "img/portrait/p.webp", "img/costumes/shisei/c.png", "thumbs/costume/t.jpg"]
        left_out = ["img/costume/a.png", "img/portrait/p.PNG"]
        for rel in kept + left_out:
            path = self.src / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
        res = setup_assets.setup(self.src, self.dest, force=False)
        for rel in kept:
            self.assertTrue((self.dest / rel).is_file(), rel)
        for rel in left_out:
            self.assertFalse((self.dest / rel).exists(), rel)
        self.assertEqual(res["skipped_originals"], 2)

    def test_plain_clone_reports_nothing_left_out(self):
        self.assertEqual(setup_assets.setup(self.src, self.dest, force=False)["skipped_originals"], 0)

    def test_cli_missing_source_exit_2(self):
        code = setup_assets.main(["--from", str(self.tmp / "nope"), "--dest", str(self.dest)])
        self.assertEqual(code, 2)

    def test_cli_copy(self):
        code = setup_assets.main(["--from", str(self.src), "--dest", str(self.dest)])
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "data").is_dir())


class FakeGit:
    """Stands in for ``subprocess.run``: records the git commands and fills the folder on checkout."""

    def __init__(self, fail_on=None):
        self.commands = []
        self.fail_on = fail_on

    def __call__(self, cmd, cwd=None, check=None, **kwargs):
        self.commands.append(cmd[1:])
        if cmd[1] == self.fail_on:
            raise setup_assets.subprocess.CalledProcessError(128, cmd)
        if cmd[1] == "checkout":
            fill_source(Path(cwd))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.dest = self.tmp / "assets"

    def test_fetches_only_the_needed_folders_at_the_pinned_commit(self):
        git = FakeGit()
        work = self.tmp / "work"
        work.mkdir()
        setup_assets.download(work, run=git)
        verbs = [c[0] for c in git.commands]
        self.assertEqual(verbs, ["init", "remote", "sparse-checkout", "fetch", "checkout"])
        sparse = git.commands[2]
        self.assertIn("--no-cone", sparse)
        for needed in ("/data/", "/img/costume/", "/img/costumes/", "/img/portrait/", "/thumbs/portrait/"):
            self.assertIn(needed, sparse)
        self.assertNotIn("/img/", sparse)  # never the whole folder: the pose images stay behind
        fetch = git.commands[3]
        self.assertIn("--depth", fetch)
        self.assertIn("--filter=blob:none", fetch)
        self.assertEqual(fetch[-2:], ["origin", setup_assets.GALLERY_REF])
        self.assertIn(setup_assets.GALLERY_URL, git.commands[1])

    def test_ref_can_be_overridden(self):
        git = FakeGit()
        work = self.tmp / "work"
        work.mkdir()
        setup_assets.download(work, ref="HEAD", run=git)
        self.assertEqual(git.commands[3][-1], "HEAD")

    def test_missing_git_and_failed_fetch_are_download_errors(self):
        def no_git(cmd, **kwargs):
            raise FileNotFoundError("git")

        with self.assertRaises(setup_assets.DownloadError) as cm:
            setup_assets.download(self.tmp, run=no_git)
        self.assertIn("git", str(cm.exception).lower())
        with self.assertRaises(setup_assets.DownloadError) as cm:
            setup_assets.download(self.tmp, run=FakeGit(fail_on="fetch"))
        self.assertIn("--from", str(cm.exception))

    def test_cli_download_sets_up_assets_and_removes_the_temporary_copy(self):
        git = FakeGit()
        with unittest.mock.patch.object(setup_assets.subprocess, "run", git):
            code = setup_assets.main(["--download", "--dest", str(self.dest)])
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "img" / "costume" / "a.webp").is_file())
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["assets"])

    def test_cli_download_failure_exits_2_and_leaves_nothing(self):
        with unittest.mock.patch.object(setup_assets.subprocess, "run", FakeGit(fail_on="fetch")):
            code = setup_assets.main(["--download", "--dest", str(self.dest)])
        self.assertEqual(code, 2)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_cli_download_refuses_existing_assets_before_downloading(self):
        (self.dest / "data").mkdir(parents=True)
        git = FakeGit()
        with unittest.mock.patch.object(setup_assets.subprocess, "run", git):
            code = setup_assets.main(["--download", "--dest", str(self.dest)])
        self.assertEqual((code, git.commands), (1, []))

    def test_cli_needs_exactly_one_of_from_and_download(self):
        for argv in ([], ["--download", "--from", str(self.tmp)]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                setup_assets.main(argv + ["--dest", str(self.dest)])


if __name__ == "__main__":
    unittest.main()
