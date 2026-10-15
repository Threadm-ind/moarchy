#!/data/data/com.termux/files/usr/bin/bash
# Resume after guest root setup: overlay patched install.py/desktop.py and
# run the per-user install + keyboard build as droid.
set -euo pipefail
BUNDLE=${BUNDLE:-moarchy-android-2e19361818cc}
SRC=${SRC:-http://127.0.0.1:8767}
cd "$HOME"
for f in guest-setup-user.sh install.py desktop.py; do
  curl -fsSL --connect-timeout 5 -O "$SRC/$f"
  chmod +x "$f" 2>/dev/null || true
done
proot-distro login debian --user droid \
  --bind /data/data/com.termux/files/home:/host-home \
  -- bash /host-home/guest-setup-user.sh "/host-home/moarchy-bundle/$BUNDLE.tar.gz"
echo 'User install complete. Start with: bash ~/session.sh start'
