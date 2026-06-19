from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from cycling.ble.scanner import scan_devices
from cycling.platform.bridge import _is_android


class ScanManager:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._bridge_task: Optional[asyncio.Task] = None
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._devices: dict[str, dict[str, Any]] = {}
        self._running = False
        self._paused = False

    @property
    def devices(self) -> list[dict[str, Any]]:
        return sorted(
            self._devices.values(),
            key=lambda d: d.get("rssi", -100) or -100,
            reverse=True,
        )

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if _is_android():
            self._bridge_task = asyncio.create_task(self._bridge_listener())
        else:
            self._task = asyncio.create_task(self._scan_loop())

    async def stop(self) -> None:
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._bridge_task:
            self._bridge_task.cancel()
            self._bridge_task = None

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    async def _bridge_listener(self) -> None:
        from cycling.platform.bridge import device_queue

        while self._running:
            try:
                data = await asyncio.wait_for(device_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                if self._devices:
                    await self._broadcast(
                        {"type": "devices", "devices": self.devices}
                    )
                continue
            addr = data.get("address", "")
            now = datetime.now().isoformat()
            self._devices[addr] = {
                "name": data.get("name", "Unknown"),
                "address": addr,
                "rssi": data.get("rssi"),
                "last_seen": now,
            }
            stale = [
                addr
                for addr, info in self._devices.items()
                if (
                    datetime.now()
                    - datetime.fromisoformat(info["last_seen"])
                ).total_seconds()
                > 60
            ]
            for addr in stale:
                del self._devices[addr]
            await self._broadcast({"type": "devices", "devices": self.devices})

    async def _scan_loop(self) -> None:
        while self._running:
            if not self._paused:
                try:
                    discovered = await scan_devices(timeout=5, cycling_only=True)
                    now = datetime.now().isoformat()
                    for d in discovered:
                        addr = d.get("address", "")
                        if addr not in self._devices or (
                            d.get("rssi") is not None
                            and d.get("rssi", -100)
                            > self._devices[addr].get("rssi", -100)
                        ):
                            self._devices[addr] = {
                                "name": d.get("name", "Unknown"),
                                "address": addr,
                                "rssi": d.get("rssi"),
                                "last_seen": now,
                            }
                        else:
                            self._devices[addr]["last_seen"] = now
                    stale = [
                        addr
                        for addr, info in self._devices.items()
                        if (
                            datetime.now()
                            - datetime.fromisoformat(info["last_seen"])
                        ).total_seconds()
                        > 60
                    ]
                    for addr in stale:
                        del self._devices[addr]
                    device_list = self.devices
                    data: dict[str, Any] = {
                        "type": "devices",
                        "devices": device_list,
                    }
                    await self._broadcast(data)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
            try:
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break

    async def _broadcast(self, data: dict[str, Any]) -> None:
        for q in self._subscribers:
            try:
                await q.put(data)
            except Exception:
                pass

    def subscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.append(queue)

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)
