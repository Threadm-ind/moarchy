#!/usr/bin/env python3
"""Build the Android guest bundle without executing either OS installer."""

import argparse
import hashlib
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.request

REPO = Path(__file__).resolve().parents[1]
OMARCHY_SHA256 = "f8fe9d0ca01226112a144d1961831ce3f27fddfa66e0f9f44b67c375a372b9f1"
PORT_SHA256 = "af7959d7400d8cc3d2e5e9c5ef439c6867ebdb4d4c4299cb5d2a6b82506b3e78"
FONT_SHA256 = "ef552a3e638f25125c6ad4c51176a6adcdce295ab1d2ffacf0db060caf8c1582"
KEYBOARD_SHA256 = "b0606fa00d642ff92d881977332f8fb9b7563519efeccbc2a61368d2fa6e2fc7"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_verified(archive, checksum, destination, source_root):
    if digest(archive) != checksum:
        raise ValueError(f"archive checksum mismatch: {archive}")
    if destination.exists():
        raise ValueError(f"extraction destination exists: {destination}")
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] != source_root
            ):
                raise ValueError(f"unsafe archive path: {member.name}")
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError(f"unsupported archive member: {member.name}")
            if member.issym():
                target = PurePosixPath(member.linkname)
                resolved = PurePosixPath(posixpath.normpath(str(path.parent / target)))
                if (
                    target.is_absolute()
                    or not resolved.parts
                    or resolved.parts[0] != source_root
                ):
                    raise ValueError(f"unsafe archive link: {member.name}")
        destination.mkdir(parents=True)
        try:
            tar.extractall(destination, members=members, filter="data")
        except (tarfile.TarError, OSError) as error:
            shutil.rmtree(destination)
            raise ValueError(f"archive extraction failed: {error}") from error
    return destination / source_root


def replace_exact(path, old, new, count=1):
    text = path.read_text()
    actual = text.count(old)
    if actual != count:
        raise ValueError(f"{path}: expected {count} matches, got {actual}: {old!r}")
    path.write_text(text.replace(old, new))


def release_digest(folder):
    checksum = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            checksum.update(str(path.relative_to(folder)).encode() + b"\0")
            checksum.update(str(path.stat().st_mode & 0o777).encode() + b"\0")
            checksum.update(path.read_bytes())
    return checksum.hexdigest()


def fetch(url, checksum, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    shutil.copyfileobj(response, out)
                out.flush()
                if digest(temporary) != checksum:
                    raise ValueError(f"download checksum mismatch: {url}")
                temporary.rename(path)
            finally:
                temporary.unlink(missing_ok=True)
    if digest(path) != checksum:
        raise ValueError(f"cached archive checksum mismatch: {path}")
    return path


def assemble(source, bundle):
    omarchy = bundle / "omarchy"
    omarchy.mkdir(parents=True)
    for name in ("shell", "config", "default", "themes"):
        shutil.copytree(source / name, omarchy / name, symlinks=True)
    for name in ("LICENSE", "version", "icon.png", "logo.svg"):
        shutil.copy2(source / name, omarchy / name)
    (omarchy / "bin").mkdir()
    for name in ("omarchy-shell", "omarchy-theme-color", "omarchy-theme-set-templates"):
        shutil.copy2(source / "bin" / name, omarchy / "bin" / name)
    subprocess.run(
        [
            "patch",
            "--batch",
            "--fuzz=0",
            "-p1",
            "-i",
            str(REPO / "pkgbuilds/omarchy-config/port-4x.patch"),
        ],
        cwd=omarchy,
        check=True,
    )

    moarchy = bundle / "moarchy"
    shutil.copytree(REPO / "default/omarchy/plugins", moarchy / "plugins")
    (moarchy / "bin").mkdir()
    shutil.copy2(REPO / "bin/moarchy-one-app-per-workspace", moarchy / "bin")
    shutil.copytree(
        REPO / "android",
        bundle / "android",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(REPO / "android/plugins", moarchy / "plugins", dirs_exist_ok=True)
    shutil.copytree(
        REPO / "android/bin",
        omarchy / "bin",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(REPO / "default/themed/sway.conf.tpl", omarchy / "default/themed")
    # Debian 13 Foot keeps cursor colors in [cursor], not the newer [colors-dark].
    replace_exact(
        omarchy / "default/themed/foot.ini.tpl",
        "[colors-dark]",
        "[cursor]\ncolor={{ background_strip }} {{ bright_foreground_strip }}\n\n[colors]",
    )
    replace_exact(
        omarchy / "default/themed/foot.ini.tpl",
        "cursor={{ background_strip }} {{ bright_foreground_strip }}\n\n",
        "",
    )

    # Only the private bus may activate apps; never uwsm or shared user services.
    replace_exact(
        omarchy / "shell/services/AppLibrary.qml",
        "uwsm-app -- gtk-launch ",
        "gtk-launch ",
    )
    replace_exact(omarchy / "shell/Commons/Util.qml", '"-lc"', '"-c"', count=2)
    shell_qml = omarchy / "shell/shell.qml"
    # Wait for the initial inputs before deciding whether a fallback is needed.
    # These latches stay true during later configuration reloads and rescans.
    replace_exact(
        shell_qml,
        "  property bool pluginReloadPending: false\n",
        """  property bool pluginReloadPending: false
  property bool initialDefaultsComplete: false
  property bool initialUserConfigComplete: false
  property bool initialPluginScanComplete: false
  readonly property bool initialBarInputsReady: initialDefaultsComplete
    && initialUserConfigComplete && initialPluginScanComplete
""",
    )
    replace_exact(
        shell_qml,
        "    onLoaded: shell.loadDefaults(text())",
        "    onLoaded: { shell.loadDefaults(text()); shell.initialDefaultsComplete = true }",
    )
    replace_exact(
        shell_qml,
        '      shell.loadDefaults("")',
        '      shell.loadDefaults("")\n      shell.initialDefaultsComplete = true',
    )
    replace_exact(
        shell_qml,
        "    onLoaded: shell.applyShellConfig()",
        "    onLoaded: { shell.applyShellConfig(); shell.initialUserConfigComplete = true }",
    )
    replace_exact(
        shell_qml,
        "    onLoadFailed: function(error) { shell.applyShellConfig() }",
        "    onLoadFailed: function(error) { shell.applyShellConfig(); shell.initialUserConfigComplete = true }",
    )
    replace_exact(
        shell_qml,
        "    active: shell.activeBarId === shell.defaultBarId",
        "    active: shell.initialBarInputsReady && shell.activeBarId === shell.defaultBarId",
    )
    replace_exact(
        shell_qml,
        "    active: !shell.pluginReloading && shell.activeBarId !== shell.defaultBarId",
        "    active: shell.initialBarInputsReady && !shell.pluginReloading && shell.activeBarId !== shell.defaultBarId",
    )
    replace_exact(
        shell_qml,
        "    function onScanFinished() {",
        "    function onScanFinished() {\n      shell.initialPluginScanComplete = true",
    )
    # Normal scans already publish the panels via pluginsChanged. Replacing
    # that array again destroys the first set of asynchronous Loader contexts.
    replace_exact(
        shell_qml,
        """      shell.pluginReloading = false
      shell._syncServices()
      shell.panelEntries = shell.computePanelEntries()""",
        """      var wasReloading = shell.pluginReloading
      shell.pluginReloading = false
      shell._syncServices()
      if (wasReloading) shell.panelEntries = shell.computePanelEntries()""",
    )
    # Quickshell 0.3's native reload replaces the QML/IPC generation in order.
    # Defer it until the IPC invocation has returned; keep the supervised process.
    replace_exact(
        shell_qml,
        """  function reloadPlugins() {
    if (shell.pluginReloading || shell.pluginRegistry.scanning) {
      shell.pluginReloadPending = true
      return
    }
    shell.pluginReloading = true
    shell.unloadPanels()
    shell.unloadPluginServices()
    shell.unloadPluginWidgets()
    Qt.callLater(shell.finishPluginReload)
  }

  function finishPluginReload() {
    if (!shell.pluginReloading) return
    if (shell.pluginRegistry.scanning) {
      shell.pluginReloadPending = true
      return
    }
    if (typeof Qt.clearComponentCache === "function") Qt.clearComponentCache()
    shell.pluginRegistry.rescan()
  }""",
        """  function reloadPlugins() {
    Qt.callLater(shell.reloadShellGeneration)
  }

  function reloadShellGeneration() {
    Quickshell.reload(false)
  }""",
    )
    # Configuration changes use the same generation boundary. Applying a new
    # panel model inside the old generation reintroduces stale IPC handlers.
    replace_exact(
        shell_qml,
        "    onFileChanged: reload()",
        "    onFileChanged: shell.reloadPlugins()",
        count=2,
    )
    replace_exact(
        shell_qml,
        """    function reloadConfig(): string {
      userConfigFile.reload()
      return "ok"
    }""",
        """    function reloadConfig(): string {
      shell.reloadPlugins()
      return "ok"
    }""",
    )
    replace_exact(
        shell_qml,
        "    shellConfig = payload\n    userConfigFile.setText",
        "    userConfigFile.setText",
    )
    # Keep required properties available at creation. A distinct outer alias
    # avoids the upstream `shell: shell` binding resolving to Bar.shell itself.
    replace_exact(
        omarchy / "shell/shell.qml",
        "  id: shell\n",
        "  id: shell\n  readonly property var androidShellRoot: shell\n",
    )
    replace_exact(
        omarchy / "shell/shell.qml",
        """    Bar {
      omarchyPath: shell.omarchyPath
      barWidgetRegistry: shell.barWidgetRegistry
      barConfig: shell.barConfig
      shell: shell
      manifest: shell.barManifestFor(shell.defaultBarId)
    }""",
        """    Bar {
      omarchyPath: androidShellRoot.omarchyPath
      barWidgetRegistry: androidShellRoot.barWidgetRegistry
      barConfig: androidShellRoot.barConfig
      shell: androidShellRoot
      manifest: androidShellRoot.barManifestFor(androidShellRoot.defaultBarId)
    }""",
    )
    registry = omarchy / "shell/services/PluginRegistry.qml"
    notification = omarchy / "shell/plugins/notifications/Service.qml"
    replace_exact(notification, "var transient = false", "var ephemeralHint = false")
    replace_exact(notification, "transient = !!", "ephemeralHint = !!")
    replace_exact(notification, "transient = false }", "ephemeralHint = false }")
    replace_exact(notification, "return transient ||", "return ephemeralHint ||")
    style = omarchy / "shell/Commons/Style.qml"
    replace_exact(style, "hyprctlProc.running = true", "root.cornerRadius = 12")
    replace_exact(style, "gapsOutProc.running = true", "root.gapsOut = 0")
    replace_exact(
        style,
        'path: Quickshell.env("HOME") + "/.config/fontconfig/fonts.conf"',
        'path: Quickshell.env("FONTCONFIG_FILE")',
    )
    # The PinePhone package patches this separately when building its payload.
    replace_exact(
        registry,
        'property string pluginsDir: home + "/.config/omarchy/plugins"',
        'property string pluginsDir: Quickshell.env("MOARCHY_PATH") + "/plugins"',
    )

    config = {
        "version": 1,
        "idle": {"screensaver": 0, "lock": 0},
        "bar": {"id": "moarchy.bar", "position": "top", "layout": {}},
        "plugins": [
            {"id": "moarchy." + name}
            for name in ("gestures", "drawer", "recents", "shade", "themes", "splash")
        ],
    }
    # First-party services are enabled implicitly upstream. Disable unported ones.
    allowed = {"omarchy.notifications", "omarchy.osd"}
    config["disabledPlugins"] = sorted(
        {
            json.loads(path.read_text())["id"]
            for path in (omarchy / "shell/plugins").rglob("manifest.json")
        }
        - allowed
        - {"omarchy.bar"}
    )
    (omarchy / "config/omarchy/shell.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )
    licenses = bundle / "LICENSES"
    licenses.mkdir()
    shutil.copy2(REPO / "LICENSE", licenses / "moarchy-MIT.txt")
    shutil.copy2(source / "LICENSE", licenses / "omarchy-MIT.txt")
    keyboard = tomllib.loads((REPO / "manifest.toml").read_text())["moarchy-keyboard"]
    keyboard_archive = fetch(
        f"{keyboard['url']}/archive/{keyboard['ref']}.tar.gz",
        KEYBOARD_SHA256,
        REPO / f".cache/android/moarchy-keyboard-{keyboard['ref']}.tar.gz",
    )
    with tempfile.TemporaryDirectory(dir=bundle.parent) as work:
        keyboard_source = extract_verified(
            keyboard_archive,
            KEYBOARD_SHA256,
            Path(work) / "source",
            f"moarchy-keyboard-{keyboard['ref']}",
        )
        shutil.copytree(keyboard_source, bundle / "keyboard-source")
        shutil.copy2(keyboard_source / "LICENSE", licenses / "moarchy-keyboard-MIT.txt")
    (bundle / "SOURCES.json").write_text(
        json.dumps(
            {
                "omarchy": {"sha256": OMARCHY_SHA256},
                "moarchy-keyboard": {"ref": keyboard["ref"], "sha256": KEYBOARD_SHA256},
                "JetBrainsMonoNerdFont": {"version": "3.4.0", "sha256": FONT_SHA256},
            },
            indent=2,
        )
        + "\n"
    )
    fonts = fetch(
        "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.4.0/JetBrainsMono.tar.xz",
        FONT_SHA256,
        REPO / ".cache/android/JetBrainsMono-v3.4.0.tar.xz",
    )
    with tarfile.open(fonts) as tar:
        for name in ("Regular", "Bold", "SemiBold", "Italic"):
            member = tar.getmember(f"JetBrainsMonoNerdFont-{name}.ttf")
            if not member.isfile():
                raise ValueError("font artifact is not a regular file")
            (omarchy / "default/fonts" / Path(member.name).name).write_bytes(
                tar.extractfile(member).read()
            )
        licenses.joinpath("JetBrainsMono-OFL.txt").write_bytes(
            tar.extractfile("OFL.txt").read()
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / ".cache/android/dist")
    args = parser.parse_args()
    manifest = tomllib.loads((REPO / "manifest.toml").read_text())["omarchy"]
    patch = REPO / "pkgbuilds/omarchy-config/port-4x.patch"
    if digest(patch) != PORT_SHA256:
        raise ValueError("upstream Sway patch checksum changed; review the new pin")
    archive = fetch(
        f"{manifest['url']}/archive/{manifest['ref']}.tar.gz",
        OMARCHY_SHA256,
        REPO / f".cache/android/omarchy-{manifest['ref']}.tar.gz",
    )
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=args.output) as work:
        work = Path(work)
        source = extract_verified(
            archive, OMARCHY_SHA256, work / "source", f"omarchy-{manifest['ref']}"
        )
        bundle = work / "moarchy-android"
        assemble(source, bundle)
        release = release_digest(bundle)
        (bundle / "RELEASE").write_text(release + "\n")
        target = args.output / f"moarchy-android-{release[:12]}.tar.gz"
        with tarfile.open(work / "bundle.tar.gz", "w:gz", dereference=True) as tar:
            tar.add(bundle, arcname="moarchy-android")
        os.replace(work / "bundle.tar.gz", target)
        (target.with_suffix(target.suffix + ".sha256")).write_text(
            f"{digest(target)}  {target.name}\n"
        )
        print(target)


if __name__ == "__main__":
    main()
