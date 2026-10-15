#!/data/data/com.termux/files/usr/bin/bash
# Install the missing Qt Wayland platform plugin into the proot guest.
set -euo pipefail
DEB=qt6-wayland_6.8.2-4_arm64.deb
curl -fsSL --connect-timeout 5 -o "$HOME/debs/$DEB" "http://127.0.0.1:8768/pool/$DEB"
curl -fsSL --connect-timeout 5 -o "$HOME/debs/Packages" "http://127.0.0.1:8768/pool/Packages"
proot-distro login debian \
  --bind /data/data/com.termux/files/home:/host-home \
  -- bash -c 'apt-get update && apt-get install -y --no-install-recommends qt6-wayland'
echo 'qt6-wayland installed. Restart with: bash ~/session.sh stop; bash ~/session.sh start'
