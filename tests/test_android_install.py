import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from android import install


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.root = self.base / "data"
        self.bundle = self.base / "bundle"
        (self.bundle / "omarchy").mkdir(parents=True)
        (self.bundle / "moarchy").mkdir()
        (self.bundle / "android").mkdir()
        (self.bundle / "RELEASE").write_text("a1b2c3d4\n")
        session = self.bundle / "android" / "session.py"
        session.write_text("#!/usr/bin/env python3\n# fixture\n")
        session.chmod(0o755)
        entry = self.bundle / "android" / "session-entry"
        entry.write_text("#!/bin/sh\n")
        entry.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def facts(self):
        return install.Facts("debian", "13", "aarch64", True)

    def test_install_copies_release_claims_exact_links_and_launcher(self):
        result = install.install(self.bundle, self.root, self.home, self.facts())
        self.assertEqual(result.release.name, "a1b2c3d4")
        self.assertEqual((self.root / "current").resolve(), result.release)
        self.assertEqual(
            (self.home / ".config" / "omarchy").resolve(),
            self.root / "profile" / "config",
        )
        self.assertEqual(
            (self.home / ".local" / "state" / "omarchy").resolve(),
            self.root / "profile" / "state",
        )
        self.assertEqual(
            (self.home / ".local" / "bin" / "moarchy-android").resolve(),
            result.release / "android" / "session.py",
        )

    def test_refuses_unmanaged_or_dangling_legacy_path_without_claiming_other(self):
        path = self.home / ".config" / "omarchy"
        path.parent.mkdir(parents=True)
        path.symlink_to(self.base / "missing")
        with self.assertRaises(install.InstallError):
            install.install(self.bundle, self.root, self.home, self.facts())
        self.assertFalse((self.home / ".local" / "state" / "omarchy").exists())

    def test_repeat_preserves_profile_state(self):
        install.install(self.bundle, self.root, self.home, self.facts())
        saved = self.root / "profile" / "state" / "keep"
        saved.write_text("keep")
        install.install(self.bundle, self.root, self.home, self.facts())
        self.assertEqual(saved.read_text(), "keep")

    def test_cli_upgrade_does_not_write_bytecode_into_bundle_or_release(self):
        install.install(self.bundle, self.root, self.home, self.facts())
        upgrade = self.base / "upgrade"
        shutil.copytree(self.bundle, upgrade)
        (upgrade / "RELEASE").write_text("b1b2c3d4\n")
        source = Path(install.__file__).parent
        for name in ("install.py", "session.py"):
            shutil.copy2(source / name, upgrade / "android" / name)
        entry = upgrade / "android/install.py"
        text = entry.read_text()
        # Exact fixture seams: preserve CLI orchestration and dynamic imports.
        self.assertEqual(text.count("    home = Path.home()"), 1)
        text = text.replace(
            "    home = Path.home()", f"    home = Path({str(self.home)!r})"
        )
        self.assertEqual(text.count("        detect_facts(),"), 1)
        entry.write_text(
            text.replace(
                "        detect_facts(),",
                "        Facts('debian', '13', 'aarch64', True),",
            )
        )
        commands = self.base / "commands"
        commands.mkdir()
        fake = commands / "systemctl"
        fake.write_text(
            "#!/bin/sh\nprintf 'LoadState=not-found\\nActiveState=inactive\\n'\n"
        )
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(commands))
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run(
            [sys.executable, str(entry), str(upgrade), "--root", str(self.root)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(upgrade.rglob("__pycache__")), [])
        self.assertEqual(
            list((self.root / "releases/b1b2c3d4").rglob("__pycache__")), []
        )

    def test_upgrade_keeps_stable_launcher_and_refuses_active_session(self):
        first = install.install(self.bundle, self.root, self.home, self.facts())
        launcher = self.home / ".local" / "bin" / "moarchy-android"
        self.assertEqual(
            os.readlink(launcher), str(self.root / "current" / "android" / "session.py")
        )
        second = self.base / "second"
        shutil.copytree(self.bundle, second)
        (second / "RELEASE").write_text("b1b2c3d4\n")
        with self.assertRaises(install.InstallError):
            install.install(
                second, self.root, self.home, self.facts(), active=lambda: True
            )
        self.assertEqual((self.root / "current").resolve(), first.release)
        result = install.install(second, self.root, self.home, self.facts())
        self.assertEqual((self.root / "current").resolve(), result.release)
        self.assertEqual(
            os.readlink(launcher), str(self.root / "current" / "android" / "session.py")
        )

    def test_collision_does_not_create_unmanaged_root_and_retry_succeeds(self):
        collision = self.home / ".config" / "omarchy"
        collision.parent.mkdir(parents=True)
        collision.symlink_to(self.base / "borrowed")
        with self.assertRaises(install.InstallError):
            install.install(self.bundle, self.root, self.home, self.facts())
        self.assertFalse(os.path.lexists(self.root))
        collision.unlink()
        install.install(self.bundle, self.root, self.home, self.facts())
        self.assertTrue((self.root / "INSTALLATION_MARKER").is_file())

    def test_rejects_adopted_profile_directory(self):
        install.install(self.bundle, self.root, self.home, self.facts())
        profile = self.root / "profile" / "config"
        profile.rmdir()
        profile.symlink_to(self.base / "borrowed")
        with self.assertRaises(install.InstallError):
            install.validate_installation(self.root, self.home)

    def test_cli_wires_upgrade_activity_query(self):
        with (
            patch.object(install, "install") as invoked,
            patch.object(Path, "home", return_value=self.home),
        ):
            install.main([str(self.bundle), "--root", str(self.root)])
        active = invoked.call_args.kwargs["active"]
        with patch.object(install, "_active_owned_session", return_value=True) as query:
            self.assertTrue(active())
        query.assert_called_once_with(self.root, self.home)

    def test_rejects_nonbaseline_facts_before_writing(self):
        with self.assertRaises(install.InstallError):
            install.install(
                self.bundle,
                self.root,
                self.home,
                install.Facts("debian", "13", "x86_64", True),
            )
        self.assertFalse(self.root.exists())

    def test_rejects_unsafe_release_before_writing(self):
        (self.bundle / "RELEASE").write_text("../bad\n")
        with self.assertRaises(install.InstallError):
            install.install(self.bundle, self.root, self.home, self.facts())
        self.assertFalse(self.root.exists())

    def test_rejects_nonexecutable_or_incomplete_session_bundle_before_writing(self):
        (self.bundle / "android" / "session.py").chmod(0o644)
        with self.assertRaises(install.InstallError):
            install.install(self.bundle, self.root, self.home, self.facts())
        self.assertFalse(self.root.exists())

    def test_uninstall_removes_only_owned_links_and_preserves_profile(self):
        install.install(self.bundle, self.root, self.home, self.facts())
        kept = self.root / "profile" / "state" / "kept"
        kept.write_text("state")
        install.uninstall(self.root, self.home)
        self.assertFalse(os.path.lexists(self.home / ".config" / "omarchy"))
        self.assertEqual(kept.read_text(), "state")
