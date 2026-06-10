#!/usr/bin/env bash
set -euo pipefail

# Build Android APK — mimics the 'Build Android APK' CI job from .github/workflows/ci.yml
#
# Prerequisites (same as CI):
#   1. JDK 17+  (e.g. temurin)
#   2. Python 3.11
#   3. Android SDK with:
#       - platforms;android-34
#       - build-tools;34.0.0
#       - ndk;26.1.10909125
#   4. ANDROID_HOME or android/local.properties pointing to the SDK

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== Cycling Android APK Builder ==="
echo "Project dir: $PROJECT_DIR"

# ------------------------------------------------------------------
# 1. Check prerequisites (soft warnings, not fatal — CI handles setup)
# ------------------------------------------------------------------
if ! command -v java &>/dev/null; then
    echo "::warning::JDK not found — install JDK 17+ (e.g. temurin)"
fi
if ! command -v python3 &>/dev/null; then
    echo "::warning::Python 3 not found"
fi
if [ -z "${ANDROID_HOME:-}" ] && [ ! -f android/local.properties ]; then
    echo "::error::Android SDK location not configured."
    echo "  Set ANDROID_HOME or create android/local.properties with:"
    echo "    sdk.dir=C\\:\\\\Users\\\\<user>\\\\AppData\\\\Local\\\\Android\\\\Sdk"
    exit 1
fi
if [ -n "${ANDROID_HOME:-}" ] && [ ! -d "$ANDROID_HOME" ]; then
    echo "::error::ANDROID_HOME ($ANDROID_HOME) does not exist"
    exit 1
fi

# ------------------------------------------------------------------
# 2. Accept licenses & install required SDK components (idempotent)
# ------------------------------------------------------------------
SDK_MANAGER="${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager"
if [ -x "$SDK_MANAGER" ]; then
    echo "--- Accepting Android licenses ---"
    yes | "$SDK_MANAGER" --licenses 2>/dev/null || true

    echo "--- Ensuring required SDK packages ---"
    "$SDK_MANAGER" \
        "platforms;android-34" \
        "build-tools;34.0.0" \
        "ndk;26.1.10909125" \
        2>/dev/null || true
else
    echo "::warning::sdkmanager not found at $SDK_MANAGER — skipping license/package install"
fi

# ------------------------------------------------------------------
# 3. Copy Python source into Chaquopy source dir (matches CI)
# ------------------------------------------------------------------
echo "--- Copying Python source to Chaquopy dir ---"
mkdir -p android/app/src/main/python
cp -r src/cycling android/app/src/main/python/

# ------------------------------------------------------------------
# 4. Build the debug APK
# ------------------------------------------------------------------
echo "--- Building APK (assembleDebug) ---"
cd android
./gradlew assembleDebug --stacktrace --no-daemon

# ------------------------------------------------------------------
# 5. Report result
# ------------------------------------------------------------------
APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK_PATH" ]; then
    APK_SIZE=$(stat --printf="%s" "$APK_PATH" 2>/dev/null || stat -f%z "$APK_PATH" 2>/dev/null)
    echo "========================================="
    echo "APK built successfully: $APK_PATH"
    echo "Size: $APK_SIZE bytes"
    echo "========================================="
else
    echo "::error::APK not found at $APK_PATH — build may have failed"
    exit 1
fi
