from __future__ import annotations

import os
import sys
from typing import Optional

from .protocol import BleClientProtocol


def create_ble_client() -> BleClientProtocol:
    if getattr(sys, "platform", "") == "android" or "ANDROID_BOOT" in os.environ:
        from .android_client import AndroidBleClient

        return AndroidBleClient()
    from .client import CyclingClient

    return CyclingClient()
