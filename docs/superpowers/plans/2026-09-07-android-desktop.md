# Moarchy in Android Terminal

Target: Alex's Pixel 10 running Android 17. The phone screenshot dated 2026-09-07 establishes Debian 13.6, aarch64 and `/usr/local/bin/enable_display`. Display and user-systemd capability still require device evidence. Android remains the host OS; this is a guest desktop, not native dual boot.

The implementation preserves Moarchy's drawer, gestures, recents and theme system inside Sway nested under Terminal's existing display server. Do not flash images, change vendor display helpers, or install PinePhone services. Keep the original Arch/PinePhone route intact.

## Implementation

1. Add `scripts/android-build.py` and behavior tests in `tests/test_android_build.py`. Verify the pinned Omarchy archive, safely extract into staging, apply the existing Sway port, overlay the mobile plugins and Android adapters, and produce a self-contained source bundle with its licenses. Missing inputs, changed pins and unsafe archive members must fail before publication of a bundle.
2. Add `android/install.py` and installer tests. Reserve per-user payload, config and state directories. Claim only exact owned legacy Omarchy symlinks, reject existing directories and dangling links, roll back partial claims, and retain user state on repeat installs. Install signed Debian package prerequisites in the guest with an explicit preparation command; avoid global Omarchy profile, sudoers and application configuration changes.
3. Add `android/session.py` and session tests. Expose start/status/stop through one named transient user service with a private D-Bus session, private runtime directory and cgroup cleanup. Validate service ownership, serialize lifecycle operations, use the explicit parent Wayland socket, pin the running release, and check Sway readiness. Do not import environment into the user manager or kill processes by name.
4. Add Android Sway configuration and narrowly scoped helper overrides under `android/`. Preserve existing mobile UI, retain the original keyboard through a pinned build, replace Arch package/host hardware actions with accurate guest actions, and reuse the upstream theme renderer without its unrelated application writes.

## Verification and delivery

- Run each behavior test red before implementation, then green. Keep full logs under `/tmp/moarchy-android-*`.
- Use the isolated Debian 13.6 amd64 sandbox for package, shell, theme and compositor checks. This validates Debian behavior, not ARM64 or Pixel acceleration.
- Render the actual QML desktop at phone, tablet and desktop dimensions; inspect QML geometry/text overflow and exercise drawer, gestures, themes and app launch. Run independent UI QA before claiming the desktop complete.
- Test service isolation separately where a user manager exists; record any sandbox limitation honestly. On the Pixel, verify Display, installation, start/stop/relaunch, keyboard and input, theme switching and application launch.
- Update `docs/android-compatibility.md` and install documentation with verified results and concrete remaining limitations. Keep package artifacts outside Git and preserve upstream MIT notices. Do not advertise 100% compatibility without device evidence.
- Do not commit, push or publish new source without Alex's request. Provide a locally built artifact and an exact installation route that actually exists.
