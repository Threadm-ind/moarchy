#!/usr/bin/env bash
set -euo pipefail
if [[ ${1-} == --help && $# == 1 ]]; then
  printf 'Usage: bash android/setup.sh\nPrepare Debian packages, install Moarchy, and build its touch keyboard.\n'
  exit 0
fi
if (( $# )); then printf 'Unexpected argument. Use --help.\n' >&2; exit 2; fi
android_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bundle_dir=$(dirname -- "$android_dir")
bash "$android_dir/prepare-debian.sh"
python3 "$android_dir/install.py" "$bundle_dir"
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
if [[ -x $keyboard_root/usr/bin/moarchy-keyboard && -f $keyboard_root/.source && $(cat "$keyboard_root/.source") == "$fingerprint" ]]; then
  printf 'Touch keyboard is already built.\n'
else
  stage=$(mktemp -d "$install_root/profile/keyboard-stage.XXXXXX")
  trap 'rm -rf -- "$stage"' EXIT
  bash "$android_dir/keyboard-build.sh" "$bundle_dir/keyboard-source" "$stage"
  MOARCHY_KEYBOARD_DATA_DIR="$stage/usr/share" QT_QPA_PLATFORM=offscreen "$stage/usr/bin/moarchy-keyboard" --check-layouts
  printf '%s\n' "$fingerprint" > "$stage/.source"
  if [[ -e $keyboard_root ]]; then
    if [[ ! -f $keyboard_root/.source || -L $keyboard_root ]]; then
      printf 'Refusing to replace an unmanaged keyboard directory: %s\n' "$keyboard_root" >&2
      exit 1
    fi
    previous=$(mktemp -d "$install_root/profile/keyboard-previous.XXXXXX")
    rmdir "$previous"
    mv -- "$keyboard_root" "$previous"
    if ! mv -- "$stage" "$keyboard_root"; then mv -- "$previous" "$keyboard_root"; exit 1; fi
    rm -rf -- "$previous"
  else
    mv -- "$stage" "$keyboard_root"
  fi
fi
printf '\nInstalled. Open Terminal’s Display, then run:\n  ~/.local/bin/moarchy-android start\n'
