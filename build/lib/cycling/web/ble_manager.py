from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from cycling.ble.client import CyclingClient
from cycling.data.models import CyclingRecord, ZONE_DEFINITIONS
from cycling.data.storage import load_latest_ftp
from cycling.training.routine_engine import RoutineEngine
from cycling.training.zones import CogganZones

ZONE_COLORS = {
    1: "blue",
    2: "green",
    3: "yellow",
    4: "orange1",
    5: "red",
    6: "magenta",
    7: "bright_white",
}


class BLEManager:
    def __init__(self) -> None:
        self._client: Optional[CyclingClient] = None
        self._task: Optional[asyncio.Task] = None
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._records: list[CyclingRecord] = []
        self._last_power: Optional[float] = None
        self._last_cad: Optional[float] = None
        self._last_hr: Optional[float] = None
        self._zones: Optional[CogganZones] = None
        self._time_in_zones: dict[int, float] = {}
        self._start_time: Optional[datetime] = None
        self._connected: bool = False
        self._recording: bool = False
        self._session_id: Optional[int] = None
        self._ftp: int = 200
        self._routine: RoutineEngine = RoutineEngine()
        self._last_tick_time: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def client(self) -> Optional[CyclingClient]:
        return self._client

    @property
    def records(self) -> list[CyclingRecord]:
        return self._records

    @property
    def start_time(self) -> Optional[datetime]:
        return self._start_time

    @property
    def session_id(self) -> Optional[int]:
        return self._session_id

    @session_id.setter
    def session_id(self, value: Optional[int]) -> None:
        self._session_id = value

    @property
    def routine(self) -> RoutineEngine:
        return self._routine

    async def routine_start(self, template_name: str) -> None:
        from cycling.training.workouts import get_workout
        template = get_workout(template_name)
        if not template:
            raise ValueError(f"Unknown routine: {template_name}")
        self._routine.set_ftp(self._ftp)
        self._routine.load(template)
        self._routine.start()
        self._last_tick_time = datetime.now()

    async def routine_pause(self) -> None:
        self._routine.pause()

    async def routine_stop(self) -> None:
        self._routine.stop()

    def _build_sse_data(self) -> dict[str, Any]:
        ftp = self._ftp
        elapsed = 0
        if self._start_time:
            elapsed = int((datetime.now() - self._start_time).total_seconds())

        power = self._last_power
        cad = self._last_cad
        hr = self._last_hr

        zone_num = 2
        if power is not None and self._zones:
            zn = self._zones.zone_for_power(power)
            zone_num = zn if isinstance(zn, int) else zn.value
        zone_name = self._zones.zone_name(zone_num) if self._zones else "Unknown"
        zone_color = ZONE_COLORS.get(zone_num, "white")

        power_pct = 0.0
        if power is not None and ftp > 0:
            power_pct = min(power / ftp * 100, 200)

        avg_power: Optional[float] = None
        avg_hr: Optional[float] = None
        avg_cad: Optional[float] = None
        if self._records:
            powers = [r.power_watts for r in self._records if r.power_watts is not None]
            hrs = [r.heart_rate_bpm for r in self._records if r.heart_rate_bpm is not None]
            cads = [r.cadence_rpm for r in self._records if r.cadence_rpm is not None]
            if powers:
                avg_power = sum(powers) / len(powers)
            if hrs:
                avg_hr = sum(hrs) / len(hrs)
            if cads:
                avg_cad = sum(cads) / len(cads)

        time_in_zones_str = {str(k): v for k, v in self._time_in_zones.items()}

        routine_data = self._routine.get_sse_data()
        evaluation = {}
        if routine_data.get("routine_active"):
            evaluation = self._routine.evaluate(power, cad)
            routine_data.update(evaluation)

        return {
            "connected": self._connected,
            "recording": self._recording,
            "power_watts": power,
            "cadence_rpm": cad,
            "heart_rate_bpm": hr,
            "zone": zone_num,
            "zone_name": zone_name,
            "zone_color": zone_color,
            "power_pct": round(power_pct, 1),
            "elapsed": elapsed,
            "avg_power": round(avg_power, 0) if avg_power is not None else None,
            "avg_hr": round(avg_hr, 0) if avg_hr is not None else None,
            "avg_cad": round(avg_cad, 0) if avg_cad is not None else None,
            "time_in_zones": time_in_zones_str,
            **routine_data,
        }

    async def connect(self, address: str, hr_address: Optional[str] = None) -> None:
        if self._connected:
            return

        ftp_config = load_latest_ftp()
        self._ftp = ftp_config.value_watts if ftp_config else 200
        self._zones = CogganZones(self._ftp)

        for z_def in ZONE_DEFINITIONS:
            self._time_in_zones[z_def["zone"].value] = 0.0

        self._client = CyclingClient()
        await self._client.connect(address, hr_address)
        self._connected = True
        self._start_time = datetime.now()
        self._records = []
        self._last_power = None
        self._last_cad = None
        self._last_hr = None

        self._task = asyncio.create_task(self._stream_loop())
        await self._broadcast(self._build_sse_data())

    async def disconnect(self) -> None:
        self._connected = False
        self._recording = False
        self._session_id = None
        self._routine.stop()
        if self._task:
            self._task.cancel()
            self._task = None
        if self._client:
            await self._client.disconnect()
            self._client = None
        await self._broadcast(self._build_sse_data())

    async def _stream_loop(self) -> None:
        if not self._client:
            return
        try:
            async for record in self._client.stream_data():
                now = datetime.now()
                if self._last_tick_time is not None:
                    delta = (now - self._last_tick_time).total_seconds()
                else:
                    delta = 0.0
                self._last_tick_time = now

                self._records.append(record)

                if record.power_watts is not None:
                    if self._zones:
                        zn = self._zones.zone_for_power(record.power_watts)
                        record.zone = zn if isinstance(zn, int) else zn.value
                        self._time_in_zones[record.zone] = self._time_in_zones.get(record.zone, 0) + 1
                    self._last_power = record.power_watts
                if record.cadence_rpm is not None:
                    self._last_cad = record.cadence_rpm
                if record.heart_rate_bpm is not None:
                    self._last_hr = record.heart_rate_bpm

                if record.power_watts is None:
                    record.power_watts = self._last_power
                if record.cadence_rpm is None:
                    record.cadence_rpm = self._last_cad
                if record.heart_rate_bpm is None:
                    record.heart_rate_bpm = self._last_hr

                self._routine.tick(delta, record.power_watts, record.cadence_rpm)

                sse_data = self._build_sse_data()
                await self._broadcast(sse_data)
        except asyncio.CancelledError:
            pass
        except Exception:
            self._connected = False
            await self._broadcast(self._build_sse_data())

    async def _broadcast(self, data: dict[str, Any]) -> None:
        for q in self._subscribers:
            await q.put(data)

    def subscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.append(queue)

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)
