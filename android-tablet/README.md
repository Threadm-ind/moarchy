# Moarchy tablet adaptation (proot Debian under Termux)

Target: HIGRACE OC101 (Allwinner A523, arm64-v8a, Android 13, bootloader locked).
The Pixel route (`android/`) rides Google's Terminal Debian VM, which only exists
on Android 15+; this layer gives the same desktop a different host on Android 13:

- Host: Termux + proot-distro Debian 13 (arm64) — no root, no bootloader changes,
  fully removable by uninstalling Termux.
- Display: Termux:X11's X server; sway runs nested via the wlroots **x11**
  backend with the **pixman** software renderer (same renderer baseline as the
  Pixel route; `desktop.py` selects the backend from `MOARCHY_ANDROID_PROOT=1`).
- Lifecycle: `guest-start.sh` replaces the systemd transient unit with
  `dbus-run-session -- session-entry`, same environment contract
  (`OMARCHY_PATH`, `MOARCHY_PATH`, `MOARCHY_ANDROID_ROOT`, `XDG_RUNTIME_DIR`,
  runtime `ROOT` marker, `desktop-ready` readiness marker, `sway.sock` guard).
- Privileges: proot has no setuid, so the apt block of `prepare-debian.sh` runs
  verbatim as root (`guest-setup-root.sh`) instead of via sudo; the per-user
  install and keyboard build stay byte-equivalent to `android/setup.sh`
  (`guest-setup-user.sh`) with the baseline check relaxed for proot
  (`install.py` honours `MOARCHY_ANDROID_PROOT=1`).

## Files

| Script | Runs where | Purpose |
|---|---|---|
| `bootstrap-termux.sh` | Termux | packages, Debian guest, bundle fetch over USB, both setup phases |
| `guest-setup-root.sh` | guest (root) | apt block of `prepare-debian.sh` + x11 backend libs + `droid` user |
| `guest-setup-user.sh` | guest (droid) | `install.py` + keyboard build, mirroring `android/setup.sh` |
| `guest-start.sh` | guest (droid) | systemd-free session launcher |
| `session.sh` | Termux | `start` / `stop` / `status` for the whole desktop |

## Expected behaviour

First start compiles nothing extra; the keyboard was built during bootstrap.
The desktop appears inside the Termux:X11 app window. Software rendering on the
A523 (2 GB RAM available) will not be fast; that is the known cost of this host.

## Out of scope / unverified

No Android root, bootloader unlocking, flashing or partition changes. Touch
behaviour, performance, audio, suspend/relaunch and clipboard sharing with
Android are device gates that only on-tablet testing can confirm.
