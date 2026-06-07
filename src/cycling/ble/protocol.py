from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from cycling.data.models import CyclingRecord


class BleClientProtocol(ABC):
    @abstractmethod
    async def connect(
        self, address: str, hr_address: Optional[str] = None, timeout: float = 10.0
    ) -> None: ...

    @abstractmethod
    def stream_data(self) -> AsyncIterator[CyclingRecord]: ...

    @property
    @abstractmethod
    def device_name(self) -> str: ...

    @abstractmethod
    async def disconnect(self) -> None: ...
