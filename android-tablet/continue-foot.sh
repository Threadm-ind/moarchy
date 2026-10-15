#!/data/data/com.termux/files/usr/bin/bash
# Open Foot inside the running Sway session (no touch required).
set -euo pipefail
proot-distro login debian --user droid --shared-tmp \
  -- env SWAYSOCK=/home/droid/.runtime/moarchy-android/sway.sock \
     swaymsg exec foot
echo 'swaymsg exec foot sent'
