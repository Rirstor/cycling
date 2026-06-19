import struct

from cycling.ble.client import _parse_indoor_bike_data


def _build(flags: int, *fields: bytes) -> bytes:
    return struct.pack("<H", flags) + b"".join(fields)


def test_empty_data():
    assert _parse_indoor_bike_data(b"") == {}
    assert _parse_indoor_bike_data(b"\x01") == {}


def test_speed_present():
    flags = 0x0000  # bit 0 = 0 → speed present
    speed_raw = 2500  # 25.00 km/h
    data = struct.pack("<H", flags) + struct.pack("<H", speed_raw)
    result = _parse_indoor_bike_data(data)
    assert result["instantaneous_speed"] == 25.0


def test_speed_not_present():
    flags = 0x0001  # bit 0 = 1 → speed NOT present, no other fields
    data = struct.pack("<H", flags)
    result = _parse_indoor_bike_data(data)
    assert "instantaneous_speed" not in result
    assert result == {}


def test_cadence_present_no_speed():
    flags = 0x0005  # bit 0=1 (no speed), bit 2 (cadence)
    cadence_raw = 170  # 85.0 rpm
    data = _build(flags, struct.pack("<H", cadence_raw))
    result = _parse_indoor_bike_data(data)
    assert result["instantaneous_cadence"] == 85.0


def test_power_present_no_speed():
    flags = 0x0041  # bit 0=1 (no speed), bit 6 (power)
    power_raw = 200  # 200 W
    data = _build(flags, struct.pack("<h", power_raw))
    result = _parse_indoor_bike_data(data)
    assert result["instantaneous_power"] == 200.0


def test_speed_cadence_power():
    flags = 0x0044  # bits 0=0 (speed), 2 (cadence), 6 (power)
    speed_raw = 3000  # 30.00 km/h
    cadence_raw = 170  # 85.0 rpm
    power_raw = 200  # 200 W
    data = _build(
        flags,
        struct.pack("<H", speed_raw),
        struct.pack("<H", cadence_raw),
        struct.pack("<h", power_raw),
    )
    result = _parse_indoor_bike_data(data)
    assert result["instantaneous_speed"] == 30.0
    assert result["instantaneous_cadence"] == 85.0
    assert result["instantaneous_power"] == 200.0


def test_speed_absent_with_cadence_power():
    flags = 0x0045  # bits 0=1 (no speed), 2 (cadence), 6 (power)
    cadence_raw = 170  # 85.0 rpm
    power_raw = 200  # 200 W
    data = _build(
        flags,
        struct.pack("<H", cadence_raw),
        struct.pack("<h", power_raw),
    )
    result = _parse_indoor_bike_data(data)
    assert "instantaneous_speed" not in result
    assert result["instantaneous_cadence"] == 85.0
    assert result["instantaneous_power"] == 200.0


def test_average_speed_no_speed():
    flags = 0x0003  # bit 0=1 (no speed), bit 1 (avg speed)
    avg_speed_raw = 2800  # 28.00 km/h
    data = _build(flags, struct.pack("<H", avg_speed_raw))
    result = _parse_indoor_bike_data(data)
    assert result["average_speed"] == 28.0


def test_average_cadence_no_speed():
    flags = 0x0009  # bit 0=1 (no speed), bit 3 (avg cadence)
    avg_cad_raw = 160  # 80.0 rpm
    data = _build(flags, struct.pack("<H", avg_cad_raw))
    result = _parse_indoor_bike_data(data)
    assert result["average_cadence"] == 80.0


def test_total_distance_no_speed():
    flags = 0x0011  # bit 0=1 (no speed), bit 4 (distance)
    distance = 12345  # 12345 m
    packed = struct.pack("<I", distance)[:3]
    data = _build(flags, packed)
    result = _parse_indoor_bike_data(data)
    assert result["total_distance"] == 12345


def test_resistance_level_no_speed():
    flags = 0x0021  # bit 0=1 (no speed), bit 5 (resistance)
    resistance = 5
    data = _build(flags, struct.pack("<H", resistance))
    result = _parse_indoor_bike_data(data)
    assert result["resistance_level"] == 5


def test_average_power_no_speed():
    flags = 0x0081  # bit 0=1 (no speed), bit 7 (avg power)
    avg_power_raw = 180
    data = _build(flags, struct.pack("<h", avg_power_raw))
    result = _parse_indoor_bike_data(data)
    assert result["average_power"] == 180.0


def test_all_fields():
    speed_raw = 3000
    avg_speed_raw = 2800
    cadence_raw = 170
    avg_cad_raw = 160
    distance = 5000
    resistance = 3
    power_raw = 200
    avg_power_raw = 185

    flags = 0b00000000_11111110
    data = _build(
        flags,
        struct.pack("<H", speed_raw),
        struct.pack("<H", avg_speed_raw),
        struct.pack("<H", cadence_raw),
        struct.pack("<H", avg_cad_raw),
        struct.pack("<I", distance)[:3],
        struct.pack("<H", resistance),
        struct.pack("<h", power_raw),
        struct.pack("<h", avg_power_raw),
    )
    result = _parse_indoor_bike_data(data)
    assert result["instantaneous_speed"] == 30.0
    assert result["average_speed"] == 28.0
    assert result["instantaneous_cadence"] == 85.0
    assert result["average_cadence"] == 80.0
    assert result["total_distance"] == distance
    assert result["resistance_level"] == resistance
    assert result["instantaneous_power"] == 200.0
    assert result["average_power"] == 185.0


def test_truncated_data_does_not_crash():
    flags = 0x0044  # expects speed (2) + cadence (2) + power (2) = 6 bytes
    data = struct.pack("<H", flags) + struct.pack("<H", 3000)
    result = _parse_indoor_bike_data(data)
    assert result.get("instantaneous_speed") == 30.0
    assert "instantaneous_cadence" not in result
    assert "instantaneous_power" not in result
