import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from android import install, session


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.root = self.base / "data"
        self.bundle = self.base / "bundle"
        for name in ("omarchy", "moarchy", "android"):
            (self.bundle / name).mkdir(parents=True, exist_ok=True)
        (self.bundle / "RELEASE").write_text("a1b2c3d4\n")
        (self.bundle / "android" / "session.py").write_text("#!/usr/bin/env python3\n")
        (self.bundle / "android" / "session.py").chmod(0o755)
        entry = self.bundle / "android" / "session-entry"
        entry.write_text("#!/bin/sh\n")
        entry.chmod(0o755)
        install.install(self.bundle, self.root, self.home, self.facts())
        keyboard = self.root / "profile" / "keyboard" / "usr" / "bin"
        keyboard.mkdir(parents=True)
        (keyboard / "moarchy-keyboard").write_text("#!/bin/sh\n")
        (keyboard / "moarchy-keyboard").chmod(0o755)
        self.release = (self.root / "current").resolve()
        self.sock_path = self.base / "parent.sock"
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(self.sock_path))
        self.previous_runtime = os.environ.get("XDG_RUNTIME_DIR")
        self.runtime = self.base / "runtime"
        self.runtime.mkdir()
        os.environ["XDG_RUNTIME_DIR"] = str(self.runtime)

    def tearDown(self):
        self.sock.close()
        if self.previous_runtime is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self.previous_runtime
        self.tmp.cleanup()

    def facts(self):
        return session.Facts("debian", "13", "aarch64", True)

    def absent_run(self, calls):
        def run(command):
            calls.append(command)
            if (
                command[:3] == ["systemctl", "--user", "show"]
                and command[3] == session.UNIT
            ):
                return session.CommandResult(
                    0, "LoadState=not-found\nActiveState=inactive\n", ""
                )
            return session.CommandResult(0, "", "")

        return run

    def owned_show(self, state="active"):
        return (
            "LoadState=loaded\nActiveState="
            + state
            + "\nExecStart="
            + str(self.release / "android" / "session-entry")
            + "\nEnvironment="
            + "MOARCHY_ANDROID_ROOT="
            + str(self.root)
            + " "
            + "OMARCHY_PATH="
            + str(self.release / "omarchy")
            + " "
            + "MOARCHY_PATH="
            + str(self.release / "moarchy")
            + "\n"
        )

    def test_parent_display_must_be_explicit_absolute_socket(self):
        self.assertEqual(
            session.resolve_parent_display(str(self.sock_path), {}), self.sock_path
        )
        with self.assertRaises(session.SessionError):
            session.resolve_parent_display("wayland-1", {})

    def test_relative_environment_display_resolves_under_outer_runtime(self):
        self.assertEqual(
            session.resolve_parent_display(
                None,
                {
                    "XDG_RUNTIME_DIR": str(self.base),
                    "WAYLAND_DISPLAY": self.sock_path.name,
                },
            ),
            self.sock_path,
        )

    def test_start_builds_pinned_transient_unit_with_only_explicit_environment(self):
        calls = []
        session.start(
            self.root,
            self.release,
            str(self.sock_path),
            home=self.home,
            facts=self.facts(),
            run=self.absent_run(calls),
            ready=lambda _: True,
        )
        command = calls[-1]
        joined = " ".join(command)
        self.assertIn("--unit=moarchy-android-session.service", joined)
        self.assertIn("KillMode=control-group", joined)
        self.assertIn("TimeoutStopSec=20s", joined)
        self.assertIn(str(self.release / "android" / "session-entry"), joined)
        self.assertNotIn("import-environment", joined)

    def test_start_rejects_repointed_legacy_link_before_executable_checks(self):
        link = self.home / ".config" / "omarchy"
        link.unlink()
        link.symlink_to(self.base / "borrowed")
        calls = []
        with self.assertRaises(session.SessionError):
            session.start(
                self.root,
                self.release,
                str(self.sock_path),
                home=self.home,
                facts=self.facts(),
                run=self.absent_run(calls),
                ready=lambda _: True,
            )
        self.assertEqual(calls, [])

    def test_foreign_prefix_and_suffix_properties_are_not_owned(self):
        show = (
            "LoadState=loaded\nActiveState=active\nExecStart=/bin/echo "
            + str(self.release / "android" / "session-entry")
            + "-backup\nEnvironment="
            + "MOARCHY_ANDROID_ROOT="
            + str(self.root)
            + "-other "
            + "OMARCHY_PATH="
            + str(self.release / "omarchy")
            + " "
            + "MOARCHY_PATH="
            + str(self.release / "moarchy")
            + "\n"
        )
        self.assertFalse(session._owned(show, self.root, self.release))

    def test_systemctl_execstart_and_quoted_environment_are_parsed_exactly(self):
        root = Path("/tmp/moarchy root's space")
        release = root / "releases" / "a1b2c3d4"
        show = (
            "LoadState=loaded\nExecStart={ path=/usr/bin/dbus-run-session ; "
            "argv[]=/usr/bin/dbus-run-session -- "
            + shlex.quote(str(release / "android" / "session-entry"))
            + ' ; ignore_errors=no ; status=0/0 }\nEnvironment="MOARCHY_ANDROID_ROOT='
            + str(root)
            + '" "OMARCHY_PATH='
            + str(release / "omarchy")
            + '" "MOARCHY_PATH='
            + str(release / "moarchy")
            + '"\n'
        )
        self.assertTrue(session._owned(show, root, release))

    def test_stop_refuses_manager_failure_and_stops_exact_owned_unit(self):
        with self.assertRaises(session.SessionError):
            session.stop(
                self.root,
                self.release,
                home=self.home,
                run=lambda _: session.CommandResult(1, "", "offline"),
            )
        calls = []

        def run(command):
            calls.append(command)
            if command[:3] == ["systemctl", "--user", "show"]:
                return session.CommandResult(0, self.owned_show(), "")
            return session.CommandResult(0, "", "")

        session.stop(self.root, self.release, home=self.home, run=run)
        self.assertEqual(calls[-1][:3], ["systemctl", "--user", "stop"])

    def test_active_start_is_idempotent_and_does_not_touch_runtime(self):
        runtime = self.runtime / "moarchy-android"
        runtime.mkdir()
        (runtime / "borrowed").write_text("keep")
        calls = []

        def run(command):
            calls.append(command)
            if command[:3] == ["systemctl", "--user", "show"]:
                return session.CommandResult(0, self.owned_show(), "")
            return session.CommandResult(0, "", "")

        session.start(
            self.root,
            self.release,
            str(self.sock_path),
            home=self.home,
            facts=self.facts(),
            run=run,
            ready=lambda _: True,
        )
        self.assertTrue((runtime / "borrowed").exists())
        self.assertFalse(any(command[0] == "systemd-run" for command in calls))

    def test_status_requires_desktop_ready_marker(self):
        def run(command):
            return session.CommandResult(0, self.owned_show(), "")

        self.assertEqual(
            session.status(
                self.root, self.release, home=self.home, run=run, ready=lambda _: False
            ),
            "active; desktop readiness unverified",
        )

    def test_production_readiness_needs_marker_and_nonempty_outputs(self):
        runtime = self.runtime / "moarchy-android"
        runtime.mkdir()
        with patch.object(session, "sway_ready", return_value=True):
            self.assertFalse(session._desktop_ready(runtime, timeout_seconds=0.01))
            (runtime / "desktop-ready").write_text("ready\n")
            self.assertTrue(session._desktop_ready(runtime))

    def test_production_readiness_waits_for_delayed_marker_and_active_output(self):
        runtime = self.runtime / "moarchy-android"
        runtime.mkdir()
        writer = threading.Timer(
            0.02, lambda: (runtime / "desktop-ready").write_text("ready\n")
        )
        writer.start()
        try:
            with patch.object(session, "sway_ready", return_value=True):
                self.assertTrue(session._desktop_ready(runtime, timeout_seconds=0.5))
        finally:
            writer.cancel()

    def test_sway_readiness_rejects_inactive_or_malformed_outputs(self):
        inactive = lambda _: session.CommandResult(0, '[{"active": false}]', "")
        malformed = lambda _: session.CommandResult(0, "not json", "")
        self.assertFalse(
            session.sway_ready(self.sock_path, timeout_seconds=0.01, run=inactive)
        )
        self.assertFalse(
            session.sway_ready(self.sock_path, timeout_seconds=0.01, run=malformed)
        )
        active = lambda _: session.CommandResult(0, '[{"active": true}]', "")
        self.assertTrue(
            session.sway_ready(self.sock_path, timeout_seconds=0.01, run=active)
        )

    def test_installed_cli_does_not_create_pycache_in_immutable_release(self):
        bundle = self.base / "cli-bundle"
        for name in ("omarchy", "moarchy", "android"):
            (bundle / name).mkdir(parents=True, exist_ok=True)
        (bundle / "RELEASE").write_text("c1d2e3f4\n")
        shutil.copy2(Path(session.__file__), bundle / "android" / "session.py")
        shutil.copy2(Path(install.__file__), bundle / "android" / "install.py")
        entry = bundle / "android" / "session-entry"
        entry.write_text("#!/bin/sh\n")
        entry.chmod(0o755)
        root, home = self.base / "cli-root", self.base / "cli-home"
        home.mkdir()
        release = install.install(bundle, root, home, self.facts()).release
        environment = dict(os.environ)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run(
            [sys.executable, str(release / "android" / "session.py"), "--help"],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(path.name == "__pycache__" for path in release.rglob("*")))

    def test_uninstall_refuses_active_owned_service_and_preserves_profile(self):
        state = self.root / "profile" / "state" / "kept"
        state.write_text("data")

        def run(command):
            return session.CommandResult(0, self.owned_show(), "")

        with self.assertRaises(session.SessionError):
            session.uninstall(self.root, home=self.home, run=run)
        self.assertEqual(state.read_text(), "data")

    def test_stop_reclaims_exact_owned_service_after_legacy_link_is_repointed(self):
        legacy = self.home / ".config" / "omarchy"
        legacy.unlink()
        legacy.symlink_to(self.base / "replacement")
        calls = []

        def run(command):
            calls.append(command)
            if command[:3] == ["systemctl", "--user", "show"]:
                return session.CommandResult(0, self.owned_show(), "")
            return session.CommandResult(0, "", "")

        session.stop(self.root, self.release, home=self.home, run=run)
        self.assertEqual(calls[-1][:3], ["systemctl", "--user", "stop"])

    def test_uninstall_preserves_repointed_legacy_link(self):
        legacy = self.home / ".config" / "omarchy"
        replacement = self.base / "replacement"
        replacement.mkdir()
        legacy.unlink()
        legacy.symlink_to(replacement)

        def run(command):
            if command[:3] == ["systemctl", "--user", "show"]:
                return session.CommandResult(
                    0, "LoadState=not-found\nActiveState=inactive\n", ""
                )
            return session.CommandResult(0, "", "")

        session.uninstall(self.root, home=self.home, run=run)
        self.assertEqual(legacy.resolve(), replacement)
        self.assertFalse(os.path.lexists(self.home / ".local" / "state" / "omarchy"))
