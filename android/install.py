"""Per-user, non-privileged installation of an already prepared Android bundle."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

MARKER = "moarchy-android-v1\n"

if __name__ == "__main__":
    sys.dont_write_bytecode = True


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Facts:
    os_id: str
    version_id: str
    architecture: str
    enable_display: bool


@dataclass(frozen=True)
class InstallResult:
    root: Path
    release: Path


def detect_facts() -> Facts:
    fields = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in {"ID", "VERSION_ID"}:
                fields[key] = value.strip().strip('"')
    return Facts(
        fields.get("ID", ""),
        fields.get("VERSION_ID", ""),
        os.uname().machine,
        Path("/usr/local/bin/enable_display").is_file(),
    )


def _require_baseline(facts: Facts) -> None:
    if os.environ.get("MOARCHY_ANDROID_PROOT") == "1":
        # Tablet adaptation: a proot Debian guest reports the same ID, version
        # and architecture but has no Google Terminal display helper.
        if (facts.os_id, facts.version_id, facts.architecture) != (
            "debian",
            "13",
            "aarch64",
        ):
            raise InstallError("proot tablet mode requires Debian 13 aarch64")
        return
    if (facts.os_id, facts.version_id, facts.architecture, facts.enable_display) != (
        "debian",
        "13",
        "aarch64",
        True,
    ):
        raise InstallError(
            "requires Debian 13 aarch64 with /usr/local/bin/enable_display"
        )


def _release(bundle: Path) -> str:
    try:
        value = (bundle / "RELEASE").read_text(encoding="utf-8").strip()
    except OSError as error:
        raise InstallError("bundle RELEASE is missing") from error
    if not re.fullmatch(r"[0-9a-f]{8,128}", value):
        raise InstallError("bundle RELEASE must be a safe hexadecimal id")
    return value


def _exists(path: Path) -> bool:
    return os.path.lexists(path)


def _real_dir(path: Path) -> bool:
    return _exists(path) and not path.is_symlink() and path.is_dir()


@contextmanager
def _lock(home: Path):
    """Use one canonical lock outside the mutable installation root."""
    import fcntl

    lock_path = home / ".local" / "state" / "moarchy-android.lock"
    if _exists(lock_path) and lock_path.is_symlink():
        raise InstallError(f"refusing symlink lock: {lock_path}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if _exists(lock_path) and not lock_path.is_file():
        raise InstallError(f"refusing non-file lock: {lock_path}")
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        digest.update(item.relative_to(path).as_posix().encode() + b"\0")
        digest.update(str(item.lstat().st_mode).encode() + b"\0")
        if item.is_symlink():
            digest.update(os.readlink(item).encode())
        elif item.is_file():
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _owned_link(path: Path, target: Path, marker: Path) -> bool:
    try:
        return (
            _exists(path)
            and path.is_symlink()
            and os.readlink(path) == str(target)
            and marker.read_text(encoding="utf-8") == MARKER
        )
    except OSError:
        return False


def _legacy(home: Path, root: Path):
    profile = root / "profile"
    return (
        (home / ".config" / "omarchy", profile / "config"),
        (home / ".local" / "state" / "omarchy", profile / "state"),
    )


def _validate_root(root: Path) -> None:
    marker = root / "INSTALLATION_MARKER"
    try:
        marked = marker.read_text(encoding="utf-8") == MARKER
    except OSError:
        marked = False
    if not _real_dir(root) or not marked:
        raise InstallError(f"refusing unmanaged installation root: {root}")
    for path in (
        root / "profile",
        root / "profile" / "config",
        root / "profile" / "state",
        root / "releases",
    ):
        if not _real_dir(path):
            raise InstallError(f"refusing invalid owned installation path: {path}")


def validate_installation(
    root: Path, home: Path, release: Path | None = None, *, require_legacy: bool = True
) -> Path:
    root, home = Path(root), Path(home)
    _validate_root(root)
    if require_legacy:
        marker = root / "INSTALLATION_MARKER"
        for path, target in _legacy(home, root):
            if not _owned_link(path, target, marker):
                raise InstallError(f"refusing missing or repointed legacy path: {path}")
    current = root / "current"
    if not current.is_symlink():
        raise InstallError("refusing missing current release link")
    selected = Path(os.readlink(current))
    if not selected.is_absolute():
        selected = current.parent / selected
    try:
        selected = selected.resolve(strict=True)
    except OSError as error:
        raise InstallError("refusing dangling current release link") from error
    if selected.parent != (root / "releases").resolve() or not _real_dir(selected):
        raise InstallError("refusing unmanaged current release link")
    if release is not None:
        try:
            expected = Path(release).resolve(strict=True)
        except OSError as error:
            raise InstallError("refusing missing release") from error
        if selected != expected:
            raise InstallError("refusing release that is not current")
    return selected


def _check_bundle(bundle: Path) -> None:
    if not _real_dir(bundle):
        raise InstallError("bundle must be a real directory")
    for path in (
        bundle / "omarchy",
        bundle / "moarchy",
        bundle / "android",
        bundle / "android" / "session.py",
    ):
        if path.is_symlink() or not path.exists():
            raise InstallError(f"bundle required path is missing or symlinked: {path}")
    launcher = bundle / "android" / "session.py"
    try:
        shebang = launcher.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError) as error:
        raise InstallError("bundle Python session launcher is unreadable") from error
    if (
        not launcher.is_file()
        or not os.access(launcher, os.X_OK)
        or "python" not in shebang
    ):
        raise InstallError(
            "bundle Python session launcher must be executable with a Python shebang"
        )
    entry = bundle / "android" / "session-entry"
    if entry.is_symlink() or not entry.is_file() or not os.access(entry, os.X_OK):
        raise InstallError("bundle executable session entry is missing")


def _replace_link(path: Path, target: Path, staging: Path) -> None:
    staging.symlink_to(target)
    staging.replace(path)


def install(
    bundle: Path, root: Path, home: Path, facts: Facts, *, active=lambda: False
) -> InstallResult:
    _require_baseline(facts)
    bundle, root, home = Path(bundle), Path(root), Path(home)
    _check_bundle(bundle)
    release_id = _release(bundle)
    release = root / "releases" / release_id
    marker = root / "INSTALLATION_MARKER"
    launcher = home / ".local" / "bin" / "moarchy-android"
    created: list[Path] = []
    with _lock(home):
        root_exists = _exists(root)
        if root_exists:
            _validate_root(root)
        for path, target in _legacy(home, root):
            if _exists(path) and not _owned_link(path, target, marker):
                raise InstallError(
                    f"refusing unmanaged or dangling legacy path: {path}"
                )
        current = root / "current"
        if _exists(current) and (
            not current.is_symlink() or current.resolve().parent != root / "releases"
        ):
            raise InstallError("refusing unmanaged current link")
        if _exists(launcher) and not _owned_link(
            launcher, root / "current" / "android" / "session.py", marker
        ):
            raise InstallError(f"refusing unmanaged launcher: {launcher}")
        if release.exists() and (
            release.is_symlink()
            or not release.is_dir()
            or _tree_hash(release) != _tree_hash(bundle)
        ):
            raise InstallError("existing release content differs from immutable bundle")
        old_current = os.readlink(current) if current.is_symlink() else None
        if old_current is not None and current.resolve() != release and active():
            raise InstallError("refusing upgrade while the owned session is active")
        try:
            if not root_exists:
                root.mkdir(parents=True)
                (root / "profile" / "config").mkdir(parents=True)
                (root / "profile" / "state").mkdir(parents=True)
                (root / "releases").mkdir()
                marker.write_text(MARKER, encoding="utf-8")
            if not release.exists():
                staging_root = Path(tempfile.mkdtemp(prefix="release-", dir=root))
                try:
                    shutil.copytree(bundle, staging_root / release_id, symlinks=True)
                    (staging_root / release_id).replace(release)
                finally:
                    shutil.rmtree(staging_root, ignore_errors=True)
            for path, target in _legacy(home, root):
                if not _exists(path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(target)
                    created.append(path)
            if not _exists(launcher):
                launcher.parent.mkdir(parents=True, exist_ok=True)
                launcher.symlink_to(root / "current" / "android" / "session.py")
                created.append(launcher)
            staging = root / ".current-new"
            if _exists(staging):
                raise InstallError("refusing occupied current staging link")
            _replace_link(current, release, staging)
            return InstallResult(root, release)
        except Exception:
            if old_current is not None and current.is_symlink():
                rollback = root / ".current-rollback"
                if not _exists(rollback):
                    _replace_link(current, Path(old_current), rollback)
            elif old_current is None and current.is_symlink():
                current.unlink()
            for path in reversed(created):
                if path.is_symlink():
                    path.unlink()
            raise


def uninstall(root: Path, home: Path, *, active=lambda: False) -> None:
    root, home = Path(root), Path(home)
    with _lock(home):
        validate_installation(root, home, require_legacy=False)
        if active():
            raise InstallError("refusing uninstall while the owned session is active")
        marker = root / "INSTALLATION_MARKER"
        for path, target in _legacy(home, root):
            if _owned_link(path, target, marker):
                path.unlink()
        launcher = home / ".local" / "bin" / "moarchy-android"
        if _owned_link(launcher, root / "current" / "android" / "session.py", marker):
            launcher.unlink()


def _active_owned_session(root: Path, home: Path) -> bool:
    """Query the fixed unit only while an existing installation is being upgraded."""
    try:
        from . import session
    except ImportError:
        import session
    release = validate_installation(root, home, require_legacy=False)
    return session._unit(session._run, root, release) in {
        "active",
        "activating",
        "deactivating",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--root", type=Path, default=Path.home() / ".local/share/moarchy-android"
    )
    args = parser.parse_args(argv)
    home = Path.home()
    install(
        args.bundle,
        args.root,
        home,
        detect_facts(),
        active=lambda: _active_owned_session(args.root, home),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
