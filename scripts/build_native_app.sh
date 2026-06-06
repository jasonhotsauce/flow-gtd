#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/native"
APP_DIR="$BUILD_DIR/Flow.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RESOURCES_DIR="$APP_DIR/Contents/Resources"
SIDECAR_RUNTIME_DIR="$RESOURCES_DIR/sidecar-runtime"
SIDECAR_DIR="$ROOT_DIR/sidecar"
INFO_PLIST="$ROOT_DIR/NativeSupport/FlowMacApp-Info.plist"
ICON_SOURCE="$ROOT_DIR/NativeSupport/FlowIcon.png"
ICONSET_DIR="$BUILD_DIR/Flow.iconset"
ICON_FILE="$RESOURCES_DIR/Flow.icns"

VERSION="$(sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT_DIR/pyproject.toml" | head -n 1)"
if [[ -z "$VERSION" ]]; then
  echo "Could not read version from pyproject.toml" >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$MACOS_DIR" "$RESOURCES_DIR"

SDK_PATH="$(xcrun --show-sdk-path)"
ARCH="$(uname -m)"
TOOLCHAIN_PROBE="$BUILD_DIR/toolchain_probe.swift"
TOOLCHAIN_STDOUT="$BUILD_DIR/toolchain_probe.stdout"
TOOLCHAIN_STDERR="$BUILD_DIR/toolchain_probe.stderr"

cat > "$TOOLCHAIN_PROBE" <<'EOF'
import Foundation
print("toolchain-ok")
EOF

if ! swiftc -sdk "$SDK_PATH" "$TOOLCHAIN_PROBE" -o "$BUILD_DIR/toolchain_probe" >"$TOOLCHAIN_STDOUT" 2>"$TOOLCHAIN_STDERR"; then
  echo "Swift toolchain verification failed before app compilation." >&2
  echo "xcode-select path: $(xcode-select -p)" >&2
  cat "$TOOLCHAIN_STDERR" >&2
  exit 1
fi

if [[ ! -f "$SIDECAR_DIR/package.json" ]]; then
  echo "Missing sidecar package.json at $SIDECAR_DIR" >&2
  exit 1
fi

if [[ ! -f "$ICON_SOURCE" ]]; then
  echo "Missing app icon source at $ICON_SOURCE" >&2
  exit 1
fi

if ! command -v iconutil >/dev/null 2>&1; then
  echo "iconutil is required to build the native app icon." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the bundled TypeScript sidecar." >&2
  exit 1
fi

(
  cd "$SIDECAR_DIR"
  npm run build >/dev/null
)

if [[ ! -f "$SIDECAR_DIR/dist/main.js" ]]; then
  echo "Sidecar build did not produce dist/main.js" >&2
  exit 1
fi

BUNDLED_NODE_CANDIDATES=(
  "${FLOW_SIDECAR_NODE_PATH:-}"
  "${CODEX_BUNDLED_NODE_PATH:-}"
  "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
  "$(command -v node || true)"
)

BUNDLED_NODE_PATH=""
for candidate in "${BUNDLED_NODE_CANDIDATES[@]}"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    BUNDLED_NODE_PATH="$candidate"
    break
  fi
done

if [[ -z "$BUNDLED_NODE_PATH" ]]; then
  echo "Could not locate a Node runtime to bundle into the app." >&2
  exit 1
fi

SWIFT_SOURCES=()
while IFS= read -r source_file; do
  SWIFT_SOURCES+=("$source_file")
done < <(find "$ROOT_DIR/Sources/FlowMacCore" "$ROOT_DIR/Sources/FlowMacApp" -name '*.swift' | sort)

swiftc \
  -sdk "$SDK_PATH" \
  -target "${ARCH}-apple-macos14.0" \
  -module-name FlowMacApp \
  -framework SwiftUI \
  -framework AppKit \
  -framework Combine \
  -framework EventKit \
  -framework UserNotifications \
  -lsqlite3 \
  "${SWIFT_SOURCES[@]}" \
  -o "$MACOS_DIR/FlowMacApp"

cp "$INFO_PLIST" "$APP_DIR/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP_DIR/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$APP_DIR/Contents/Info.plist"
printf 'APPL????' > "$APP_DIR/Contents/PkgInfo"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET_DIR" -o "$ICON_FILE"
rm -rf "$SIDECAR_RUNTIME_DIR"
mkdir -p "$SIDECAR_RUNTIME_DIR/node/bin"
cp "$BUNDLED_NODE_PATH" "$SIDECAR_RUNTIME_DIR/node/bin/node"
chmod +x "$SIDECAR_RUNTIME_DIR/node/bin/node"
cp -R "$SIDECAR_DIR/dist" "$SIDECAR_RUNTIME_DIR/dist"
cp "$SIDECAR_DIR/package.json" "$SIDECAR_RUNTIME_DIR/package.json"

echo "Built native app bundle at: $APP_DIR"
