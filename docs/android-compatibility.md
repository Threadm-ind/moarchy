# Android and Pixel 10 compatibility

Assessed 2026-09-07. Fork:
<https://github.com/Threadm-ind/moarchy>. Upstream commit:
`4f4286761c41c31e6c92afb6594d9cf85ec9480c`.

## Current status

The fork now has a separate Debian guest installer, bundle builder and nested
desktop launcher under `android/`. The existing PinePhone image route is unchanged.
The new source is local and uncommitted; it is not yet available from the public
fork. There is no Android APK or Pixel boot image.

The phone screenshot supplied on 2026-09-07 establishes a working Debian 13.6
shell, `aarch64`, and `/usr/local/bin/enable_display` on Alex's Pixel 10, which
runs GrapheneOS on Android 17 (Alex, 2026-11-11).
Phone installation, display, input and lifecycle tests remain outstanding.

The first phone download was blocked by the computer's UFW firewall; a temporary
HTTPS transfer then passed full archive verification from the computer. The next
phone screenshot, at 03:16 on 2026-09-07, shows `tar` failing with `No space left
on device` while extracting themes. The original command used a temporary directory
under `/tmp` before setup could check free space in the user's home directory.
The archive plus its regular extracted files need 262,650,716 bytes before filesystem
overhead. With the exact supplied `&&` command, a failed extraction prevents setup.

Before another phone attempt, reconnect Terminal and inspect the affected filesystems:

```sh
df -h / /tmp "$HOME"
df -i /tmp "$HOME"
```

These commands only report usage. The screenshot alone does not establish whether
temporary storage, the main Linux filesystem or its inode limit is exhausted.
Use a unique staging directory under the real Debian home and check its free space
before any future download. Do not reset the Linux environment or delete broad
temporary-directory patterns to recover a single failed extraction.

The separate `scripts/android-download.py` now checks for 4 GiB free in the Debian
home before downloading. It creates its own directory there, verifies the pinned
archive size and SHA-256, and extracts with path and size limits. It stops after
extraction and does not run setup. This is a preparation margin, not a guarantee
of sufficient space for every package transaction. The original bundle is unchanged.
Five downloader regression tests bring the complete Python suite to 47 passing tests.

The desktop has rendered in a rootless Debian 13.6 **amd64** test environment:
Weston 14.0.2 hosts nested Sway 1.10.1 with software rendering, and Quickshell
0.3.0 loads the mobile shell. The original keyboard builds against Debian's
LayerShellQt after a compatibility patch and validates all five layout files.
These are local Debian results, not ARM64 or Pixel test results.

The final source bundle is `moarchy-android-2e19361818cc.tar.gz`, SHA-256
`1001a18880e81485b4c96bf2e4c781dcf05768989fe38a3653fd6739c4c17fa8`.
Native UI QA passed at 412×892, 768×1024 and 1280×800. Five plugin rescans,
a valid configuration file change and an explicit configuration reload retained
the working drawer, theme panel and terminal. Real pointer input confirmed search
focus after both configuration reload paths. Startup logs contained no duplicate
IPC handlers, invalid-context errors, crashes or fallback bar. This is native
QML/Wayland testing; browser accessibility and performance tools do not apply.

Evidence: `/tmp/moarchy-android-ui-qa/2e193-final-normal/result.json`, the screenshots
beside it, and `/tmp/moarchy-android-ui-qa/2e193-full/generation-reload.json`.
The terminal PID survived all reloads; the sandboxed GUI PID could not be sampled
reliably, so GUI process identity is not an independently verified result.

The 42 Android automated tests pass, covering installation ownership, upgrade
rollback, archive checks, session identity and failure handling. The assembled
bundle also passes checksum and content verification and an install/reinstall/
uninstall check with injected device facts. A separate live systemd probe confirms
that stopping the owned service kills its detached child while leaving an unrelated
process running. These checks do not substitute for installing on the phone.
All 22 bundled themes also pass Debian Foot's `--check-config` after rendering
with the port's template adapter, including dark and light themes.
The repeatable native check is `python3 tests/check_android_foot_themes.py BUNDLE.tar.gz`
in a Debian environment with Foot installed.

Moarchy's existing image targets the original PinePhone. In `image/build.sh`,
the root filesystem installs `device-pine64-pinephone`, and image assembly writes
the PinePhone Allwinner U-Boot SPL into a GPT disk image. This image is unsuitable
for flashing to a Pixel. The upstream README also reports camera and microphone
problems on its intended hardware. These are upstream reports, not local tests.

## Routes considered

| Route | Assessment |
| --- | --- |
| Native Pixel 10 dual boot | No verified ready port found. Requires a separate Pixel 10 kernel, drivers, boot and update integration effort before the desktop layer can be evaluated. |
| Google Terminal Linux VM | Selected route. A per-user Moarchy session runs inside the supplied Debian guest, nested under the existing display server. Android continues running underneath. |
| Termux / PRoot / Termux:X11 | Possible broader Android fallback. A separate adaptation is needed because PRoot lacks real root, normal systemd supervision and kernel access. A working XFCE example does not establish Sway or Moarchy compatibility. |

Android's A/B slots are for operating-system updates and fallback. They do not
provide an independent second OS installation. Do not repurpose them as a generic
dual-boot installer.

## Evidence and limits

- [Moarchy source and documented limitations](https://github.com/SimonSchubert/moarchy)
- [AOSP A/B update design](https://source.android.com/docs/core/ota/ab)
- [postmarketOS port repository](https://gitlab.postmarketos.org/postmarketOS/pmaports): the research check of the main archive found no Pixel 10 `frankel` device package/path. This does not prove no experimental port exists elsewhere.
- [AOSP Linux VM use case](https://source.android.com/docs/core/virtualization/usecases): the Linux development environment uses a Debian guest.
- [Android 16 QPR2 GUI announcement](https://developer.android.com/blog/posts/android-16-qpr-2-is-released)
- [Android 16 QPR2 supported devices](https://developer.android.com/about/versions/16/qpr2/get): includes Pixel 10. Support for the OS release does not independently prove its Terminal feature is enabled on this particular phone.
- [AOSP Terminal and custom VM documentation](https://android.googlesource.com/platform/packages/modules/Virtualization/+/HEAD/docs/custom_vm.md): source documentation can be ahead of production builds; custom VM debug access must not be assumed on stock Android.
- [Android 17 release-tag Terminal documentation](https://android.googlesource.com/platform/packages/modules/Virtualization/+/refs/tags/android-17.0.0_r1/docs/custom_vm.md): the GUI entry is the Display button. Hardware acceleration has a settings option on supported devices. Replacing the existing Weston desktop is documented as experimental; do not automatically edit Google's display helpers.
- [Debian Sway package](https://packages.debian.org/trixie/sway): version `1.10.1-2` is published for ARM64 in Debian 13.
- [Debian ARM64 backports index](https://deb.debian.org/debian/dists/trixie-backports/main/binary-arm64/Packages.xz): a direct index check found `quickshell` version `0.3.0-1~bpo13+1` for ARM64, requiring Qt 6.8.2 private ABI packages. This proves package availability, not compatibility with Moarchy's complete QML shell. Evidence: `/tmp/moarchy-android-package-evidence/quickshell-arm64.json`.
- [Debian scrcpy backport](https://packages.debian.org/trixie-backports/scrcpy): `3.3.4-1~bpo13+1` in `contrib` for ARM64; [its server fetcher](https://sources.debian.org/src/scrcpy/3.3.4-1~bpo13+1/debian/scrcpy-update-server) pins the upstream server checksum. Debian `adb` is `1:34.0.5-12` in trixie main.
- [scrcpy 3.3.4 virtual displays](https://github.com/Genymobile/scrcpy/blob/v3.3.4/doc/virtual_display.md) and [its app-list format](https://github.com/Genymobile/scrcpy/blob/v3.3.4/server/src/main/java/com/genymobile/scrcpy/util/LogUtils.java): the parser follows that 30-column layout, and an explicit display size without DPI makes scrcpy scale the main display's density.
- [GrapheneOS features](https://grapheneos.org/features#network-permission-toggle): the Network permission also guards localhost, and [auto reboot](https://grapheneos.org/features#auto-reboot) defaults to 18 locked hours. [Developer options are Owner-only and device-wide](https://discuss.grapheneos.org/d/4231-developer-settings-and-usb-debugging-on-user-profiles/2); [scrcpy reaches only the Owner profile](https://github.com/Genymobile/scrcpy/issues/6201).
- [PRoot-Distro limitations](https://github.com/termux/proot-distro/blob/master/README.md)
- [Termux:X11](https://github.com/termux/termux-x11)

The phone's exact Android 17 build, display behavior, available storage and user
service manager remain unverified. Native calling, cameras, Bluetooth, brightness
and device power stay with Android. This guest desktop does not claim to control
those phone facilities. Audio and graphics acceleration require device testing.

## Installation design

The installer requires Debian 13 ARM64 and the Terminal display helper. It uses
signed Debian packages and Quickshell `0.3.0-1~bpo13+1` from trixie-backports.
`android/setup.sh` builds the supplied pinned keyboard source inside the guest.
Build instructions are in [android/README.md](../android/README.md).

Payloads live under `~/.local/share/moarchy-android/releases/`; writable files
live under its `profile/`. The installer reserves `~/.config/omarchy` and
`~/.local/state/omarchy` as exact owned symlinks and refuses existing unmanaged
paths. It does not replace Google display helpers or install the PinePhone's
system services, profile scripts, sudoers rules or bootloader.

One transient user service owns the desktop, its private D-Bus session and its
children. Starting requires a working user service manager and the explicit
parent Wayland socket. Readiness requires both a responding compositor and the
loaded mobile shell. Stop targets that service; it never kills Quickshell by name.

Android apps stay on Android. `moarchy-android-apps` adds one launcher entry per
launchable app reported by `scrcpy --list-apps` and opens each app on its own
Android virtual display with `scrcpy --new-display=WxH --start-app=PACKAGE`,
sized to the focused Sway workspace. The guest reaches the phone's adbd over
Wireless debugging after a one-time `adb pair`. Generated entries use the
`moarchy-android-app-` prefix in the session's data directory; a sync removes
only stale entries with that prefix and changes nothing when the listing fails.
Setup adds Debian `adb`, `libnotify-bin`, `curl` and `scrcpy` `3.3.4-1~bpo13+1`
from trixie-backports `contrib`. That package's postinst downloads the upstream
`scrcpy-server` and verifies its pinned SHA-256.

Unverified on the phone: whether the VM can reach adbd at the phone's Wi-Fi
address through Terminal's network, touch and keyboard input in the scrcpy
window, video latency with software rendering, and how Android 17 shows an
already-running app or the IME on a virtual display. Android notifications do
not reach the desktop shade yet.

## Guest checker

The local `scripts/android-check.sh` reads selected OS metadata, architecture,
kernel/page size and command/display availability. It installs nothing and does
not launch a desktop, source display helpers, read credentials, or send data.

```sh
bash scripts/android-check.sh
```

Exit 0 means only that the guest reports Debian/aarch64 and exposes
`enable_display`. Exit 1 means those checks need attention; a missing helper is
not proof that the phone lacks graphical support. Exit 2 means incorrect command
arguments. Every diagnostic report labels the desktop as unverified.

The script and its tests are local, uncommitted changes and are not yet available
from the public fork. The tests use synthetic guest data. A local Omarchy/x86_64
run was rejected as expected; neither test establishes Pixel compatibility.

Before claiming Pixel support, prove the built bundle installs on the actual
phone, accepts touch and keyboard input, switches themes, launches applications,
stops and restarts, and uninstalls without disturbing Android or other guest files.
Compatibility claims must name tested Android builds and devices; universal
issue-free installation cannot be established from a source fork.
