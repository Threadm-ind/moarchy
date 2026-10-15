#!/usr/bin/env python3
"""Owned transient-user-service lifecycle for an Android Moarchy session."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

if __name__ == "__main__":
    sys.dont_write_bytecode = True

try:
    from .install import (
        Facts,
        InstallError,
        _lock,
        _require_baseline,
        detect_facts,
        uninstall as uninstall_installation,
        validate_installation,
    )
except ImportError:
    from install import (
        Facts,
        InstallError,
        _lock,
        _require_baseline,
        detect_facts,
        uninstall as uninstall_installation,
        validate_installation,
    )

UNIT = "moarchy-android-session.service"
RUNTIME_MARKER = "MOARCHY_ANDROID_ROOT="


class SessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _run(command):
    timeout = 25 if command[:3] == ["systemctl", "--user", "stop"] else 10
    result = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=timeout
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


def resolve_parent_display(display, environ) -> Path:
    raw = display or environ.get("WAYLAND_DISPLAY", "")
    candidate = Path(raw)
    if display is None and not candidate.is_absolute():
        candidate = Path(environ.get("XDG_RUNTIME_DIR", "")) / candidate
    if (
        not candidate.is_absolute()
        or not candidate.exists()
        or not stat.S_ISSOCK(candidate.stat().st_mode)
    ):
        raise SessionError(
            "parent Wayland display must be an existing absolute Unix socket"
        )
    return candidate


def _properties(show: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in show.splitlines() if "=" in line)


def _owned(show: str, root: Path, release: Path) -> bool:
    properties = _properties(show)
    try:
        environment = shlex.split(properties["Environment"])
    except (KeyError, ValueError):
        return False
    argv_text = properties.get("ExecStart", "")
    marker = "argv[]="
    if marker in argv_text:
        try:
            argv = shlex.split(
                argv_text.split(marker, 1)[1].split(" ;", 1)[0].rstrip("}")
            )
        except ValueError:
            return False
        entry_ok = (
            len(argv) >= 3
            and Path(argv[-1]) == release / "android" / "session-entry"
            and argv[-2] == "--"
            and Path(argv[0]).name == "dbus-run-session"
        )
    else:
        entry_ok = argv_text == str(release / "android" / "session-entry")
    required = {
        f"MOARCHY_ANDROID_ROOT={root}",
        f"OMARCHY_PATH={release / 'omarchy'}",
        f"MOARCHY_PATH={release / 'moarchy'}",
    }
    return entry_ok and required.issubset(set(environment))


def _runtime(root: Path, environ=None) -> Path:
    raw = (os.environ if environ is None else environ).get("XDG_RUNTIME_DIR")
    if not raw or not Path(raw).is_absolute():
        raise SessionError(
            "XDG_RUNTIME_DIR must be an absolute outer runtime directory"
        )
    return Path(raw) / "moarchy-android"


def sway_ready(socket_path: Path, *, timeout_seconds: float = 5, run=None) -> bool:
    run = _run if run is None else run
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = run(["swaymsg", "-s", str(socket_path), "-t", "get_outputs"])
        if result.returncode == 0:
            try:
                outputs = json.loads(result.stdout)
            except json.JSONDecodeError:
                outputs = []
            if isinstance(outputs, list) and any(
                isinstance(output, dict) and output.get("active") is True
                for output in outputs
            ):
                return True
        time.sleep(0.1)
    return False


def _desktop_ready(runtime: Path, ready=None, *, timeout_seconds: float = 30) -> bool:
    """Production readiness waits for a marker and an active Sway output."""
    if ready is not None:
        return ready(runtime / "sway.sock")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if (runtime / "desktop-ready").is_file() and sway_ready(
            runtime / "sway.sock", timeout_seconds=min(1, deadline - time.monotonic())
        ):
            return True
        time.sleep(0.1)
    return False


def _preflight(run, root: Path) -> None:
    keyboard = root / "profile" / "keyboard" / "usr" / "bin" / "moarchy-keyboard"
    if not keyboard.is_file() or not os.access(keyboard, os.X_OK):
        raise SessionError(
            "keyboard payload missing; run the Android setup wrapper first"
        )
    for command in (
        ["systemctl", "--user", "show-environment"],
        ["sway", "--version"],
        ["swaymsg", "--version"],
        ["dbus-run-session", "--version"],
        ["quickshell", "--version"],
    ):
        result = run(command)
        if result.returncode:
            raise SessionError(
                result.stderr
                or f"runtime prerequisite unavailable: {' '.join(command)}"
            )


def _show(run) -> CommandResult:
    result = run(
        [
            "systemctl",
            "--user",
            "show",
            UNIT,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=ExecStart",
            "--property=Environment",
        ]
    )
    if result.returncode:
        raise SessionError(result.stderr or "unable to query user service manager")
    return result


def _unit(run, root: Path, release: Path) -> str:
    fields = _properties(_show(run).stdout)
    if fields.get("LoadState") == "not-found":
        return "absent"
    if "LoadState" not in fields:
        raise SessionError("user manager returned malformed unit state")
    if not _owned(
        "\n".join(f"{key}={value}" for key, value in fields.items()), root, release
    ):
        return "foreign"
    return fields.get("ActiveState", "unknown")


def _clear_stale_runtime(runtime: Path, root: Path) -> None:
    marker = runtime / "ROOT"
    if runtime.is_symlink():
        raise SessionError(f"refusing symlink runtime: {runtime}")
    if runtime.exists():
        try:
            owned = (
                marker.read_text(encoding="utf-8") == RUNTIME_MARKER + str(root) + "\n"
            )
        except OSError:
            owned = False
        if not owned:
            raise SessionError(f"refusing unmanaged runtime directory: {runtime}")
        import shutil

        for item in runtime.iterdir():
            shutil.rmtree(
                item
            ) if item.is_dir() and not item.is_symlink() else item.unlink()
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)
    marker.write_text(RUNTIME_MARKER + str(root) + "\n", encoding="utf-8")


def _start(
    root: Path,
    release: Path | None,
    display=None,
    *,
    home: Path,
    facts: Facts | None = None,
    run=_run,
    ready=None,
) -> None:
    root = Path(root)
    try:
        _require_baseline(detect_facts() if facts is None else facts)
        release = validate_installation(root, home, release)
    except InstallError as error:
        raise SessionError(str(error)) from error
    _preflight(run, root)
    parent = resolve_parent_display(display, os.environ)
    entry = release / "android" / "session-entry"
    if not entry.is_file() or not os.access(entry, os.X_OK):
        raise SessionError("pinned executable session entry is missing")
    state = _unit(run, root, release)
    if state == "active":
        return
    if state in {"activating", "deactivating"}:
        raise SessionError("owned session is transitioning; refusing runtime reuse")
    if state == "foreign":
        raise SessionError("refusing fixed-unit collision with foreign service")
    if state != "absent":
        stopped = run(["systemctl", "--user", "stop", UNIT])
        if stopped.returncode or _unit(run, root, release) not in {
            "absent",
            "inactive",
            "failed",
        }:
            raise SessionError(
                stopped.stderr or "owned unit did not stop before runtime cleanup"
            )
    runtime = _runtime(root)
    _clear_stale_runtime(runtime, root)
    command = [
        "systemd-run",
        "--user",
        f"--unit={UNIT}",
        "--collect",
        "--property=Type=exec",
        "--property=KillMode=control-group",
        "--property=TimeoutStopSec=20s",
        "--property=Restart=no",
        f"--setenv=OMARCHY_PATH={release / 'omarchy'}",
        f"--setenv=MOARCHY_PATH={release / 'moarchy'}",
        f"--setenv=MOARCHY_ANDROID_ROOT={root}",
        f"--setenv=MOARCHY_PARENT_DISPLAY={parent}",
        f"--setenv=XDG_RUNTIME_DIR={runtime}",
        "dbus-run-session",
        "--",
        str(entry),
    ]
    result = run(command)
    if result.returncode:
        raise SessionError(result.stderr or "systemd-run failed")
    if not _desktop_ready(runtime, ready):
        stopped = run(["systemctl", "--user", "stop", UNIT])
        if stopped.returncode:
            raise SessionError(
                "Sway readiness failed and owned unit could not be stopped"
            )
        raise SessionError("service started but desktop readiness did not respond")


def start(
    root: Path,
    release: Path | None = None,
    display=None,
    *,
    home: Path | None = None,
    **kwargs,
) -> None:
    home = Path.home() if home is None else Path(home)
    with _lock(home):
        _start(root, release, display, home=home, **kwargs)


def status(
    root: Path,
    release: Path | None = None,
    *,
    home: Path | None = None,
    run=_run,
    ready=None,
) -> str:
    home = Path.home() if home is None else Path(home)
    with _lock(home):
        try:
            release = validate_installation(root, home, release, require_legacy=False)
            state = _unit(run, Path(root), release)
        except (InstallError, SessionError):
            return "unavailable"
        if state == "active" and not _desktop_ready(_runtime(Path(root)), ready):
            return "active; desktop readiness unverified"
        return state


def _stop(root: Path, release: Path | None, *, home: Path, run=_run) -> None:
    try:
        release = validate_installation(root, home, release, require_legacy=False)
    except InstallError as error:
        raise SessionError(str(error)) from error
    state = _unit(run, Path(root), release)
    if state == "absent":
        return
    if state == "foreign":
        raise SessionError("refusing to stop foreign or unverified unit")
    result = run(["systemctl", "--user", "stop", UNIT])
    if result.returncode:
        raise SessionError(result.stderr or "systemctl stop failed")


def stop(
    root: Path, release: Path | None = None, *, home: Path | None = None, run=_run
) -> None:
    home = Path.home() if home is None else Path(home)
    with _lock(home):
        _stop(root, release, home=home, run=run)


def uninstall(root: Path, *, home: Path | None = None, run=_run) -> None:
    home = Path.home() if home is None else Path(home)

    def active():
        release = validate_installation(root, home, require_legacy=False)
        return _unit(run, Path(root), release) in {
            "active",
            "activating",
            "deactivating",
        }

    try:
        uninstall_installation(root, home, active=active)
    except InstallError as error:
        raise SessionError(str(error)) from error


def _installed_root() -> Path:
    candidate = Path(__file__).resolve().parents[3]
    try:
        if (candidate / "INSTALLATION_MARKER").read_text(
            encoding="utf-8"
        ) == "moarchy-android-v1\n":
            return candidate
    except OSError:
        pass
    return Path.home() / ".local/share/moarchy-android"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop", "uninstall"))
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--display")
    args = parser.parse_args(argv)
    root = args.root or _installed_root()
    if args.action == "start":
        start(root, display=args.display)
    elif args.action == "stop":
        stop(root)
    elif args.action == "uninstall":
        uninstall(root)
    else:
        print(status(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
