from datetime import datetime

from cycling.data.models import CyclingRecord, TrainingZone
from cycling.training.zones import CogganZones


def test_zone_for_power():
    zones = CogganZones(ftp=200)
    assert zones.zone_for_power(80) == TrainingZone.ACTIVE_RECOVERY
    assert zones.zone_for_power(130) == TrainingZone.ENDURANCE
    assert zones.zone_for_power(160) == TrainingZone.TEMPO
    assert zones.zone_for_power(200) == TrainingZone.THRESHOLD
    assert zones.zone_for_power(230) == TrainingZone.VO2MAX
    assert zones.zone_for_power(280) == TrainingZone.ANAEROBIC
    assert zones.zone_for_power(350) == TrainingZone.NEUROMUSCULAR


def test_watt_range():
    zones = CogganZones(ftp=250)
    low, high = zones.watt_range(2)
    assert low == 137
    assert high == 187
    low2, high2 = zones.watt_range(4)
    assert low2 == 225
    assert high2 == 262


def test_zone_names():
    zones = CogganZones(ftp=200)
    assert zones.zone_name(1) == "Active Recovery"
    assert zones.zone_name(5) == "VO2max"


def test_describe():
    zones = CogganZones(ftp=200)
    desc = zones.describe()
    assert len(desc) == 7
    assert desc[0]["name"] == "Active Recovery"
    assert desc[0]["watt_range"] == "0-110 W"


def test_calculate_time_in_zones():
    zones = CogganZones(ftp=200)
    records = [
        CyclingRecord(timestamp=datetime.now(), power_watts=100, zone=2),
        CyclingRecord(timestamp=datetime.now(), power_watts=100, zone=2),
        CyclingRecord(timestamp=datetime.now(), power_watts=180, zone=4),
    ]
    time_in_zones = CogganZones.calculate_time_in_zones(records, 200)
    assert time_in_zones["Endurance"] == 2
    assert time_in_zones["Threshold"] == 1


def test_calculate_tss():
    records = [
        CyclingRecord(timestamp=datetime.now(), power_watts=200)
        for _ in range(60)
    ]
    tss = CogganZones.calculate_tss(records, 200)
    assert tss > 0
    assert tss < 100
