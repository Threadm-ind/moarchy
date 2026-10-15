#!/data/data/com.termux/files/usr/bin/bash
# Termux-side session control for the Moarchy tablet desktop.
# start: brings up termux-x11 (:0), opens the Termux:X11 app, and launches the
#        proot Debian guest as droid with the in-guest launcher.
# stop : kills the session process group and clears runtime sockets/markers.
# status: reports stopped/starting/running.
set -euo pipefail
distro=debian
pidfile="$HOME/.moarchy-session.pid"
xsock="$PREFIX/tmp/.X11-unix/X0"
guest_ready() {
  proot-distro login "$distro" --user droid -- \
    test -e /home/droid/.runtime/moarchy-android/desktop-ready >/dev/null 2>&1
}
case "${1:-status}" in
start)
  if [ ! -f "$HOME/guest-hosts" ]; then
    printf '127.0.0.1\tlocalhost proxy\n::1\tlocalhost ip6-localhost ip6-loopback\n' > "$HOME/guest-hosts"
  fi
  mkdir -p -- "$PREFIX/tmp/.X11-unix"
  if [ ! -S "$xsock" ]; then
    termux-x11 :0 >/dev/null 2>&1 &
    for _ in $(seq 1 30); do
      [ -S "$xsock" ] && break
      sleep 0.5
    done
    [ -S "$xsock" ] || { echo 'termux-x11 socket never appeared.' >&2; exit 1; }
  fi
  am start -n com.termux.x11/.MainActivity >/dev/null 2>&1 || true
  if [ -e "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo 'Session already running.'
    exit 0
  fi
  rm -f -- "$pidfile"
  setsid proot-distro login "$distro" --user droid \
    --shared-tmp \
    --bind /data/data/com.termux/files/home:/host-home \
    --bind /data/data/com.termux/files/home/guest-hosts:/etc/hosts \
    -- env DISPLAY=:0 LANG=C.UTF-8 LC_ALL=C.UTF-8 \
       bash /host-home/guest-start.sh &
  pid=$!
  echo "$pid" > "$pidfile"
  for _ in $(seq 1 60); do
    if guest_ready; then
      echo 'Desktop ready. Check the Termux:X11 app.'
      exit 0
    fi
    kill -0 "$pid" 2>/dev/null || {
      echo 'Session process exited early; inspect by running guest-start.sh manually.' >&2
      exit 1
    }
    sleep 2
  done
  echo 'Timed out waiting for desktop readiness.' >&2
  exit 1
  ;;
stop)
  if [ -e "$pidfile" ]; then
    pid=$(cat "$pidfile")
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    rm -f -- "$pidfile"
  fi
  proot-distro login "$distro" --user droid -- bash -c \
    'rm -f "$HOME/.runtime/moarchy-android/sway.sock" "$HOME/.runtime/moarchy-android/desktop-ready"' \
    >/dev/null 2>&1 || true
  echo 'Stopped.'
  ;;
status)
  if [ -e "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    if guest_ready; then
      echo 'running (desktop ready)'
    else
      echo 'starting'
    fi
  else
    echo 'stopped'
  fi
  ;;
*)
  echo 'Usage: session.sh start|stop|status' >&2
  exit 2
  ;;
esac
