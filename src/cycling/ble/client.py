from __future__ import annotations

import asyncio
import struct
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from cycling.ble.protocol import BleClientProtocol

if TYPE_CHECKING:
    from bleak import BleakClient
from cycling.data.models import CyclingRecord

FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


def _parse_indoor_bike_data(data: bytes) -> dict[str, Any]:
    if len(data) < 2:
        return {}
    flags = struct.unpack_from("<H", data, 0)[0]
    offset = 2
    result: dict[str, Any] = {}

    # Bit 0 (More Data): when SET, Instantaneous Speed is NOT present.
    if flags & 0x0001 == 0 and len(data) >= offset + 2:
        raw = struct.unpack_from("<H", data, offset)[0]
        result["instantaneous_speed"] = raw / 100.0
        offset += 2

    if flags & 0x0002:
        if len(data) >= offset + 2:
            raw = struct.unpack_from("<H", data, offset)[0]
            result["average_speed"] = raw / 100.0
            offset += 2

    if flags & 0x0004:
        if len(data) >= offset + 2:
            raw = struct.unpack_from("<H", data, offset)[0]
            result["instantaneous_cadence"] = raw / 2.0
            offset += 2

    if flags & 0x0008:
        if len(data) >= offset + 2:
            raw = struct.unpack_from("<H", data, offset)[0]
            result["average_cadence"] = raw / 2.0
            offset += 2

    if flags & 0x0010:
        if len(data) >= offset + 3:
            result["total_distance"] = struct.unpack_from("<I", data, offset)[0] & 0xFFFFFF
            offset += 3

    if flags & 0x0020:
        if len(data) >= offset + 2:
            raw = struct.unpack_from("<H", data, offset)[0]
            result["resistance_level"] = raw
            offset += 2

    if flags & 0x0040:
        if len(data) >= offset + 2:
            result["instantaneous_power"] = struct.unpack_from("<h", data, offset)[0]
            offset += 2

    if flags & 0x0080:
        if len(data) >= offset + 2:
            result["average_power"] = struct.unpack_from("<h", data, offset)[0]
            offset += 2

    return result


class CyclingClient(BleClientProtocol):
    def __init__(self):
        self._trainer_client: Optional[BleakClient] = None
        self._hr_client: Optional[BleakClient] = None
        self._hr_data: dict[str, Any] = {}
        self._trainer_address: str = ""
        self._hr_address: str = ""

    async def connect(self, trainer_address: str, hr_address: Optional[str] = None, timeout: float = 10.0) -> None:
        from bleak import BleakClient

        self._trainer_address = trainer_address
        self._hr_address = hr_address or ""
        self._trainer_client = BleakClient(trainer_address, disconnected_callback=self._on_disconnect)
        await asyncio.wait_for(self._trainer_client.connect(), timeout=timeout)
        if self._trainer_client and hr_address:
            self._hr_client = BleakClient(hr_address, disconnected_callback=self._on_hr_disconnect)
            await asyncio.wait_for(self._hr_client.connect(), timeout=timeout)
            if self._hr_client:
                await self._hr_client.start_notify(
                    HEART_RATE_UUID, self._hr_notification_handler
                )

    def _on_disconnect(self, client: BleakClient) -> None:
        pass

    def _on_hr_disconnect(self, client: BleakClient) -> None:
        pass

    def _hr_notification_handler(self, characteristic: Any, data: bytearray) -> None:
        heart_rate = data[1] if len(data) > 1 else 0
        self._hr_data["heart_rate"] = heart_rate
        self._hr_data["timestamp"] = datetime.now()

    async def stream_data(self) -> AsyncIterator[CyclingRecord]:
        if not self._trainer_client:
            return
        data_queue: asyncio.Queue[CyclingRecord] = asyncio.Queue()

        def indoor_bike_handler(characteristic: Any, data: bytearray) -> None:
            parsed = _parse_indoor_bike_data(bytes(data))
            record = CyclingRecord(
                timestamp=datetime.now(),
                power_watts=parsed.get("instantaneous_power"),
                cadence_rpm=parsed.get("instantaneous_cadence"),
                speed_kph=parsed.get("instantaneous_speed"),
            )
            data_queue.put_nowait(record)

        try:
            await self._trainer_client.start_notify(
                INDOOR_BIKE_DATA_UUID, indoor_bike_handler
            )
        except Exception:
            pass

        while True:
            try:
                record = await asyncio.wait_for(data_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if self._hr_data and "heart_rate" in self._hr_data:
                record.heart_rate_bpm = self._hr_data["heart_rate"]
            yield record

    async def disconnect(self) -> None:
        if self._hr_client:
            try:
                await self._hr_client.stop_notify(HEART_RATE_UUID)
            except Exception:
                pass
            try:
                await self._hr_client.disconnect()
            except Exception:
                pass
        if self._trainer_client:
            try:
                await self._trainer_client.stop_notify(INDOOR_BIKE_DATA_UUID)
            except Exception:
                pass
            try:
                await self._trainer_client.disconnect()
            except Exception:
                pass

    @property
    def device_name(self) -> str:
        if self._trainer_client and self._trainer_client.is_connected:
            return self._trainer_address
        return ""
