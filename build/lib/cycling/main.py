from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live

from cycling import __version__
from cycling.ble.registry import device_name_for_address, load_known_devices, mark_device_offline, resolve_identifier
from cycling.data.models import CyclingRecord, Session, ZONE_DEFINITIONS
from cycling.data.storage import (
    create_session,
    end_session,
    init_db,
    load_latest_ftp,
    load_session,
    load_sessions,
    save_ftp as storage_save_ftp,
    save_record,
)
from cycling.training.zones import CogganZones
from cycling.ui.cli import (
    print_discovered_devices,
    render_device_list,
    render_history,
    render_live_dashboard,
    render_session_report,
    render_zone_table,
)

console = Console()
app = typer.Typer(help="Cycling - Indoor cycling training application")
state: dict = {"ftp": 200}


def get_zones() -> CogganZones:
    return CogganZones(state["ftp"])


def load_ftp_from_db() -> int:
    ftp_config = load_latest_ftp()
    if ftp_config:
        state["ftp"] = ftp_config.value_watts
        return ftp_config.value_watts
    return 200


@app.callback()
def main_callback() -> None:
    init_db()
    load_ftp_from_db()


@app.command()
def scan(
    timeout: int = typer.Option(10, "--timeout", "-t", help="Scan duration in seconds"),
    all_devices: bool = typer.Option(False, "--all", "-a", help="Show all BLE devices, not just cycling"),
) -> None:
    """Discover nearby BLE cycling devices (trainers, HR monitors, etc.)"""
    from cycling.ble.scanner import scan_devices

    async def _scan() -> list[dict]:
        return await scan_devices(timeout=timeout, cycling_only=not all_devices)

    try:
        console.print(f"[cyan]Scanning for BLE devices for {timeout}s...[/]")
        devices = asyncio.run(_scan())
        print_discovered_devices(devices)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(code=1)


@app.command()
def devices() -> None:
    """List known BLE devices (online/offline from last scan)"""
    known = load_known_devices()
    render_device_list(known)


def _resolve(identifier: str, what: str = "device") -> str:
    resolved = resolve_identifier(identifier)
    if not resolved:
        console.print(f"[red]Unknown {what}: '{identifier}'. Run [cyan]cycling scan[/] first or provide a valid address.[/]")
        raise typer.Exit(code=1)
    if resolved != identifier:
        name = device_name_for_address(resolved)
        console.print(f"Resolved '[cyan]{identifier}[/]' -> {resolved} ({name})")
    return resolved


@app.command()
def live(
    address: str = typer.Argument(..., help="BLE address or name of the trainer"),
    hr_address: Optional[str] = typer.Option(None, "--hr", help="BLE address or name of HR monitor"),
) -> None:
    """Connect to a trainer and display live data (no recording)"""
    addr = _resolve(address, "trainer")
    hr_addr: Optional[str] = None
    if hr_address:
        hr_addr = _resolve(hr_address, "HR monitor")
    from cycling.ble.client import CyclingClient

    async def _run() -> None:
        client = CyclingClient()
        zones = get_zones()
        try:
            console.print(f"[cyan]Connecting to {addr}...[/]")
            await client.connect(addr, hr_addr)
            console.print("[green]Connected! Streaming live data...[/]")
            records: list[CyclingRecord] = []
            time_in_zones: dict[int, float] = {}
            for z_def in ZONE_DEFINITIONS:
                time_in_zones[z_def["zone"].value] = 0.0
            start_time = datetime.now()
            last_power: Optional[float] = None
            last_cad: Optional[float] = None
            last_hr: Optional[float] = None

            with Live(refresh_per_second=4, screen=True) as live:
                async for record in client.stream_data():
                    records.append(record)
                    elapsed = int((datetime.now() - start_time).total_seconds())
                    if record.power_watts is not None:
                        zn = zones.zone_for_power(record.power_watts)
                        record.zone = zn
                        time_in_zones[zn] = time_in_zones.get(zn, 0) + 1
                    if record.power_watts is not None:
                        last_power = record.power_watts
                    if record.cadence_rpm is not None:
                        last_cad = record.cadence_rpm
                    if record.heart_rate_bpm is not None:
                        last_hr = record.heart_rate_bpm
                    avg_power = sum(r.power_watts for r in records if r.power_watts is not None) / max(len([r for r in records if r.power_watts is not None]), 1)
                    avg_hr = sum(r.heart_rate_bpm for r in records if r.heart_rate_bpm is not None) / max(len([r for r in records if r.heart_rate_bpm is not None]), 1)
                    avg_cad = sum(r.cadence_rpm for r in records if r.cadence_rpm is not None) / max(len([r for r in records if r.cadence_rpm is not None]), 1)
                    if record.power_watts is None:
                        record.power_watts = last_power
                    if record.cadence_rpm is None:
                        record.cadence_rpm = last_cad
                    if record.heart_rate_bpm is None:
                        record.heart_rate_bpm = last_hr
                    layout = render_live_dashboard(
                        record, zones, elapsed, avg_power, avg_hr, avg_cad, time_in_zones
                    )
                    live.update(layout)

        except asyncio.TimeoutError:
            console.print("[red]Connection timed out. Is the device powered on and in range?[/]")
        except Exception as e:
            console.print(f"[red]Connection failed: {e}[/]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Disconnecting...[/]")
        finally:
            await client.disconnect()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


@app.command()
def record(
    address: str = typer.Argument(..., help="BLE address or name of the trainer"),
    hr_address: Optional[str] = typer.Option(None, "--hr", help="BLE address or name of HR monitor"),
) -> None:
    """Connect to trainer, record session data to database"""
    addr = _resolve(address, "trainer")
    hr_addr: Optional[str] = None
    if hr_address:
        hr_addr = _resolve(hr_address, "HR monitor")
    from cycling.ble.client import CyclingClient

    async def _run() -> None:
        client = CyclingClient()
        zones = get_zones()
        session_id: Optional[int] = None
        records: list[CyclingRecord] = []
        start_time = datetime.now()
        try:
            console.print(f"[cyan]Connecting to {addr}...[/]")
            await client.connect(addr, hr_addr)
            console.print("[green]Connected! Recording session. Press Ctrl+C to stop.[/]")
            session_id = create_session(client.device_name, state["ftp"])
            time_in_zones: dict[int, float] = {}
            for z_def in ZONE_DEFINITIONS:
                time_in_zones[z_def["zone"].value] = 0.0
            last_power: Optional[float] = None
            last_cad: Optional[float] = None
            last_hr: Optional[float] = None

            with Live(refresh_per_second=4, screen=True) as live:
                async for record in client.stream_data():
                    records.append(record)
                    elapsed = int((datetime.now() - start_time).total_seconds())
                    if record.power_watts is not None:
                        zn = zones.zone_for_power(record.power_watts)
                        record.zone = zn
                        time_in_zones[zn] = time_in_zones.get(zn, 0) + 1
                    if record.power_watts is not None:
                        last_power = record.power_watts
                    if record.cadence_rpm is not None:
                        last_cad = record.cadence_rpm
                    if record.heart_rate_bpm is not None:
                        last_hr = record.heart_rate_bpm
                    if record.power_watts is None:
                        record.power_watts = last_power
                    if record.cadence_rpm is None:
                        record.cadence_rpm = last_cad
                    if record.heart_rate_bpm is None:
                        record.heart_rate_bpm = last_hr
                    save_record(session_id, record)
                    avg_power = sum(r.power_watts for r in records if r.power_watts is not None) / max(len([r for r in records if r.power_watts is not None]), 1)
                    avg_hr = sum(r.heart_rate_bpm for r in records if r.heart_rate_bpm is not None) / max(len([r for r in records if r.heart_rate_bpm is not None]), 1)
                    avg_cad = sum(r.cadence_rpm for r in records if r.cadence_rpm is not None) / max(len([r for r in records if r.cadence_rpm is not None]), 1)
                    layout = render_live_dashboard(
                        record, zones, elapsed, avg_power, avg_hr, avg_cad, time_in_zones
                    )
                    live.update(layout)

        except asyncio.TimeoutError:
            console.print("[red]Connection timed out. Is the device powered on and in range?[/]")
        except Exception as e:
            console.print(f"[red]Connection failed: {e}[/]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Finishing session...[/]")
        finally:
            if session_id is not None:
                session = Session(
                    id=session_id,
                    start_time=start_time,
                    end_time=datetime.now(),
                    device_name=addr,
                    ftp_at_time=state["ftp"],
                    records=records,
                )
                end_session(session_id, session)
                console.print(f"[green]Session #{session_id} saved![/]")
            await client.disconnect()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of sessions to show"),
) -> None:
    """List past training sessions"""
    sessions = load_sessions(limit=limit)
    render_history(sessions)


@app.command()
def session(
    session_id: int = typer.Argument(..., help="Session ID to view"),
) -> None:
    """View detailed report for a past session"""
    s = load_session(session_id)
    if not s:
        console.print(f"[red]Session #{session_id} not found.[/]")
        raise typer.Exit(code=1)
    zones = CogganZones(s.ftp_at_time)
    render_session_report(s, zones)


@app.command()
def ftp(
    value: Optional[int] = typer.Argument(None, help="Set FTP value in watts"),
) -> None:
    """Get or set your Functional Threshold Power"""
    if value is not None:
        storage_save_ftp(value)
        state["ftp"] = value
        console.print(f"[green]FTP set to {value} W[/]")
    else:
        console.print(f"Current FTP: [bold]{state['ftp']} W[/]")


@app.command()
def zones() -> None:
    """Display your current training zones based on FTP"""
    render_zone_table(get_zones())


@app.command()
def version() -> None:
    """Show the application version"""
    console.print(f"[cyan]cycling[/] version [bold]{__version__}[/]")


if __name__ == "__main__":
    app()
