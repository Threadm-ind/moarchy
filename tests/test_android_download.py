"""Behavior tests for the deliberately non-installing Android bundle downloader."""

import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "android-download.py"


class Response:
    def __init__(self, payload):
        self.payload = io.BytesIO(payload)

    def read(self, count=-1):
        return self.payload.read(count)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False


class DownloadTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("android_download", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()

    def archive(self, members):
        path = self.root / "fixture.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, content in members:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        return path.read_bytes()

    def pinned_fixture(self, payload):
        return patch.multiple(
            self.module,
            ARTIFACT_NAME="fixture.tar.gz",
            EXPECTED_BYTES=len(payload),
            EXPECTED_SHA256=hashlib.sha256(payload).hexdigest(),
            MIN_FREE_BYTES=1,
        )

    def test_low_space_refuses_before_network_or_stage_write(self):
        calls = []
        low_space = type(
            "Vfs", (), {"f_bavail": 1, "f_frsize": 1, "f_favail": 1, "f_files": 1}
        )()
        with (
            patch.object(self.module.os, "statvfs", return_value=low_space),
            patch.object(
                self.module.urllib.request,
                "urlopen",
                side_effect=lambda *args: calls.append(args),
            ),
        ):
            with self.assertRaisesRegex(self.module.DownloadError, "4 GiB.*1 bytes"):
                self.module.prepare_download(
                    "https://downloads.example/releases", self.home
                )
        self.assertEqual(calls, [])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_downloads_pinned_archive_under_home_and_never_installs(self):
        payload = self.archive(
            [
                ("moarchy-android/android/setup.sh", b"marker"),
                ("moarchy-android/README", b"ok"),
            ]
        )
        alternate_tmp = self.root / "other-tmp"
        alternate_tmp.mkdir()
        marker = self.root / "installer-ran"
        with (
            self.pinned_fixture(payload),
            patch.dict("os.environ", {"TMPDIR": str(alternate_tmp)}),
            patch.object(
                self.module.urllib.request, "urlopen", return_value=Response(payload)
            ) as open_url,
        ):
            result = self.module.prepare_download(
                "https://downloads.example/releases", self.home
            )
        self.assertEqual(
            open_url.call_args.args[0].full_url,
            "https://downloads.example/releases/fixture.tar.gz",
        )
        self.assertTrue(result.archive.is_file())
        self.assertEqual(
            (result.extracted / "moarchy-android" / "README").read_bytes(), b"ok"
        )
        self.assertTrue((result.extracted / self.module.SETUP_RELATIVE_PATH).is_file())
        self.assertTrue(result.stage.is_relative_to(self.home))
        self.assertFalse(marker.exists())
        self.assertEqual(list(alternate_tmp.iterdir()), [])

    def test_bad_transfers_refuse_without_extracting_or_touching_unrelated_files(self):
        payload = self.archive([("bundle/README", b"ok")])
        protected = self.home / "keep"
        protected.write_text("untouched")
        for supplied in (
            payload[:-1],
            payload[:-1] + bytes([payload[-1] ^ 1]),
            payload + b"x",
        ):
            with (
                self.subTest(length=len(supplied)),
                self.pinned_fixture(payload),
                patch.object(
                    self.module.urllib.request,
                    "urlopen",
                    return_value=Response(supplied),
                ),
            ):
                with self.assertRaises(self.module.DownloadError):
                    self.module.prepare_download("https://downloads.example", self.home)
            self.assertEqual(protected.read_text(), "untouched")
            self.assertEqual(list(self.home.glob("moarchy-download-*")), [])

    def test_unsafe_or_wrong_root_archive_refuses_and_cleans_only_owned_stage(self):
        protected = self.home / "keep"
        protected.write_text("untouched")
        for members in [
            [("../outside", b"bad")],
            [("wrong-root/android/setup.sh", b"bad")],
        ]:
            payload = self.archive(members)
            with (
                self.subTest(members=members),
                self.pinned_fixture(payload),
                patch.object(
                    self.module.urllib.request,
                    "urlopen",
                    return_value=Response(payload),
                ),
            ):
                with self.assertRaisesRegex(self.module.DownloadError, "unsafe|root"):
                    self.module.prepare_download("https://downloads.example", self.home)
        self.assertEqual(protected.read_text(), "untouched")
        self.assertFalse((self.root / "outside").exists())
        self.assertEqual(list(self.home.glob("moarchy-download-*")), [])

    def test_help_exits_without_starting_a_download(self):
        with (
            patch.object(sys, "argv", ["android-download.py", "--help"]),
            patch.object(
                self.module,
                "prepare_download",
                side_effect=AssertionError("download started"),
            ),
        ):
            with self.assertRaises(SystemExit) as exited:
                self.module.main()
        self.assertEqual(exited.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
