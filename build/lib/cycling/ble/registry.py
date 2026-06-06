from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path.home() / ".cycling" / "devices.json"


def _load_raw() -> dict[str, dict]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_raw(data: dict[str, dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, indent=2))


def save_scanned_devices(devices: list[dict]) -> None:
    known = _load_raw()
    seen_addrs = set()
    for d in devices:
        addr = d["address"]
        name = d["name"] or "Unknown"
        seen_addrs.add(addr)
        if addr in known:
            known[addr]["name"] = name
            known[addr]["online"] = True
            known[addr]["last_seen"] = datetime.now().isoformat()
        else:
            known[addr] = {
                "name": name,
                "address": addr,
                "online": True,
                "last_seen": datetime.now().isoformat(),
                "services": d.get("services", []),
            }
    for addr in known:
        if addr not in seen_addrs:
            known[addr]["online"] = False
    _save_raw(known)


def mark_device_offline(address: str) -> None:
    known = _load_raw()
    if address in known:
        known[address]["online"] = False
    _save_raw(known)


def load_known_devices() -> list[dict]:
    return sorted(_load_raw().values(), key=lambda d: d.get("last_seen", ""), reverse=True)


def resolve_identifier(identifier: str) -> Optional[str]:
    known = _load_raw()
    for addr, info in known.items():
        if info["name"].lower() == identifier.lower():
            return addr
    for addr in known:
        if addr.upper() == identifier.upper():
            return addr
    if ":" in identifier and len(identifier) == 17:
        return identifier.upper()
    return None


def device_name_for_address(address: str) -> str:
    known = _load_raw()
    entry = known.get(address)
    return entry["name"] if entry else address
