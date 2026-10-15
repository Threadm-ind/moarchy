#!/data/data/com.termux/files/usr/bin/bash
# Termux-side bootstrap for the Moarchy tablet adaptation (OC101, Android 13).
# Internet flows through the laptop: http_proxy -> adb reverse tcp:8888.
# The pinned bundle flows over USB:  http://127.0.0.1:8766 (adb reverse).
# This adaptation layer itself is fetched from: http://127.0.0.1:8767.
set -euo pipefail
BUNDLE=${BUNDLE:-moarchy-android-2e19361818cc}
mkdir -p "$PREFIX/etc/apt/apt.conf.d"
echo 'Acquire::Max-FutureTime "86400";' > "$PREFIX/etc/apt/apt.conf.d/99-future-time"
SRC=${SRC:-http://127.0.0.1:8767}
: "${http_proxy:=http://127.0.0.1:8888}"
export http_proxy https_proxy="$http_proxy"

echo '== Fetching tablet adaptation scripts =='
cd "$HOME"
for script in bootstrap-termux.sh guest-setup-root.sh guest-setup-user.sh guest-start.sh session.sh continue-user.sh install.py desktop.py; do
  curl -fsSL --connect-timeout 5 -O "$SRC/$script"
  chmod +x "$script"
done

echo '== Termux packages (via laptop proxy) =='
pkg update -y
pkg install -y proot-distro x11-repo
pkg update -y
pkg install -y termux-x11-nightly

echo '== Debian proot guest =='
proot-distro install debian || echo 'debian guest already present'

echo '== Fetching pinned bundle over USB =='
mkdir -p "$HOME/moarchy-bundle"
cd "$HOME/moarchy-bundle"
curl -fL --connect-timeout 5 -O "http://127.0.0.1:8766/$BUNDLE.tar.gz"
curl -fL --connect-timeout 5 -O "http://127.0.0.1:8766/$BUNDLE.tar.gz.sha256"
sha256sum -c "$BUNDLE.tar.gz.sha256"

echo '== Fetching local Debian repo over USB =='
curl -fL --connect-timeout 5 -o "$HOME/debs.tar.gz" http://127.0.0.1:8768/debs.tar.gz
rm -rf "$HOME/debs"
mkdir -p "$HOME/debs"
tar -xzf "$HOME/debs.tar.gz" -C "$HOME/debs"
test -f "$HOME/debs/Packages"

echo '== Guest privileged preparation (root inside proot) =='
printf '127.0.0.1\tlocalhost proxy\n::1\tlocalhost ip6-localhost ip6-loopback\n' > "$HOME/guest-hosts"
proot-distro login debian \
  --bind /data/data/com.termux/files/home:/host-home \
  --bind /data/data/com.termux/files/home/guest-hosts:/etc/hosts \
  -- bash /host-home/guest-setup-root.sh

echo '== Guest per-user install (droid inside proot) =='
proot-distro login debian --user droid \
  --bind /data/data/com.termux/files/home:/host-home \
  --bind /data/data/com.termux/files/home/guest-hosts:/etc/hosts \
  -- bash /host-home/guest-setup-user.sh "/host-home/moarchy-bundle/$BUNDLE.tar.gz"

echo 'Bootstrap complete. Start the desktop with: bash ~/session.sh start'
