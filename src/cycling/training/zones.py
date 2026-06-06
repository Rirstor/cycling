from __future__ import annotations

from cycling.data.models import ZONE_DEFINITIONS, CyclingRecord, TrainingZone


class CogganZones:
    def __init__(self, ftp: int):
        self.ftp = ftp

    def watt_range(self, zone_num: int) -> tuple[int, int]:
        if zone_num < 1 or zone_num > 7:
            raise ValueError(f"Invalid zone number: {zone_num}")
        z = ZONE_DEFINITIONS[zone_num - 1]
        low = int(self.ftp * z["pct_min"] / 100)
        high = int(self.ftp * z["pct_max"] / 100)
        return (low, high)

    def zone_for_power(self, power_watts: float) -> TrainingZone:
        for z in ZONE_DEFINITIONS:
            low = self.ftp * z["pct_min"] / 100
            high = self.ftp * z["pct_max"] / 100
            if low <= power_watts < high:
                return z["zone"]
        return TrainingZone.NEUROMUSCULAR

    def zone_name(self, zone_num: int) -> str:
        return ZONE_DEFINITIONS[zone_num - 1]["name"]

    def describe(self) -> list[dict]:
        result = []
        for z in ZONE_DEFINITIONS:
            low, high = self.watt_range(z["zone"])
            result.append({
                "zone": z["zone"].value,
                "name": z["name"],
                "watt_range": f"{low}-{high} W",
                "pct_range": f"{z['pct_min']}-{z['pct_max']}%",
                "description": z["description"],
            })
        return result

    @staticmethod
    def calculate_time_in_zones(records: list[CyclingRecord], ftp: int) -> dict[str, float]:
        zones = CogganZones(ftp)
        time_in_zones: dict[str, float] = {}
        for z_def in ZONE_DEFINITIONS:
            time_in_zones[z_def["name"]] = 0.0
        for rec in records:
            if rec.power_watts is not None and rec.zone is not None:
                name = zones.zone_name(rec.zone)
                time_in_zones[name] = time_in_zones.get(name, 0) + 1
        return time_in_zones

    @staticmethod
    def calculate_tss(records: list[CyclingRecord], ftp: int) -> float:
        powers = [r.power_watts for r in records if r.power_watts is not None]
        if len(powers) < 30:
            return 0.0
        import statistics
        rolling = []
        for i in range(len(powers) - 29):
            rolling.append(statistics.mean(powers[i:i + 30]))
        fourth_avg = statistics.mean([v ** 4 for v in rolling])
        np_val = fourth_avg ** 0.25 if fourth_avg > 0 else 0
        int_fac = np_val / ftp if ftp > 0 else 0
        hours = len(records) / 3600.0
        return round(int_fac * int_fac * hours * 100, 1)
