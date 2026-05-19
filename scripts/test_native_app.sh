#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.build/native-tests"
SDK_PATH="$(xcrun --show-sdk-path)"
ARCH="$(uname -m)"
TEST_BINARY="$BUILD_DIR/FlowMacCoreSmokeTests"
TOOLCHAIN_PROBE="$BUILD_DIR/toolchain_probe.swift"
SIDECAR_DIR="$ROOT_DIR/sidecar"

mkdir -p "$BUILD_DIR"

cat > "$TOOLCHAIN_PROBE" <<'EOF'
import Foundation
print("toolchain-ok")
EOF

if ! swiftc -sdk "$SDK_PATH" "$TOOLCHAIN_PROBE" -o "$BUILD_DIR/toolchain_probe" >/dev/null 2>"$BUILD_DIR/toolchain_probe.stderr"; then
  echo "Swift toolchain verification failed before running smoke tests." >&2
  echo "xcode-select path: $(xcode-select -p)" >&2
  cat "$BUILD_DIR/toolchain_probe.stderr" >&2
    exit 1
fi

if [[ -f "$SIDECAR_DIR/package.json" ]]; then
  (
    cd "$SIDECAR_DIR"
    npm run build >/dev/null
  )
fi

CORE_SOURCES=()
while IFS= read -r source_file; do
  CORE_SOURCES+=("$source_file")
done < <(find "$ROOT_DIR/Sources/FlowMacCore" -name '*.swift' | sort)

APP_SOURCES=()
while IFS= read -r source_file; do
  APP_SOURCES+=("$source_file")
done < <(find "$ROOT_DIR/Sources/FlowMacApp" -name '*.swift' ! -name 'FlowMacApp.swift' | sort)

swiftc \
  -sdk "$SDK_PATH" \
  -target "${ARCH}-apple-macos14.0" \
  -module-name FlowMacCoreSmokeTests \
  -framework SwiftUI \
  -framework AppKit \
  -framework Combine \
  -framework EventKit \
  -framework UserNotifications \
  -lsqlite3 \
  "${CORE_SOURCES[@]}" \
  "${APP_SOURCES[@]}" \
  "$ROOT_DIR"/Tests/NativeSmoke/*.swift \
  -o "$TEST_BINARY"

"$TEST_BINARY"
