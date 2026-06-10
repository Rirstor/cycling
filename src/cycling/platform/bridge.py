from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from typing import Any, Optional

ble_data_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
device_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
_connected: bool = False
_device_name: str = ""
_loop: asyncio.AbstractEventLoop | None = None
_device_buffer: list[dict[str, Any]] = []
connect_event: asyncio.Event | None = None


def _is_android() -> bool:
    return (
        importlib.util.find_spec("java") is not None
        or getattr(sys, "platform", "") == "android"
        or "ANDROID_BOOT" in os.environ
    )


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop, connect_event
    _loop = loop
    connect_event = asyncio.Event()
    for item in _device_buffer:
        _loop.call_soon_threadsafe(device_queue.put_nowait, item)
    _device_buffer.clear()


def push_ble_data(json_str: str) -> None:
    data = json.loads(json_str)
    if _loop is not None:
        _loop.call_soon_threadsafe(lambda: ble_data_queue.put_nowait(data))


def push_device(address: str, name: str, rssi: int) -> None:
    data = {"address": address, "name": name, "rssi": rssi}
    if _loop is not None:
        _loop.call_soon_threadsafe(lambda: device_queue.put_nowait(data))
    else:
        _device_buffer.append(data)


def set_connected(device_name: str) -> None:
    global _connected, _device_name
    _connected = True
    _device_name = device_name
    if _loop is not None and connect_event is not None:
        _loop.call_soon_threadsafe(connect_event.set)


def set_disconnected() -> None:
    global _connected
    _connected = False


def is_connected() -> bool:
    return _connected


def get_connected_name() -> str:
    return _device_name


async def connect_device(address: str, hr_address: Optional[str] = None) -> None:
    if connect_event is None:
        raise RuntimeError("Bridge not initialized (set_event_loop not called)")
    connect_event.clear()
    try:
        from java import jclass
        BleBridge = jclass("com.cycling.app.BleBridge")
        BleBridge.connectToDevice(address, hr_address)
    except ImportError:
        pass
    await asyncio.wait_for(connect_event.wait(), timeout=10.0)


async def disconnect_device() -> None:
    try:
        from java import jclass
        BleBridge = jclass("com.cycling.app.BleBridge")
        BleBridge.disconnectFromDevice()
    except ImportError:
        pass
