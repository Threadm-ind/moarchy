#!/usr/bin/env bash
# Guest-side privileged preparation, run as root inside the proot Debian guest.
# Packages come from a laptop-fetched arm64 repo bind-mounted at /host-home/debs
# (file:// — no DNS, no loopback getaddrinfo).
set -euo pipefail
if [ "$(id -u)" != 0 ]; then
  echo 'Run as root inside the proot Debian guest.' >&2
  exit 1
fi

debs=/host-home/debs
if [ ! -f "$debs/Packages" ]; then
  echo "Local package repo missing: $debs/Packages" >&2
  exit 1
fi

mkdir -p /etc/apt/apt.conf.d /etc/apt/sources.list.d
cat > /etc/apt/apt.conf.d/99-tablet-offline <<'EOF'
Acquire::Max-FutureTime "86400";
APT::Install-Recommends "false";
EOF
if [ -f /etc/apt/sources.list ]; then
  sed -i 's/^deb /# deb /' /etc/apt/sources.list
fi
rm -f /etc/apt/sources.list.d/debian.sources \
      /etc/apt/sources.list.d/debian-security.sources \
      /etc/apt/sources.list.d/moarchy-backports.sources
printf 'deb [trusted=yes] file:%s ./\n' "$debs" > /etc/apt/sources.list.d/local-debs.list

apt-get update
packages=(sway swaybg foot dbus dbus-x11 inotify-tools jq procps wayland-utils grim
  libgtk-3-bin fonts-noto-color-emoji adwaita-icon-theme ca-certificates python3 xz-utils
  firefox-esr nautilus gnome-text-editor
  qml6-module-qtquick-templates qml6-module-qtqml-workerscript
  build-essential cmake ninja-build pkgconf patch qt6-base-dev qt6-declarative-dev
  qt6-wayland-dev liblayershellqtinterface-dev libwayland-dev libxkbcommon-dev)
apt-get install -y --no-install-recommends "${packages[@]}" quickshell
apt-get install -y --no-install-recommends \
  libxcb-icccm4 libxcb-keysyms1 libxcb-xinput0 libxcb-cursor0 libxkbcommon-x11-0

id droid >/dev/null 2>&1 || useradd -m -s /bin/bash droid
printf 'Root preparation complete.\n'
