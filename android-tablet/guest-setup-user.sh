#!/usr/bin/env bash
# Guest-side per-user install, run as droid inside the proot Debian guest.
# Mirrors android/setup.sh lines 11-43 (install.py plus the keyboard build),
# with the proot baseline override enabled instead of prepare-debian.sh.
set -euo pipefail
export MOARCHY_ANDROID_PROOT=1
bundle_tar=${1:?Usage: guest-setup-user.sh /host-home/moarchy-bundle/<bundle>.tar.gz}
bundle_dir_dirname=$(dirname -- "$bundle_tar")
(cd "$bundle_dir_dirname" && sha256sum -c "$(basename -- "$bundle_tar").sha256")

build="$HOME/build"
rm -rf -- "$build"
mkdir -p -- "$build"
tar -xzf "$bundle_tar" -C "$build"
bundle_dir="$build/moarchy-android"
cp /host-home/install.py "$bundle_dir/android/install.py"
cp /host-home/desktop.py "$bundle_dir/android/desktop.py"
python3 "$bundle_dir/android/install.py" "$bundle_dir"

install_root="$HOME/.local/share/moarchy-android"
keyboard_root="$install_root/profile/keyboard"
fingerprint=$(python3 - "$bundle_dir" <<'PY'
import hashlib, json, platform, sys
from pathlib import Path
bundle = Path(sys.argv[1])
pin = json.loads((bundle / 'SOURCES.json').read_text())['moarchy-keyboard']['sha256']
print(hashlib.sha256(pin.encode() + (bundle / 'android/keyboard-debian.patch').read_bytes() + platform.machine().encode()).hexdigest())
PY
)
if [ -x "$keyboard_root/usr/bin/moarchy-keyboard" ] \
   && [ -f "$keyboard_root/.source" ] \
   && [ "$(cat "$keyboard_root/.source")" = "$fingerprint" ]; then
  printf 'Touch keyboard is already built.\n'
else
  stage=$(mktemp -d "$install_root/profile/keyboard-stage.XXXXXX")
  trap 'rm -rf -- "$stage"' EXIT
  bash "$bundle_dir/android/keyboard-build.sh" "$bundle_dir/keyboard-source" "$stage"
  MOARCHY_KEYBOARD_DATA_DIR="$stage/usr/share" QT_QPA_PLATFORM=offscreen \
    "$stage/usr/bin/moarchy-keyboard" --check-layouts
  printf '%s\n' "$fingerprint" > "$stage/.source"
  if [ -e "$keyboard_root" ]; then
    if [ ! -f "$keyboard_root/.source" ] || [ -L "$keyboard_root" ]; then
      printf 'Refusing to replace an unmanaged keyboard directory: %s\n' "$keyboard_root" >&2
      exit 1
    fi
    previous=$(mktemp -d "$install_root/profile/keyboard-previous.XXXXXX")
    rmdir -- "$previous"
    mv -- "$keyboard_root" "$previous"
    if ! mv -- "$stage" "$keyboard_root"; then
      mv -- "$previous" "$keyboard_root"
      exit 1
    fi
    rm -rf -- "$previous"
  else
    mv -- "$stage" "$keyboard_root"
  fi
fi
printf '\nInstalled. Start the desktop from Termux with: bash ~/session.sh start\n'
