#!/usr/bin/env bash
# Read-only Android guest diagnostic. It does not enable or start a desktop.

set -u

OS_RELEASE_FILE="/etc/os-release"

usage() {
  cat <<'USAGE'
Usage: scripts/android-check.sh

Check whether this guest resembles the current Debian/aarch64 display-helper
baseline for investigating Moarchy on Android. This is not a compatibility or
desktop-launch check, and it makes no changes.
USAGE
}

if [ "$#" -gt 0 ]; then
  case "$1" in
    -h|--help)
      if [ "$#" -eq 1 ]; then
        usage
        exit 0
      fi
      ;;
  esac
  usage >&2
  exit 2
fi

os_id=""
os_version_id=""
os_name=""

if [ -r "$OS_RELEASE_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case "$line" in
      ID=*|VERSION_ID=*|NAME=*)
        key=${line%%=*}
        value=${line#*=}
        case "$value" in
          \"*\") value=${value#\"}; value=${value%\"} ;;
          \'*\') value=${value#\'}; value=${value%\'} ;;
        esac
        case "$key" in
          ID) os_id=$value ;;
          VERSION_ID) os_version_id=$value ;;
          NAME) os_name=$value ;;
        esac
        ;;
    esac
  done < "$OS_RELEASE_FILE"
fi

cpu_arch=""
if cpu_arch=$(uname -m 2>/dev/null); then
  :
else
  cpu_arch=""
fi

kernel_release="unavailable"
if value=$(uname -r 2>/dev/null); then
  kernel_release=$value
fi

page_size="unavailable"
if value=$(getconf PAGESIZE 2>/dev/null); then
  page_size=$value
fi

if command -v enable_display >/dev/null 2>&1; then
  enable_display="available"
else
  enable_display="missing"
fi

if [ -n "${WAYLAND_DISPLAY-}" ]; then wayland_display="present"; else wayland_display="absent"; fi
if [ -n "${DISPLAY-}" ]; then x_display="present"; else x_display="absent"; fi
if command -v sway >/dev/null 2>&1; then sway="available"; else sway="missing"; fi
if command -v quickshell >/dev/null 2>&1; then quickshell="available"; else quickshell="missing"; fi
if command -v dbus-run-session >/dev/null 2>&1; then dbus_run_session="available"; else dbus_run_session="missing"; fi

printf 'Moarchy Android guest diagnostic\n'
printf 'OS_ID=%s\n' "${os_id:-unavailable}"
printf 'OS_VERSION_ID=%s\n' "${os_version_id:-unavailable}"
printf 'OS_NAME=%s\n' "${os_name:-unavailable}"
printf 'CPU_ARCH=%s\n' "${cpu_arch:-unavailable}"
printf 'KERNEL_RELEASE=%s\n' "$kernel_release"
printf 'PAGE_SIZE=%s\n' "$page_size"
printf 'ENABLE_DISPLAY=%s\n' "$enable_display"
printf 'WAYLAND_DISPLAY=%s\n' "$wayland_display"
printf 'DISPLAY=%s\n' "$x_display"
printf 'SWAY=%s\n' "$sway"
printf 'QUICKSHELL=%s\n' "$quickshell"
printf 'DBUS_RUN_SESSION=%s\n' "$dbus_run_session"
printf 'DESKTOP_STATUS=UNVERIFIED (no desktop was launched)\n'

errors=()
if [ "$os_id" != "debian" ]; then
  errors+=("requires Debian guest OS (reported: ${os_id:-unavailable})")
fi
if [ -z "$cpu_arch" ]; then
  errors+=("could not collect CPU architecture")
elif [ "$cpu_arch" != "aarch64" ]; then
  errors+=("requires aarch64 CPU architecture (reported: $cpu_arch)")
fi
if [ "$enable_display" != "available" ]; then
  errors+=("enable_display helper is missing; inspect /usr/local/bin and check the Terminal Display button before treating graphics as unsupported")
fi

if [ "${#errors[@]}" -gt 0 ]; then
  printf 'BASELINE_CANDIDATE=FAIL\n'
  for error in "${errors[@]}"; do
    printf 'Reason: %s\n' "$error" >&2
  done
  exit 1
fi

printf 'BASELINE_CANDIDATE=PASS (Debian/aarch64 with enable_display available; Moarchy compatibility unverified)\n'
