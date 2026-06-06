from __future__ import annotations

from typing import Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from cycling.ble.registry import save_scanned_devices

SERVICE_UUIDS = {
    "00001826-0000-1000-8000-00805f9b34fb": "Fitness Machine (FTMS)",
    "00001818-0000-1000-8000-00805f9b34fb": "Cycling Power (CPS)",
    "00001816-0000-1000-8000-00805f9b34fb": "Cycling Speed/Cadence (CSCS)",
    "0000180d-0000-1000-8000-00805f9b34fb": "Heart Rate (HRS)",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery (BAS)",
}

CYCLING_SERVICE_UUIDS = {u.lower() for u in SERVICE_UUIDS}


def is_cycling_device(device: BLEDevice, adv_data: AdvertisementData | None = None) -> bool:
    if device.name and any(kw in device.name.lower() for kw in ["kickr", "tacx", "neo", "suito", "wahoo",
                                                                  "elite", "zwift", "hub", "hammer",
                                                                  "h3", "flux", "snap", "dragon",
                                                                  "stages", "garmin", "assist"]):
        return True
    if adv_data and adv_data.service_uuids:
        for uuid in adv_data.service_uuids:
            if uuid.lower() in CYCLING_SERVICE_UUIDS:
                return True
    return False


async def scan_devices(timeout: int = 10, cycling_only: bool = True) -> list[dict]:
    try:
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    except Exception as e:
        msg = str(e)
        if "org.bluez" in msg:
            raise RuntimeError(
                "Bluetooth is not available. On WSL, install Python on Windows "
                "and run from there, or use a Linux system with Bluetooth."
            ) from e
        raise RuntimeError(f"Bluetooth scan failed: {msg}") from e
    results = []
    for d, adv_data in devices.values():
        if cycling_only and not is_cycling_device(d, adv_data):
            continue
        service_names = []
        if adv_data and adv_data.service_uuids:
            for uuid in adv_data.service_uuids:
                name = SERVICE_UUIDS.get(uuid, f"Unknown ({uuid[:8]}...)")
                service_names.append(name)
        results.append({
            "name": d.name or "Unknown",
            "address": d.address,
            "rssi": adv_data.rssi if adv_data else None,
            "services": service_names,
            "details": d,
        })
    results.sort(key=lambda x: x["rssi"] or -100, reverse=True)
    save_scanned_devices(results)
    return results


async def get_device_by_address(address: str) -> Optional[BLEDevice]:
    devices = await BleakScanner.discover(timeout=5)
    for d in devices:
        if d.address.upper() == address.upper():
            return d
    return None
