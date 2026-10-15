import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = REPO / "scripts" / "android-check.sh"


class AndroidCheckTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.temp = Path(self.workspace.name)
        self.mock_bin = self.temp / "bin"
        self.mock_bin.mkdir()
        self.script = self.temp / "android-check.sh"
        self.os_release = self.temp / "os-release"
        for name in ("bash", "cat", "touch"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, f"test host must provide {name}")
            (self.mock_bin / name).symlink_to(executable)

    def tearDown(self):
        self.workspace.cleanup()

    def prepare_script(self, os_release=None, block_os_release=False):
        self.assertTrue(SOURCE_SCRIPT.exists(), "android-check.sh must exist")
        if block_os_release:
            os.mkfifo(self.os_release)
        else:
            self.os_release.write_text(os_release, encoding="utf-8")
        source = SOURCE_SCRIPT.read_text(encoding="utf-8")
        assignment = 'OS_RELEASE_FILE="/etc/os-release"'
        self.assertEqual(source.count(assignment), 1, "test seam must be unique")
        source = source.replace(assignment, f'OS_RELEASE_FILE="{self.os_release}"')
        self.script.write_text(source, encoding="utf-8")
        self.script.chmod(self.script.stat().st_mode | stat.S_IXUSR)

    def command(self, name, body):
        path = self.mock_bin / name
        path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def install_standard_commands(self, arch="aarch64", uname_status=0):
        self.command(
            "uname",
            f'if [ "$1" = "-m" ]; then echo "{arch}"; exit {uname_status}; fi\necho "6.12.0-test"',
        )
        self.command(
            "getconf", 'if [ "$1" = "PAGESIZE" ]; then echo 4096; exit 0; fi\nexit 2'
        )
        for name in ("enable_display", "sway", "quickshell", "dbus-run-session"):
            self.command(name, "exit 0")

    def run_check(self, *args, extra_env=None, timeout=2):
        env = os.environ.copy()
        env["PATH"] = str(self.mock_bin)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(self.script), *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
            timeout=timeout,
        )

    def test_help_succeeds_without_probing(self):
        self.prepare_script(block_os_release=True)
        marker = self.temp / "probed"
        self.command("uname", f'touch "{marker}"\nexit 99')

        cases = (("-h", 0), ("--help", 0), ("--unknown", 2), ("--help", "extra", 2))
        for *args, expected_status in cases:
            with self.subTest(args=args):
                result = self.run_check(*args)

                self.assertEqual(result.returncode, expected_status)
                self.assertIn(
                    "Usage:", result.stdout if expected_status == 0 else result.stderr
                )
        self.assertFalse(marker.exists())

    def test_supported_synthetic_debian_guest_reports_unverified_desktop(self):
        self.prepare_script('ID=debian\nVERSION_ID="13"\nNAME="Debian GNU/Linux"\n')
        self.install_standard_commands()

        result = self.run_check(
            extra_env={"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OS_ID=debian", result.stdout)
        self.assertIn("CPU_ARCH=aarch64", result.stdout)
        self.assertIn("ENABLE_DISPLAY=available", result.stdout)
        self.assertIn("WAYLAND_DISPLAY=present", result.stdout)
        self.assertIn("DISPLAY=present", result.stdout)
        self.assertIn("BASELINE_CANDIDATE=PASS", result.stdout)
        self.assertIn("DESKTOP_STATUS=UNVERIFIED", result.stdout)

    def test_wrong_os_arch_or_missing_helper_fails_baseline(self):
        cases = (
            (
                "ID=ubuntu\nVERSION_ID=24.04\nNAME=Ubuntu\n",
                "aarch64",
                True,
                "requires Debian",
            ),
            (
                "ID=debian\nVERSION_ID=13\nNAME=Debian\n",
                "x86_64",
                True,
                "requires aarch64",
            ),
            (
                "ID=debian\nVERSION_ID=13\nNAME=Debian\n",
                "aarch64",
                False,
                "enable_display helper is missing",
            ),
        )
        for os_release, arch, helper, reason in cases:
            with self.subTest(reason=reason):
                self.mock_bin.mkdir(exist_ok=True)
                self.prepare_script(os_release)
                self.install_standard_commands(arch=arch)
                if not helper:
                    (self.mock_bin / "enable_display").unlink()

                result = self.run_check()

                self.assertEqual(result.returncode, 1)
                self.assertIn(reason, result.stderr)
                self.assertNotIn("BASELINE_CANDIDATE=PASS", result.stdout)

    def test_malformed_os_release_is_inert_and_fails(self):
        marker = self.temp / "executed"
        self.prepare_script(f'ID=$(touch "{marker}")\nVERSION_ID=13\nNAME=Debian\n')
        self.install_standard_commands()

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertFalse(marker.exists())
        self.assertIn("requires Debian", result.stderr)
        self.assertNotIn("BASELINE_CANDIDATE=PASS", result.stdout)

    def test_collection_failure_never_reports_baseline_pass(self):
        self.prepare_script("ID=debian\nVERSION_ID=13\nNAME=Debian\n")
        self.install_standard_commands(uname_status=1)

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn("could not collect CPU architecture", result.stderr)
        self.assertNotIn("BASELINE_CANDIDATE=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
