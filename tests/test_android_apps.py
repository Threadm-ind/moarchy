"""Android app sync turns scrcpy's app list into owned launcher entries."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "android/bin/moarchy-android-apps"


def listing(apps):
    """The exact layout of scrcpy 3.3.4 LogUtils.buildAppListMessage."""
    text = "[server] INFO: Processing Android apps... (this may take some time)\n"
    text += "[server] INFO: List of apps:"
    for system, name, package in apps:
        text += "\n " + ("* " if system else "- ") + name
        text += " " * (30 - len(name)) if len(name) < 30 else "\n   " + " " * 30
        text += " " + package
    return text + "\n"


class AndroidAppsTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.temp = Path(self.workspace.name)
        self.bin = self.temp / "bin"
        self.bin.mkdir()
        self.apps = self.temp / "data" / "applications"
        self.list = self.temp / "list.txt"
        self.command("adb", "if [[ $* == *get-state ]]; then echo device; fi")
        self.command("scrcpy", f'cat "{self.list}"\nexit "${{FAKE_STATUS:-0}}"')
        self.command("notify-send", "exit 0")

    def tearDown(self):
        self.workspace.cleanup()

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def sync(self, status=0):
        env = dict(
            os.environ,
            PATH=f"{self.bin}:/usr/bin:/bin",
            XDG_DATA_HOME=str(self.temp / "data"),
            XDG_STATE_HOME=str(self.temp / "state"),
            XDG_CONFIG_HOME=str(self.temp / "config"),
            FAKE_STATUS=str(status),
        )
        return subprocess.run(
            [str(SCRIPT), "sync"], env=env, capture_output=True, text=True
        )

    def entries(self):
        return {
            path.name: path.read_text(encoding="utf-8")
            for path in self.apps.glob("*.desktop")
        }

    def test_sync_writes_every_app_and_removes_only_stale_owned_entries(self):
        self.apps.mkdir(parents=True)
        (self.apps / "moarchy-android-app-com.removed.app.desktop").write_text(
            "stale\n"
        )
        (self.apps / "moarchy-android-terminal.desktop").write_text("session entry\n")
        long_name = "A Very Long Application Label 1.2"
        self.list.write_text(
            listing(
                [
                    (True, "Chrome", "com.android.chrome"),
                    (True, "Terminal", "com.android.virtualization.terminal"),
                    (False, long_name, "org.example.longlabel"),
                    (False, "Back\\slash Notes", "org.example.notes"),
                ]
            )
        )

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        entries = self.entries()
        self.assertEqual(
            set(entries),
            {
                "moarchy-android-terminal.desktop",
                "moarchy-android-app-com.android.chrome.desktop",
                "moarchy-android-app-org.example.longlabel.desktop",
                "moarchy-android-app-org.example.notes.desktop",
            },
        )
        chrome = entries["moarchy-android-app-com.android.chrome.desktop"]
        self.assertIn("\nName=Chrome\n", chrome)
        self.assertIn("\nExec=moarchy-android-apps launch com.android.chrome\n", chrome)
        self.assertIn(
            f"\nName={long_name}\n",
            entries["moarchy-android-app-org.example.longlabel.desktop"],
        )
        self.assertIn(
            "\nName=Back\\\\slash Notes\n",
            entries["moarchy-android-app-org.example.notes.desktop"],
        )
        self.assertEqual(entries["moarchy-android-terminal.desktop"], "session entry\n")

    def test_failed_listing_keeps_existing_entries(self):
        self.apps.mkdir(parents=True)
        kept = self.apps / "moarchy-android-app-com.android.chrome.desktop"
        kept.write_text("kept\n")
        for status, text in ((1, "ERROR: Server connection failed\n"), (0, "")):
            with self.subTest(status=status):
                self.list.write_text(text)
                result = self.sync(status)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(kept.read_text(), "kept\n")

    def test_disconnected_phone_fails_before_listing(self):
        self.command("adb", "exit 1")
        self.command("scrcpy", f'touch "{self.temp / "listed"}"')
        result = self.sync()
        self.assertEqual(result.returncode, 1)
        self.assertIn("moarchy-android-apps connect HOST:PORT", result.stderr)
        self.assertFalse((self.temp / "listed").exists())


if __name__ == "__main__":
    unittest.main()
