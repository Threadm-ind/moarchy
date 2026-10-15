#!/usr/bin/env bash
# Build a supplied, verified moarchy-keyboard source tree without network access.
#
# Usage: android/keyboard-build.sh SOURCE_DIR OUTPUT_DIR
#
# The output is a DESTDIR staging tree: OUTPUT_DIR/usr/bin/moarchy-keyboard and
# OUTPUT_DIR/usr/share/moarchy-keyboard/layouts/*.json.  BUILD_DIR defaults to
# a temporary build directory. The caller owns OUTPUT_DIR.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  printf 'Usage: %s SOURCE_DIR OUTPUT_DIR\n' "$0" >&2
  exit 64
fi

SOURCE_DIR="$1"
OUTPUT_DIR="$2"
BUILD_DIR="${BUILD_DIR:-${TMPDIR:-/tmp}/moarchy-keyboard-build}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATCH_FILE="$SCRIPT_DIR/keyboard-debian.patch"

if [ ! -f "$SOURCE_DIR/CMakeLists.txt" ]; then
  printf 'Keyboard source is missing CMakeLists.txt: %s\n' "$SOURCE_DIR" >&2
  exit 66
fi

if [ "$SOURCE_DIR" = "$BUILD_DIR" ]; then
  printf 'BUILD_DIR must differ from SOURCE_DIR\n' >&2
  exit 64
fi
if [ ! -f "$PATCH_FILE" ]; then
  printf 'Debian compatibility patch is missing: %s\n' "$PATCH_FILE" >&2
  exit 66
fi

install -d -m 0755 "$BUILD_DIR" "$OUTPUT_DIR"
PATCHED_SOURCE_DIR=$(mktemp -d "$BUILD_DIR/source.XXXXXX")
CMAKE_BUILD_DIR=$(mktemp -d "$BUILD_DIR/build.XXXXXX")
trap 'rm -rf -- "$PATCHED_SOURCE_DIR" "$CMAKE_BUILD_DIR"' EXIT
cp -a "$SOURCE_DIR/." "$PATCHED_SOURCE_DIR/"
patch --batch --forward -p1 -d "$PATCHED_SOURCE_DIR" < "$PATCH_FILE"

cmake -S "$PATCHED_SOURCE_DIR" -B "$CMAKE_BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
  -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$CMAKE_BUILD_DIR" --parallel "${MOARCHY_BUILD_JOBS:-2}"
DESTDIR="$OUTPUT_DIR" cmake --install "$CMAKE_BUILD_DIR" --prefix /usr
