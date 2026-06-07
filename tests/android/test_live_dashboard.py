"""Appium-based Android UI tests for the Cycling app.

Requires:
    - Android emulator running on localhost:5555 (or APPIUM_HOST env)
    - Appium server running on localhost:4723
    - APK built at android/app/build/outputs/apk/debug/app-debug.apk
"""

import os
import time
from typing import Any

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy

APPIUM_HOST = os.environ.get("APPIUM_HOST", "localhost")
APK_PATH = os.environ.get("APK_PATH", "/apk/app-debug.apk")


@pytest.fixture(scope="module")
def driver() -> Any:
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name = "emulator-5554"
    options.app = APK_PATH
    options.auto_grant_permissions = True
    options.no_reset = False
    options.ensure_webviews_have_pages = True

    driver = webdriver.Remote(
        f"http://{APPIUM_HOST}:4723", options=options
    )
    yield driver
    driver.quit()


def test_app_launches(driver: Any) -> None:
    """Verify the app starts and the Python server serves the dashboard."""
    time.sleep(10)

    contexts = driver.contexts
    webview = [c for c in contexts if "WEBVIEW" in c]
    assert webview, f"No WebView context found. Contexts: {contexts}"

    driver.switch_to.context(webview[0])
    time.sleep(2)

    page_source = driver.page_source
    assert "Cycling Dashboard" in page_source, (
        f"Expected 'Cycling Dashboard' in page. Got: {page_source[:200]}"
    )


def test_navigate_live_page(driver: Any) -> None:
    """Navigate to the Live page and verify device scanning UI."""
    contexts = driver.contexts
    webview = [c for c in contexts if "WEBVIEW" in c]
    assert webview
    driver.switch_to.context(webview[0])
    time.sleep(1)

    live_link = driver.find_element(AppiumBy.LINK_TEXT, "Live")
    live_link.click()
    time.sleep(3)

    assert "Available Devices" in driver.page_source


def test_navigate_routines(driver: Any) -> None:
    """Navigate to the Routines page and verify it loads."""
    contexts = driver.contexts
    webview = [c for c in contexts if "WEBVIEW" in c]
    assert webview
    driver.switch_to.context(webview[0])
    time.sleep(1)

    routines_link = driver.find_element(AppiumBy.LINK_TEXT, "Routines")
    routines_link.click()
    time.sleep(2)

    assert "Workout" in driver.page_source or "Routine" in driver.page_source


def test_navigate_history(driver: Any) -> None:
    """Navigate to the History page."""
    contexts = driver.contexts
    webview = [c for c in contexts if "WEBVIEW" in c]
    assert webview
    driver.switch_to.context(webview[0])

    driver.find_element(AppiumBy.LINK_TEXT, "History").click()
    time.sleep(2)

    assert "History" in driver.page_source or "session" in driver.page_source.lower()


def test_health_endpoint(driver: Any) -> None:
    """Verify the Python server health endpoint responds via WebView."""
    driver.get("http://127.0.0.1:8080/health")
    time.sleep(2)
    assert "ok" in driver.page_source.lower()
