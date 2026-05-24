#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_DIR="${FLOW_NATIVE_APP_DIR:-"$ROOT_DIR/.build/native/Flow.app"}"
DIST_DIR="${FLOW_NATIVE_DIST_DIR:-"$ROOT_DIR/dist"}"
VERSION="${FLOW_RELEASE_VERSION:-}"
ARCH="${FLOW_RELEASE_ARCH:-$(uname -m)}"
REQUIRE_SIGNED="${FLOW_REQUIRE_SIGNED:-0}"
CODESIGN_IDENTITY="${FLOW_CODESIGN_IDENTITY:-}"

normalize_arch() {
  case "$1" in
    arm64|aarch64)
      printf 'arm64'
      ;;
    x86_64|amd64)
      printf 'x86_64'
      ;;
    *)
      printf 'Unsupported release architecture: %s\n' "$1" >&2
      return 1
      ;;
  esac
}

read_version() {
  local version
  version="$(sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT_DIR/pyproject.toml" | head -n 1)"
  if [[ -z "$version" ]]; then
    printf 'Could not read version from pyproject.toml\n' >&2
    return 1
  fi
  printf '%s\n' "$version"
}

require_path() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    printf 'Missing required app bundle path: %s\n' "$path" >&2
    exit 1
  fi
}

require_executable() {
  local path="$1"
  require_path "$path"
  if [[ ! -x "$path" ]]; then
    printf 'Required path is not executable: %s\n' "$path" >&2
    exit 1
  fi
}

if [[ -z "$VERSION" ]]; then
  cd "$ROOT_DIR"
  VERSION="$(read_version)"
fi

ARCH="$(normalize_arch "$ARCH")"

require_path "$APP_DIR"
require_executable "$APP_DIR/Contents/MacOS/FlowMacApp"
require_path "$APP_DIR/Contents/Info.plist"
require_executable "$APP_DIR/Contents/Resources/sidecar-runtime/node/bin/node"
require_path "$APP_DIR/Contents/Resources/sidecar-runtime/dist/main.js"
require_path "$APP_DIR/Contents/Resources/sidecar-runtime/package.json"

PLIST_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP_DIR/Contents/Info.plist" 2>/dev/null || true)"
if [[ "$PLIST_VERSION" != "$VERSION" ]]; then
  printf 'App bundle version mismatch: expected %s, found %s\n' "$VERSION" "${PLIST_VERSION:-<missing>}" >&2
  exit 1
fi

if [[ -n "$CODESIGN_IDENTITY" ]]; then
  codesign --force --deep --options runtime --sign "$CODESIGN_IDENTITY" "$APP_DIR"
fi

if codesign --verify --deep --strict "$APP_DIR" >/dev/null 2>&1; then
  printf 'Code signature verified for: %s\n' "$APP_DIR"
elif [[ "$REQUIRE_SIGNED" == "1" ]]; then
  printf 'App bundle is not signed for distribution. Set FLOW_CODESIGN_IDENTITY or sign before release.\n' >&2
  exit 1
else
  printf 'Warning: app bundle is not signed for distribution. Sign and notarize before public release.\n' >&2
fi

mkdir -p "$DIST_DIR"
ARCHIVE_PATH="$DIST_DIR/Flow-$VERSION-macos-$ARCH.zip"
rm -f "$ARCHIVE_PATH"

COPYFILE_DISABLE=1 ditto -c -k --norsrc --keepParent "$APP_DIR" "$ARCHIVE_PATH"

SHA256="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')"

printf 'Archive: %s\n' "$ARCHIVE_PATH"
printf 'SHA256: %s\n' "$SHA256"
