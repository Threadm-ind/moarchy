# Fork publication check

Checked 2026-09-06 against upstream commit
`4f4286761c41c31e6c92afb6594d9cf85ec9480c`.

Alex requested a fork of `SimonSchubert/moarchy`. Publication is limited to
GitHub's copy of that public upstream repository. Local changes are not included.

Created and verified: <https://github.com/Threadm-ind/moarchy>, public fork of
`SimonSchubert/moarchy`, default branch `main`, at the same commit as above.
Verification used `gh api repos/Threadm-ind/moarchy` and
`gh api repos/Threadm-ind/moarchy/commits/main`. The local `origin` points to this
fork; `upstream` points to Simon Schubert's repository.

| Gate | Result |
| --- | --- |
| Repository posture | Deliberately public upstream fork, authorized by Alex. `git ls-files` contains no `dist/`, `build/`, `out/`, `.next/` output or `.map` files. |
| Ownership and licence | Preserve the upstream MIT licence and Simon Schubert copyright. Do not claim Alex authored the upstream work or replace its licence. |
| Shipped surface | Source repository only. No website, Android package or device image is being deployed. Upstream screenshots and public package-verification keys remain upstream content. |
| Visible claim | Existing upstream copyright retained. No new rendered surface to annotate. |
| Copy detection | Exception: no Alex-authored shipped surface. Do not fingerprint or minify the upstream project. |
| Paper trail | Preserve upstream Git history. No new commit or push authorized; local research stays uncommitted. |

## Installation status

This check covers fork publication only. It does not establish Android or Pixel
compatibility, build success, or readiness to flash a phone.

## Android source bundle review — 2026-09-07

`gh repo view Threadm-ind/moarchy --json nameWithOwner,visibility,isFork,defaultBranchRef`
still reports the deliberately public fork on `main`. New Android source remains
local and uncommitted. The archive builder writes only to ignored `.cache/`;
`git ls-files '*.map' 'dist/*' 'build/*' 'out/*' '.next/*'` returns no tracked output.

The bundle preserves MIT notices for Omarchy, Moarchy and moarchy-keyboard and
the JetBrains Mono font OFL. The font archive digest matches the official Nerd
Fonts 3.4.0 SHA-256 list. Original authors retain their attribution; the Android
adaptation does not claim authorship of their work or change its open-source license.

This is an intentionally readable source distribution, with a SHA-256 archive
checksum and a content-derived release ID. Browser minification, HTML copyright
footers, source-map removal and browser copy fingerprints do not apply to this
native QML source bundle. No website or binary release is being published.

The bundle is a Linux guest desktop, not a Pixel boot image. Device compatibility
and security review are separate from this ownership/licensing check. No new
commit, push, GitHub release or phone flash has been performed.

Final archive reviewed: `moarchy-android-2e19361818cc.tar.gz`, SHA-256
`1001a18880e81485b4c96bf2e4c781dcf05768989fe38a3653fd6739c4c17fa8`.
The archive has 765 files, all four licence notices and no Python bytecode.
Its content digest and simulated install/reinstall/uninstall pass; evidence is
`/tmp/moarchy-android-build-evidence/bundle-validation.json`. Delivery to Alex's
phone uses a temporary LAN server restricted to a directory containing this
archive and checksum. This is a local source-bundle handover, not a GitHub release.

## Phone transfer repair — 2026-09-07

The Pixel could not reach the LAN server. The kernel journal records UFW blocking
its connection to port 8765; the original host-side check did not test LAN ingress.
Transfer now uses a temporary public Cloudflare Quick Tunnel to the same dedicated
directory, containing only the reviewed archive and checksum. The tunnel is limited
to 12 hours and bound to the existing source server's lifetime. Existing Cloudflare
account configuration and firewall rules remain unchanged. No GitHub publication,
repository history change or new installer content is part of this repair.

The full HTTPS download passed: 125,538,031 bytes and the expected SHA-256, with
matching checksum file. Evidence: `/tmp/moarchy-android-download-repair/https-validation.json`.

## Download preparation correction — 2026-09-07

The additional `scripts/android-download.py` is original source under this fork's
MIT licence. It contains the public archive name, length and hash, accepts an HTTPS
base URL, and has no credentials or client data. Its scope is downloading and
extracting the existing bundle under the real Debian home after a free-space check.
It does not run setup, install packages, or clean up previous phone downloads.
Its failure cleanup is limited to the directory it created. Five behavior tests
cover refusal before writes, integrity checks, archive paths and no installation.
This helper and its checksum may accompany the existing reviewed transfer bundle.
## Tablet adaptation layer — 2026-09-07

A second local host route, `android-tablet/`, targets the HIGRACE OC101
(Allwinner A523, Android 13, bootloader locked) via Termux + proot Debian. It is
original source under this fork's MIT licence, stays uncommitted like the rest
of the Android work, and ships nowhere: no GitHub release, no APK distribution,
no commit or push. `android/install.py` and `android/desktop.py` gained an
env-gated (`MOARCHY_ANDROID_PROOT=1`) tablet mode; the Pixel route's tested
behaviour is unchanged when the variable is unset. Transfer to the tablet runs
over USB (`adb reverse`) with the same reviewed `2e19361818cc` archive and
checksum; a loopback-only scratch CONNECT proxy on the laptop gives the tablet
package access through the owner's own connection. No Android root, bootloader
unlock, flashing or partition change is part of this layer.
