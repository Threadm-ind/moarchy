#!/usr/bin/env bash
# In-guest session launcher, run as droid. Mirrors session.py _start's
# environment contract without systemd: dbus-run-session owns the session bus
# and session-entry (desktop.py) runs sway nested under Termux:X11's X server
# via the wlroots x11 backend with the pixman renderer.
# Readiness: autostart touches $XDG_RUNTIME_DIR/desktop-ready.
set -euo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8
if [ -z "${DISPLAY:-}" ]; then
  echo 'DISPLAY for the Termux:X11 server is required.' >&2
  exit 1
fi
root="$HOME/.local/share/moarchy-android"
release=$(readlink -f "$root/current")
if [ ! -d "$release" ]; then
  echo 'Moarchy is not installed; run guest-setup-user.sh first.' >&2
  exit 1
fi
keyboard="$root/profile/keyboard/usr/bin/moarchy-keyboard"
if [ ! -x "$keyboard" ]; then
  echo 'Touch keyboard missing; run guest-setup-user.sh first.' >&2
  exit 1
fi
runtime="$HOME/.runtime/moarchy-android"
mkdir -p -- "$runtime"
chmod 700 -- "$runtime"
if [ -e "$runtime/sway.sock" ]; then
  echo 'sway.sock exists; stop the previous session first.' >&2
  exit 1
fi
rm -f -- "$runtime/desktop-ready"
printf 'MOARCHY_ANDROID_ROOT=%s\n' "$root" > "$runtime/ROOT"
export OMARCHY_PATH="$release/omarchy" \
       MOARCHY_PATH="$release/moarchy" \
       MOARCHY_ANDROID_ROOT="$root" \
       MOARCHY_ANDROID_PROOT=1 \
       XDG_RUNTIME_DIR="$runtime"
exec dbus-run-session -- "$release/android/session-entry"
