#!/usr/bin/env bash
# Run inside Android Terminal's Debian guest before the per-user installer.
set -euo pipefail
if [[ ${1-} == --help && $# == 1 ]]; then
  printf 'Usage: bash android/prepare-debian.sh\nInstall signed Debian dependencies and compile the bundled touch keyboard.\n'
  exit 0
fi
if (( $# )); then printf 'Unexpected argument. Use --help.\n' >&2; exit 2; fi
android_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 - "$android_dir" <<'PY'
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from install import _require_baseline, detect_facts
_require_baseline(detect_facts())
PY
if (( EUID == 0 )); then
  printf 'Run this as the normal droid user; it invokes sudo only for Debian packages.\n' >&2
  exit 1
fi
available=$(df -B1 --output=avail "$HOME" | tail -1 | tr -d ' ')
if (( available < 3221225472 )); then
  printf 'At least 3 GiB free is required for dependencies and the keyboard build. Increase the Linux disk in Terminal settings, then retry.\n' >&2
  exit 1
fi
source_file=/etc/apt/sources.list.d/moarchy-backports.sources
source_text='Types: deb
URIs: https://deb.debian.org/debian
Suites: trixie-backports
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg'
if [[ -e $source_file || -L $source_file ]]; then
  if [[ -L $source_file || $(cat "$source_file") != "$source_text" ]]; then
    printf 'Existing %s differs; no repository configuration was changed.\n' "$source_file" >&2
    exit 1
  fi
else
  printf '%s\n' "$source_text" | sudo tee "$source_file" >/dev/null
fi
sudo apt-get update
packages=(sway swaybg foot dbus dbus-x11 inotify-tools jq procps wayland-utils grim
  libgtk-3-bin fonts-noto-color-emoji adwaita-icon-theme ca-certificates python3 xz-utils
  firefox-esr nautilus gnome-text-editor
  qml6-module-qtquick-templates qml6-module-qtqml-workerscript
  build-essential cmake ninja-build pkgconf patch qt6-base-dev qt6-declarative-dev
  qt6-wayland-dev liblayershellqtinterface-dev libwayland-dev libxkbcommon-dev)
for package in "${packages[@]}"; do apt-cache show "$package" >/dev/null; done
sudo apt-get install -y "${packages[@]}" quickshell=0.3.0-1~bpo13+1
printf 'Debian packages prepared. Continue with: python3 %q %q\n' "$android_dir/install.py" "$(dirname -- "$android_dir")"
