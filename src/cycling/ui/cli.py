from __future__ import annotations

from datetime import datetime

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from cycling.data.models import CyclingRecord, Session, ZONE_DEFINITIONS
from cycling.training.zones import CogganZones

console = Console()

ZONE_COLORS = {
    1: "blue",
    2: "green",
    3: "yellow",
    4: "orange1",
    5: "red",
    6: "magenta",
    7: "bright_white",
}


def build_live_layout(record: CyclingRecord, zones: CogganZones, elapsed: int,
                      avg_power: float, avg_hr: float, avg_cad: float,
                      time_in_zones: dict[int, float]) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=6),
        Layout(name="middle", size=3),
        Layout(name="bottom", size=6),
    )

    zone_num = 2
    if record.power_watts is not None:
        zone_num = zones.zone_for_power(record.power_watts)
    zone_name = zones.zone_name(zone_num)
    zone_color = ZONE_COLORS.get(zone_num, "white")

    power_str = f"{record.power_watts:.0f}" if record.power_watts is not None else "--"
    hr_str = f"{record.heart_rate_bpm:.0f}" if record.heart_rate_bpm is not None else "--"
    cad_str = f"{record.cadence_rpm:.0f}" if record.cadence_rpm is not None else "--"

    top_grid = Table.grid(padding=(0, 4))
    top_grid.add_row(
        Panel(Align.center(Text(f"{power_str}", style="bold white")), title="Power (W)",
              border_style="cyan"),
        Panel(Align.center(Text(f"{hr_str}", style="bold white")), title="Heart Rate",
              border_style="red"),
        Panel(Align.center(Text(f"{cad_str}", style="bold white")), title="Cadence (RPM)",
              border_style="green"),
        Panel(Align.center(Text(f"Zone {zone_num}", style=f"bold {zone_color}")),
              title=zone_name, border_style=zone_color),
    )
    layout["top"].update(top_grid)

    pct = min(record.power_watts / zones.ftp * 100, 200) if record.power_watts is not None and zones.ftp > 0 else 0
    bar = ProgressBar(total=200, completed=pct, width=30)
    mins, secs = divmod(elapsed, 60)
    middle_grid = Table.grid(padding=(0, 2))
    middle_grid.add_row(
        Panel(Align.center(bar), title="Power (% FTP)"),
        Panel(Align.center(f"Elapsed: {mins:02d}:{secs:02d}"), title="Session Time"),
    )
    layout["middle"].update(middle_grid)

    bottom_grid = Table.grid(padding=(0, 2))
    stats = Table(title="Session Averages")
    stats.add_column("Metric", style="cyan")
    stats.add_column("Value", style="white")
    stats.add_row("Avg Power", f"{avg_power:.0f} W" if avg_power else "--")
    stats.add_row("Avg HR", f"{avg_hr:.0f} bpm" if avg_hr else "--")
    stats.add_row("Avg Cadence", f"{avg_cad:.0f} rpm" if avg_cad else "--")
    stats.add_row("Time", f"{elapsed // 60}m {elapsed % 60}s")

    zone_table = Table(title="Time in Zones")
    zone_table.add_column("Zone", style="cyan")
    zone_table.add_column("Time (s)", style="white")
    zone_table.add_column("Bar", no_wrap=True)
    total_zone_time = sum(time_in_zones.values())
    for z in ZONE_DEFINITIONS:
        zn = z["zone"].value
        t = time_in_zones.get(zn, 0)
        pct = (t / total_zone_time * 100) if total_zone_time > 0 else 0
        bar_len = int(pct / 5)
        bar_str = "█" * bar_len
        zone_table.add_row(f"Z{zn}", f"{t:.0f}", f"[{ZONE_COLORS[zn]}]{bar_str}[/]")

    bottom_grid.add_row(stats, zone_table)
    layout["bottom"].update(bottom_grid)

    return layout


def render_live_dashboard(record: CyclingRecord, zones: CogganZones, elapsed: int,
                          avg_power: float, avg_hr: float, avg_cad: float,
                          time_in_zones: dict[int, float]) -> Layout:
    return build_live_layout(record, zones, elapsed, avg_power, avg_hr, avg_cad, time_in_zones)


def render_session_report(session: Session, zones: CogganZones) -> None:
    console.print(f"\n[bold cyan]Session #{session.id} Report[/]")
    console.print(f"Device: {session.device_name}")
    console.print(f"Start: {session.start_time.strftime('%Y-%m-%d %H:%M')}")
    dur = session.duration_seconds
    console.print(f"Duration: {int(dur // 60)}m {int(dur % 60)}s")
    console.print(f"FTP: {session.ftp_at_time} W")

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Avg Power", f"{session.avg_power:.0f} W" if session.avg_power else "--")
    table.add_row("Normalized Power", f"{session.normalized_power:.0f} W" if session.normalized_power else "--")
    table.add_row("Max Power", f"{session.max_power:.0f} W" if session.max_power else "--")
    table.add_row("Avg HR", f"{session.avg_hr:.0f} bpm" if session.avg_hr else "--")
    table.add_row("Max HR", f"{session.max_hr:.0f} bpm" if session.max_hr else "--")
    table.add_row("Avg Cadence", f"{session.avg_cadence:.0f} rpm" if session.avg_cadence else "--")
    table.add_row("IF", f"{session.intensity_factor:.2f}" if session.intensity_factor else "--")
    table.add_row("TSS", f"{session.tss:.1f}" if session.tss else "--")
    console.print(table)

    zone_table = Table(title="Time in Zones")
    zone_table.add_column("Zone", style="cyan")
    zone_table.add_column("Time", style="white")
    zone_table.add_column("%", style="white")
    total_zone = sum(session.time_in_zones.values())
    for z_def in ZONE_DEFINITIONS:
        zn = z_def["zone"].value
        t = session.time_in_zones.get(zn, 0)
        pct = (t / total_zone * 100) if total_zone > 0 else 0
        zone_table.add_row(z_def["name"], f"{t:.0f}s", f"{pct:.1f}%")
    console.print(zone_table)

    from cycling.training.workouts import match_workout_type
    matched = match_workout_type(
        {z_def["name"]: session.time_in_zones.get(z_def["zone"].value, 0) for z_def in ZONE_DEFINITIONS},
        dur
    )
    console.print(f"\nSuggested workout type: [bold]{matched}[/]")


def render_zone_table(zones: CogganZones) -> None:
    table = Table(title=f"Training Zones (FTP: {zones.ftp} W)")
    table.add_column("Zone", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Watts", style="green")
    table.add_column("% FTP", style="yellow")
    table.add_column("Description")
    for z in zones.describe():
        table.add_row(
            str(z["zone"]),
            z["name"],
            z["watt_range"],
            z["pct_range"],
            z["description"],
        )
    console.print(table)


def render_history(sessions: list[Session]) -> None:
    if not sessions:
        console.print("[yellow]No past sessions found.[/]")
        return
    table = Table(title="Session History")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="white")
    table.add_column("Duration", style="white")
    table.add_column("Avg Power", style="green")
    table.add_column("Avg HR", style="red")
    table.add_column("TSS", style="yellow")
    table.add_column("Device", style="blue")
    for s in sessions:
        dur = s.duration_seconds
        dur_str = f"{int(dur // 60)}m" if dur else "--"
        date_str = s.start_time.strftime("%m/%d %H:%M")
        table.add_row(
            str(s.id),
            date_str,
            dur_str,
            f"{s.avg_power:.0f}W" if s.avg_power else "--",
            f"{s.avg_hr:.0f}" if s.avg_hr else "--",
            f"{s.tss:.0f}" if s.tss else "--",
            s.device_name,
        )
    console.print(table)


def print_discovered_devices(devices: list[dict]) -> None:
    if not devices:
        console.print("[yellow]No BLE cycling devices found. Try a longer scan or check Bluetooth is on.[/]")
        return
    table = Table(title="Discovered BLE Devices")
    table.add_column("#", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Address", style="green")
    table.add_column("RSSI", style="yellow")
    table.add_column("Services", style="white")
    for i, d in enumerate(devices, 1):
        services = ", ".join(d["services"]) if d["services"] else "N/A"
        table.add_row(str(i), d["name"], d["address"], str(d["rssi"] or "?"), services)
    console.print(table)
    console.print(f"\n[bold]Total: {len(devices)} device(s)[/]")
    if devices:
        console.print("\nTip: use a device [cyan]name[/] instead of address:\n      [dim]cycling live <name>[/]")


def render_device_list(devices: list[dict]) -> None:
    if not devices:
        console.print("[yellow]No known devices. Run [cyan]cycling scan[/] first.[/]")
        return
    table = Table(title="Known Devices")
    table.add_column("Name", style="cyan")
    table.add_column("Address", style="green")
    table.add_column("Status", style="white")
    table.add_column("Last Seen", style="dim")
    for d in devices:
        status = "[green]Online[/]" if d.get("online") else "[red]Offline[/]"
        last_seen = ""
        if d.get("last_seen"):
            last_seen = datetime.fromisoformat(d["last_seen"]).strftime("%m/%d %H:%M")
        table.add_row(d["name"], d["address"], status, last_seen)
    console.print(table)
