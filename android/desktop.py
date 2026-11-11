"""Prepare owned desktop configuration and await the nested compositor."""

import json
import os
from pathlib import Path
import shlex
import subprocess
from xml.sax.saxutils import escape


def main():
    env = dict(os.environ)
    tablet = os.environ.get("MOARCHY_ANDROID_PROOT") == "1"
    root = Path(env["MOARCHY_ANDROID_ROOT"])
    omarchy = Path(env["OMARCHY_PATH"])
    moarchy = Path(env["MOARCHY_PATH"])
    runtime = Path(env["XDG_RUNTIME_DIR"])
    profile = root / "profile"
    android = Path(__file__).resolve().parent
    env.update(
        PATH=f"{omarchy}/bin:{moarchy}/bin:{profile}/keyboard/usr/bin:/usr/bin:/bin",
        MOARCHY_KEYBOARD_DATA_DIR=str(profile / "keyboard/usr/share"),
        XDG_CONFIG_HOME=str(profile / "app-config"),
        XDG_CACHE_HOME=str(profile / "cache"),
        XDG_STATE_HOME=str(profile / "app-state"),
        WLR_BACKENDS="x11" if tablet else "wayland",
        WLR_RENDERER="pixman",
        **({"WAYLAND_DISPLAY": env["MOARCHY_PARENT_DISPLAY"]} if not tablet else {}),
        SWAYSOCK=str(runtime / "sway.sock"),
        XDG_CURRENT_DESKTOP="sway",
        XDG_SESSION_TYPE="wayland",
        QT_QPA_PLATFORM="wayland",
        QT_QUICK_BACKEND="software",
        QT_STYLE_OVERRIDE="Basic",
        QT_QUICK_CONTROLS_STYLE="Basic",
    )
    # A software renderer is the portable baseline; accelerated rendering needs
    # a separate verified device option. Never select the host DRM/input backend.
    if not tablet:
        env.pop("DISPLAY", None)
    env.pop("WAYLAND_SOCKET", None)
    for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        Path(env[name]).mkdir(parents=True, exist_ok=True)
    if (runtime / "sway.sock").exists():
        raise RuntimeError(
            "owned Sway socket already exists; stop the previous session first"
        )
    fontconfig = profile / "fontconfig.xml"
    fontconfig.write_text(
        '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig><include>/etc/fonts/fonts.conf</include>"
        f"<dir>{escape(str(omarchy / 'default/fonts'))}</dir>"
        "<alias><family>monospace</family><prefer><family>JetBrainsMono Nerd Font</family></prefer></alias>"
        "</fontconfig>\n"
    )
    env["FONTCONFIG_FILE"] = str(fontconfig)
    if not (profile / "state/current/theme/colors.toml").is_file():
        subprocess.run(
            [str(omarchy / "bin/omarchy-theme-set"), "Tokyo Night"], env=env, check=True
        )
    foot = profile / "foot.ini"
    foot.write_text(
        "[main]\n" + f"include={profile}/state/current/theme/foot.ini\n"
        "font=JetBrainsMono Nerd Font:size=10\npad=12x12\n"
        "[scrollback]\nlines=10000\n"
    )
    data = profile / "data"
    apps = data / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    # Desktop entries live in the session data namespace and never replace the
    # guest's normal launchers. gtk-launch remains on the private session bus.
    for slug, name, icon, command in [
        ("terminal", "Terminal", "foot", ["moarchy-launch-terminal"]),
        (
            "themes",
            "Themes",
            str(omarchy / "icon.png"),
            ["omarchy-shell", "themes", "open"],
        ),
        (
            "sync-android",
            "Sync Android Apps",
            "phone",
            ["moarchy-android-apps", "sync"],
        ),
    ]:
        (apps / f"moarchy-android-{slug}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nIcon={icon}\nExec={' '.join(command)}\n"
        )
    env["XDG_DATA_HOME"] = str(data)
    config = runtime / "sway.conf"
    quote = lambda value: json.dumps(str(value))
    lines = [
        "set $mod Mod4",
        "xwayland disable",
        "gaps inner 0",
        "gaps outer 0",
        "default_border pixel 2",
        "default_floating_border pixel 2",
        "hide_edge_borders smart",
        "font pango:JetBrainsMono Nerd Font 10",
        "default_orientation vertical",
        "output * scale 1",
        f"output * bg {quote(profile / 'state/current/background')} fill",
        "seat * hide_cursor 3000",
        f"include {quote(profile / 'state/current/theme/sway.conf')}",
        "bindsym $mod+Return exec moarchy-launch-terminal",
        "bindsym $mod+space exec omarchy-shell drawer open",
        "bindsym $mod+t exec omarchy-shell themes open",
        "bindsym $mod+w kill",
        "bindsym $mod+Shift+e exit",
        "bindsym $mod+Left workspace prev_on_output",
        "bindsym $mod+Right workspace next_on_output",
        "bindsym $mod+i exec moarchy-toggle-keyboard",
        f"exec {shlex.quote(str(android / 'autostart'))}",
    ]
    for number in range(1, 10):
        lines.append(f"bindsym $mod+{number} workspace number {number}")
    config.write_text("\n".join(lines) + "\n")
    # Sway exports its new Wayland display to the autostart children. Its parent
    # connection remains the explicit absolute Weston socket in this environment.
    return subprocess.call(["sway", "-d", "-c", str(config)], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
