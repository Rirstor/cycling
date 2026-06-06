from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from cycling.data.models import WorkoutTemplate, WorkoutSegment


@dataclass
class RoutineState:
    status: Literal["idle", "playing", "paused", "completed"] = "idle"
    current_segment_index: int = 0
    segment_elapsed: float = 0.0
    total_elapsed: float = 0.0
    actual_power: list[tuple[float, float]] = field(default_factory=list)
    actual_cadence: list[tuple[float, float]] = field(default_factory=list)
    template: Optional[WorkoutTemplate] = None


class RoutineEngine:
    def __init__(self) -> None:
        self._state = RoutineState()
        self._ftp: int = 200

    @property
    def state(self) -> RoutineState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state.status in ("playing", "paused")

    def set_ftp(self, ftp: int) -> None:
        self._ftp = ftp

    def load(self, template: WorkoutTemplate) -> None:
        self._state = RoutineState(template=template)

    def start(self) -> None:
        if not self._state.template:
            return
        self._state.status = "playing"
        self._state.current_segment_index = 0
        self._state.segment_elapsed = 0.0
        self._state.total_elapsed = 0.0
        self._state.actual_power = []
        self._state.actual_cadence = []

    def pause(self) -> None:
        if self._state.status == "playing":
            self._state.status = "paused"
        elif self._state.status == "paused":
            self._state.status = "playing"

    def stop(self) -> None:
        self._state.status = "idle"

    def tick(self, delta_sec: float, power_watts: Optional[float], cadence_rpm: Optional[float]) -> None:
        if self._state.status != "playing" or not self._state.template:
            return

        self._state.total_elapsed += delta_sec
        self._state.segment_elapsed += delta_sec

        if power_watts is not None:
            self._state.actual_power.append((self._state.total_elapsed, power_watts))
        if cadence_rpm is not None:
            self._state.actual_cadence.append((self._state.total_elapsed, cadence_rpm))

        segments = self._state.template.segments
        while (
            self._state.current_segment_index < len(segments)
            and self._state.segment_elapsed >= segments[self._state.current_segment_index].duration_seconds
        ):
            self._state.segment_elapsed -= segments[self._state.current_segment_index].duration_seconds
            self._state.current_segment_index += 1

        if self._state.current_segment_index >= len(segments):
            self._state.status = "completed"

    def get_current_segment(self) -> Optional[WorkoutSegment]:
        if not self._state.template:
            return None
        segments = self._state.template.segments
        if self._state.current_segment_index >= len(segments):
            return None
        return segments[self._state.current_segment_index]

    def get_targets(self) -> dict[str, Any]:
        seg = self.get_current_segment()
        if not seg:
            return {"target_power": None, "target_cadence": None, "target_type": "power"}

        target_power: Optional[float] = None
        target_cadence: Optional[float] = None

        if seg.target_type in ("power", "both") and seg.target_pct_ftp is not None:
            target_power = round(self._ftp * seg.target_pct_ftp / 100, 1)
        if seg.target_type in ("cadence", "both") and seg.target_cadence_rpm is not None:
            target_cadence = seg.target_cadence_rpm

        return {
            "target_power": target_power,
            "target_cadence": target_cadence,
            "target_type": seg.target_type,
        }

    def evaluate(self, power_watts: Optional[float], cadence_rpm: Optional[float]) -> dict[str, Any]:
        targets = self.get_targets()
        seg = self.get_current_segment()

        power_within_range = True
        cadence_within_range = True
        power_deviation: Optional[float] = None
        cadence_deviation: Optional[float] = None

        if targets["target_power"] is not None and power_watts is not None and targets["target_power"] > 0:
            power_deviation = abs(power_watts - targets["target_power"]) / targets["target_power"]
            power_within_range = power_deviation <= 0.10

        if targets["target_cadence"] is not None and cadence_rpm is not None and targets["target_cadence"] > 0:
            cadence_deviation = abs(cadence_rpm - targets["target_cadence"]) / targets["target_cadence"]
            cadence_within_range = cadence_deviation <= 0.10

        return {
            "within_range": power_within_range and cadence_within_range,
            "power_within_range": power_within_range,
            "cadence_within_range": cadence_within_range,
            "power_deviation_pct": round(power_deviation * 100, 1) if power_deviation is not None else None,
            "cadence_deviation_pct": round(cadence_deviation * 100, 1) if cadence_deviation is not None else None,
        }

    def get_profile(self) -> list[list[float]]:
        if not self._state.template:
            return []
        profile: list[list[float]] = []
        elapsed = 0.0
        for seg in self._state.template.segments:
            target_watts: float = 0
            if seg.target_pct_ftp is not None:
                target_watts = round(self._ftp * seg.target_pct_ftp / 100, 1)
            profile.append([elapsed, target_watts])
            elapsed += seg.duration_seconds
            profile.append([elapsed, target_watts])
        return profile

    def get_total_duration(self) -> float:
        if not self._state.template:
            return 0.0
        return sum(seg.duration_seconds for seg in self._state.template.segments)

    def segment_time_remaining(self) -> float:
        seg = self.get_current_segment()
        if not seg:
            return 0.0
        return max(0.0, seg.duration_seconds - self._state.segment_elapsed)

    def get_sse_data(self) -> dict[str, Any]:
        if not self.is_active:
            return {
                "routine_active": False,
            }

        seg = self.get_current_segment()
        targets = self.get_targets()
        segment_count = len(self._state.template.segments) if self._state.template else 0

        return {
            "routine_active": True,
            "routine_name": self._state.template.name if self._state.template else "",
            "routine_status": self._state.status,
            "segment_index": self._state.current_segment_index,
            "segment_count": segment_count,
            "segment_description": seg.description if seg else "",
            "segment_duration": seg.duration_seconds if seg else 0,
            "segment_elapsed": round(self._state.segment_elapsed, 1),
            "segment_time_remaining": round(self.segment_time_remaining(), 1),
            "total_elapsed": round(self._state.total_elapsed, 1),
            "total_duration": round(self.get_total_duration(), 1),
            **targets,
        }
