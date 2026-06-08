from __future__ import annotations

from cycling.platform.bridge import _is_android

from .protocol import BleClientProtocol


def create_ble_client() -> BleClientProtocol:
    if _is_android():
        from .android_client import AndroidBleClient

        return AndroidBleClient()
    from .client import CyclingClient

    return CyclingClient()
