# Moarchy inside Android Terminal

This port runs the Moarchy mobile desktop inside Android's Debian Linux VM.
Android stays running. It does not install a second bootable operating system.

The target is Debian 13 ARM64 with Google's Terminal display helper. Alex's
Pixel 10 on Android 17 reports this guest environment. Local Debian amd64 tests
do not establish working installation or graphics on that phone.

## Build the bundle

On a development machine with Python 3.12+ and `patch`:

```sh
python3 scripts/android-build.py
```

The builder downloads pinned upstream archives, checks their SHA-256 digests,
applies the Sway and Debian adaptations in staging, and writes a source bundle
and checksum file to `.cache/android/dist/`. It never runs an OS installer.
Upstream Omarchy, Moarchy, keyboard and font licenses accompany the bundle.

## Install in the phone's Debian terminal

Allow at least 3 GiB free in the Linux disk for packages and the keyboard build.
Increase the Linux disk allocation in Terminal settings if needed. Obtain the
built archive and its matching checksum file from the builder. With both files
in the same directory, substitute the actual bundle name below:

```sh
sha256sum -c moarchy-android-RELEASE.tar.gz.sha256
tar -xzf moarchy-android-RELEASE.tar.gz
bash moarchy-android/android/setup.sh
```

Run setup as the normal `droid` user. It invokes `sudo` for Debian packages,
then installs the desktop and compiles its keyboard as the user. Existing
unmanaged Omarchy files cause a refusal. Review those files yourself instead
of deleting them to bypass the check.

Open Terminal's Display using its monitor button. From a shell that has the
parent display in `WAYLAND_DISPLAY`:

```sh
~/.local/bin/moarchy-android start
~/.local/bin/moarchy-android status
~/.local/bin/moarchy-android stop
```

If the Terminal shell does not expose `WAYLAND_DISPLAY`, identify the socket
used by its display helper and pass its absolute path with `start --display`.
Do not pick an arbitrary socket from another session. The launcher checks that
the path is an existing Unix socket and that a user service manager is available.

The top bar opens desktop controls; the bottom gestures open apps and recent
windows. Phone hardware controls remain in Android. With a hardware keyboard,
Super+Return opens Terminal, Super+Space opens Apps, Super+T opens Themes,
Super+I toggles the touch keyboard and Super+Shift+E closes the desktop.

## Stop, remove and troubleshoot

```sh
~/.local/bin/moarchy-android stop
~/.local/bin/moarchy-android uninstall
```

Uninstall removes owned links and the launcher and retains profile data and
downloaded releases. Debian packages installed by setup remain available to
other guest applications. The installer does not alter Android partitions.

Read service logs with:

```sh
journalctl --user -u moarchy-android-session.service -b --no-pager
```

Closing the launching shell does not intentionally close the desktop. Explicit
stop does. If Android stops the VM, reopen Terminal and start a new desktop
session. That behavior still needs verification on the actual phone.

The baseline uses software rendering. Hardware acceleration, audio, physical
touch behavior, clipboard sharing with Android and suspend/relaunch behavior
are device test gates. This is not a claim of issue-free support for every
modern Android phone. See [the compatibility record](../docs/android-compatibility.md).
