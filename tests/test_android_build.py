"""Exercise archive boundaries before real upstream sources are unpacked."""

import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/android-build.py"


class BuildTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("android_build", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, names):
        archive = self.root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, kind, value in names:
                entry = tarfile.TarInfo(name)
                if kind == "link":
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = value
                    tar.addfile(entry)
                else:
                    content = value.encode()
                    entry.size = len(content)
                    tar.addfile(entry, io.BytesIO(content))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_checksum_failure_leaves_destination_absent(self):
        archive, _ = self.archive([("source/LICENSE", "file", "MIT")])
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.module.extract_verified(archive, "0" * 64, self.root / "out", "source")
        self.assertFalse((self.root / "out").exists())

    def test_exact_source_root_and_files(self):
        archive, checksum = self.archive([("source/LICENSE", "file", "MIT")])
        result = self.module.extract_verified(
            archive, checksum, self.root / "out", "source"
        )
        self.assertEqual((result / "LICENSE").read_text(), "MIT")

    def test_unsafe_members_never_escape(self):
        for members in [
            [("../escaped", "file", "bad")],
            [("source/../../escaped", "file", "bad")],
            [("/escaped", "file", "bad")],
            [("other/LICENSE", "file", "bad")],
            [("source/link", "link", "../../escaped")],
        ]:
            with self.subTest(members=members), tempfile.TemporaryDirectory() as out:
                archive, checksum = self.archive(members)
                with self.assertRaises(ValueError):
                    self.module.extract_verified(
                        archive, checksum, Path(out) / "out", "source"
                    )
                self.assertFalse((self.root / "escaped").exists())

    def test_patch_requires_exact_match(self):
        target = self.root / "file.qml"
        target.write_text("alpha alpha")
        with self.assertRaisesRegex(ValueError, "expected"):
            self.module.replace_exact(target, "alpha", "beta")
        self.assertEqual(target.read_text(), "alpha alpha")
        self.module.replace_exact(target, "alpha", "beta", count=2)
        self.assertEqual(target.read_text(), "beta beta")

    def test_relative_link_within_source_is_allowed(self):
        archive, checksum = self.archive(
            [
                ("source/icon", "file", "image"),
                ("source/sub/icon", "link", "../icon"),
            ]
        )
        out = self.module.extract_verified(
            archive, checksum, self.root / "out", "source"
        )
        self.assertEqual((out / "sub/icon").read_text(), "image")

    def test_release_hash_tracks_content_and_executable_mode(self):
        folder = self.root / "bundle"
        folder.mkdir()
        file = folder / "run"
        file.write_text("first")
        before = self.module.release_digest(folder)
        file.write_text("second")
        after = self.module.release_digest(folder)
        self.assertNotEqual(before, after)
        file.chmod(0o755)
        self.assertNotEqual(after, self.module.release_digest(folder))


if __name__ == "__main__":
    unittest.main()
