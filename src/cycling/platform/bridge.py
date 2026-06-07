from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

ble_data_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
device_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
_connected: bool = False
_device_name: str = ""


def push_ble_data(json_str: str) -> None:
    """Called from Kotlin via JNI on each BLE notification.

    The JSON string is a flat dict of parsed FTMS Indoor Bike Data fields.
    """
    data = json.loads(json_str)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.call_soon_threadsafe(lambda: ble_data_queue.put_nowait(data))


def push_device(address: str, name: str, rssi: int) -> None:
    """Called from Kotlin when BLE scan finds a cycling device."""
    data = {"address": address, "name": name, "rssi": rssi}
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.call_soon_threadsafe(lambda: device_queue.put_nowait(data))


def set_connected(device_name: str) -> None:
    global _connected, _device_name
    _connected = True
    _device_name = device_name


def set_disconnected() -> None:
    global _connected
    _connected = False


def is_connected() -> bool:
    return _connected


def get_connected_name() -> str:
    return _device_name


async def connect_device(address: str, hr_address: Optional[str] = None) -> None:
    """Reserved for future use; the Kotlin side handles connections directly."""
    pass


async def disconnect_device() -> None:
    """Reserved for future use; the Kotlin side handles disconnections directly."""
    pass
