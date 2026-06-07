from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from cycling.data.models import CyclingRecord
from cycling.ble.protocol import BleClientProtocol

from cycling.platform.bridge import (
    ble_data_queue,
    connect_device,
    disconnect_device,
    get_connected_name,
)


class AndroidBleClient(BleClientProtocol):
    """Android BLE client that receives data from Kotlin via Chaquopy JNI bridge.

    Does NOT import bleak — all BLE operations are handled on the Kotlin side.
    """

    def __init__(self) -> None:
        self._name: str = ""
        self._connected: bool = False

    async def connect(
        self, address: str, hr_address: Optional[str] = None, timeout: float = 10.0
    ) -> None:
        await connect_device(address, hr_address)
        self._name = get_connected_name()
        self._connected = True

    async def stream_data(self) -> AsyncIterator[CyclingRecord]:
        while self._connected:
            try:
                data: dict[str, Any] = await asyncio.wait_for(
                    ble_data_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            yield CyclingRecord(
                timestamp=datetime.now(),
                power_watts=data.get("instantaneous_power"),
                cadence_rpm=data.get("instantaneous_cadence"),
                heart_rate_bpm=data.get("heart_rate"),
                speed_kph=data.get("instantaneous_speed"),
            )

    async def disconnect(self) -> None:
        self._connected = False
        await disconnect_device()

    @property
    def device_name(self) -> str:
        return self._name
