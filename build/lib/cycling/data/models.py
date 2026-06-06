from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Literal, Optional


class TrainingZone(IntEnum):
    ACTIVE_RECOVERY = 1
    ENDURANCE = 2
    TEMPO = 3
    THRESHOLD = 4
    VO2MAX = 5
    ANAEROBIC = 6
    NEUROMUSCULAR = 7


ZONE_DEFINITIONS: list[dict] = [
    {"zone": TrainingZone.ACTIVE_RECOVERY, "name": "Active Recovery", "pct_min": 0, "pct_max": 55,
     "description": "Very easy spinning, recovery"},
    {"zone": TrainingZone.ENDURANCE, "name": "Endurance", "pct_min": 55, "pct_max": 75,
     "description": "Aerobic base, fat oxidation"},
    {"zone": TrainingZone.TEMPO, "name": "Tempo", "pct_min": 75, "pct_max": 90,
     "description": "Sweet spot, moderate intensity"},
    {"zone": TrainingZone.THRESHOLD, "name": "Threshold", "pct_min": 90, "pct_max": 105,
     "description": "Lactate threshold, FTP range"},
    {"zone": TrainingZone.VO2MAX, "name": "VO2max", "pct_min": 105, "pct_max": 120,
     "description": "Maximum oxygen uptake"},
    {"zone": TrainingZone.ANAEROBIC, "name": "Anaerobic", "pct_min": 120, "pct_max": 150,
     "description": "Anaerobic capacity"},
    {"zone": TrainingZone.NEUROMUSCULAR, "name": "Neuromuscular", "pct_min": 150, "pct_max": 999,
     "description": "Sprint power"},
]


@dataclass
class CyclingRecord:
    timestamp: datetime
    power_watts: Optional[float] = None
    cadence_rpm: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    speed_kph: Optional[float] = None
    zone: Optional[int] = None


@dataclass
class Session:
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    device_name: str = ""
    ftp_at_time: int = 200
    records: list[CyclingRecord] = field(default_factory=list)
    notes: str = ""
    _avg_power: Optional[float] = None
    _normalized_power: Optional[float] = None
    _max_power: Optional[float] = None
    _avg_hr: Optional[float] = None
    _max_hr: Optional[float] = None
    _avg_cadence: Optional[float] = None
    _tss: Optional[float] = None
    _time_in_zones: dict[int, float] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if not self.end_time or not self.start_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def avg_power(self) -> Optional[float]:
        if self._avg_power is not None:
            return self._avg_power
        powers = [r.power_watts for r in self.records if r.power_watts is not None]
        return statistics.mean(powers) if powers else None

    @property
    def normalized_power(self) -> Optional[float]:
        if self._normalized_power is not None:
            return self._normalized_power
        powers = [r.power_watts for r in self.records if r.power_watts is not None]
        if len(powers) < 30:
            return None
        rolling = []
        for i in range(len(powers) - 29):
            window = powers[i:i + 30]
            avg = statistics.mean(window)
            rolling.append(avg)
        if not rolling:
            return None
        fourth_power_avg = statistics.mean([v ** 4 for v in rolling])
        return fourth_power_avg ** 0.25

    @property
    def max_power(self) -> Optional[float]:
        if self._max_power is not None:
            return self._max_power
        powers = [r.power_watts for r in self.records if r.power_watts is not None]
        return max(powers) if powers else None

    @property
    def avg_hr(self) -> Optional[float]:
        if self._avg_hr is not None:
            return self._avg_hr
        hrs = [r.heart_rate_bpm for r in self.records if r.heart_rate_bpm is not None]
        return statistics.mean(hrs) if hrs else None

    @property
    def max_hr(self) -> Optional[float]:
        if self._max_hr is not None:
            return self._max_hr
        hrs = [r.heart_rate_bpm for r in self.records if r.heart_rate_bpm is not None]
        return max(hrs) if hrs else None

    @property
    def avg_cadence(self) -> Optional[float]:
        if self._avg_cadence is not None:
            return self._avg_cadence
        cads = [r.cadence_rpm for r in self.records if r.cadence_rpm is not None]
        return statistics.mean(cads) if cads else None

    @property
    def intensity_factor(self) -> Optional[float]:
        if self.avg_power and self.ftp_at_time:
            return self.avg_power / self.ftp_at_time
        return None

    @property
    def tss(self) -> Optional[float]:
        if self._tss is not None:
            return self._tss
        np = self.normalized_power
        if np and self.ftp_at_time and self.duration_seconds > 0:
            int_fac = np / self.ftp_at_time
            hours = self.duration_seconds / 3600.0
            return int_fac * int_fac * hours * 100
        return None

    @property
    def time_in_zones(self) -> dict[int, float]:
        if self._time_in_zones:
            return self._time_in_zones
        result: dict[int, float] = {}
        for r in self.records:
            if r.zone is not None:
                result[r.zone] = result.get(r.zone, 0) + 1
        return result


@dataclass
class FTPConfig:
    value_watts: int
    date_set: datetime


@dataclass
class WorkoutSegment:
    duration_seconds: int
    target_pct_ftp: float | None = None
    target_cadence_rpm: float | None = None
    target_type: Literal["power", "cadence", "both"] = "power"
    description: str = ""


@dataclass
class WorkoutTemplate:
    name: str
    workout_type: str
    description: str
    target_zone: TrainingZone
    segments: list[WorkoutSegment]
