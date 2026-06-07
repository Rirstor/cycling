#!/usr/bin/env bash
#
# test-apk-on-device.sh — Build, install, and smoke-test the Cycling APK
# on a connected Android device (physical phone or emulator).
#
# Usage:
#   ./scripts/test-apk-on-device.sh              # build + test
#   ./scripts/test-apk-on-device.sh --skip-build  # test only (APK must exist)
#
# Requirements:
#   - adb (Android SDK platform-tools)
#   - A device connected via USB with USB debugging enabled
#   - (Optional) curl on the host to test the Python server port

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APK_PATH="${SCRIPT_DIR}/android/app/build/outputs/apk/debug/app-debug.apk"
APP_ID="com.cycling.app"
MAIN_ACTIVITY="${APP_ID}/.MainActivity"
HEALTH_URL="http://127.0.0.1:8080/health"

# ── colours ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
cmd()   { echo -e "${CYAN}[CMD]${NC}   $*"; "$@"; }

# ── step 0 — locate / build APK ──────────────────────────────
if [ "${1:-}" = "--skip-build" ]; then
    if [ ! -f "$APK_PATH" ]; then
        fail "APK not found at ${APK_PATH}. Build it first."
    fi
    info "Using existing APK: ${APK_PATH}"
else
    info "Building APK ..."
    cmd "${SCRIPT_DIR}/android/gradlew" -p "${SCRIPT_DIR}/android" assembleDebug --stacktrace --no-daemon
    if [ ! -f "$APK_PATH" ]; then
        fail "APK was not produced at ${APK_PATH}."
    fi
    pass "APK built: ${APK_PATH}"
fi

# ── step 1 — check device ────────────────────────────────────
DEVICE_COUNT=$(adb devices | awk 'NR>1 && /device$/ {count++} END {print count}')
if [ "$DEVICE_COUNT" -eq 0 ]; then
    fail "No Android device connected. Connect a device via USB with USB debugging enabled."
fi
info "Found ${DEVICE_COUNT} device(s) connected."

DEVICE=$(adb devices | awk 'NR>1 && /device$/ {print $1; exit}')
info "Using device: ${DEVICE}"

# ── step 2 — install APK ─────────────────────────────────────
info "Installing APK on device ..."
cmd adb -s "$DEVICE" install -r "$APK_PATH" 2>&1
pass "APK installed."

# ── step 3 — grant permissions ───────────────────────────────
info "Granting runtime permissions ..."
cmd adb -s "$DEVICE" shell pm grant "${APP_ID}" android.permission.BLUETOOTH_SCAN   2>/dev/null || true
cmd adb -s "$DEVICE" shell pm grant "${APP_ID}" android.permission.BLUETOOTH_CONNECT 2>/dev/null || true
cmd adb -s "$DEVICE" shell pm grant "${APP_ID}" android.permission.ACCESS_FINE_LOCATION 2>/dev/null || true
pass "Permissions granted."

# ── step 4 — clear logcat and launch ─────────────────────────
info "Clearing logcat ..."
cmd adb -s "$DEVICE" logcat -c 2>/dev/null || true

info "Launching app ..."
cmd adb -s "$DEVICE" shell am start -n "${MAIN_ACTIVITY}"
pass "App launched."

# ── step 5 — wait for Python server ──────────────────────────
info "Waiting for Python server to start (up to 30s) ..."
SERVER_READY=false
for i in $(seq 1 30); do
    sleep 1
    if adb -s "$DEVICE" logcat -d -s "PythonServer:I" 2>/dev/null | grep -q "Server ready"; then
        SERVER_READY=true
        break
    fi
    # Also check error log
    if adb -s "$DEVICE" logcat -d -s "PythonServer:E" 2>/dev/null | grep -q "."; then
        warn "PythonServer error detected in logcat"
        adb -s "$DEVICE" logcat -d -s "PythonServer:E" 2>/dev/null | tail -5
    fi
done

if [ "$SERVER_READY" = true ]; then
    pass "Python server started and ready."
else
    warn "Timed out waiting for Python server."
    info "Last 20 lines of logcat (PythonServer):"
    adb -s "$DEVICE" logcat -d -s "PythonServer:I" 2>/dev/null | tail -20
    info "Last 20 lines of logcat (all errors):"
    adb -s "$DEVICE" logcat -d -s "*:E" 2>/dev/null | tail -20
    fail "Python server did not become ready."
fi

# ── step 6 — port-forward and health-check ───────────────────
info "Setting up port forwarding (8080 → device:8080) ..."
cmd adb -s "$DEVICE" forward tcp:8080 tcp:8080

info "Testing health endpoint ..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${HEALTH_URL}" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    HEALTH_BODY=$(curl -s --max-time 5 "${HEALTH_URL}" 2>/dev/null)
    pass "Health endpoint responded: ${HEALTH_BODY}"
else
    warn "Health endpoint returned HTTP ${HTTP_CODE}."
    fail "Python server health check failed."
fi

# ── step 7 — verify dashboard serves ─────────────────────────
info "Testing dashboard page ..."
DASHBOARD_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:8080/" 2>/dev/null || echo "000")
if [ "$DASHBOARD_CODE" = "200" ]; then
    pass "Dashboard serves correctly (HTTP ${DASHBOARD_CODE})."
else
    warn "Dashboard returned HTTP ${DASHBOARD_CODE}."
    fail "Dashboard health check failed."
fi

# ── step 8 — check logcat for crashes ────────────────────────
CRASH_COUNT=$(adb -s "$DEVICE" logcat -d -b crash 2>/dev/null | grep -c "${APP_ID}" || true)
if [ "$CRASH_COUNT" -gt 0 ]; then
    warn "Found ${CRASH_COUNT} crash log(s) for ${APP_ID}."
    adb -s "$DEVICE" logcat -d -b crash 2>/dev/null | grep -A 5 "${APP_ID}" | head -20
else
    pass "No crashes detected."
fi

# ── all done ──────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo -e "${GREEN}  All checks passed! The app is working.${NC}"
echo "══════════════════════════════════════════════════"
echo ""
info "The APK is installed and verified on your device."
info "You can now open the app normally from the launcher."
info "To remove APK port-forward: adb forward --remove tcp:8080"
