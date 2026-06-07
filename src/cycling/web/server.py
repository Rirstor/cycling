from __future__ import annotations

import asyncio
import importlib.resources
import json
import os
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

import cycling.web
from cycling.ble.registry import resolve_identifier
from cycling.data.models import Session
from cycling.data.storage import (
    create_session,
    end_session,
    init_db,
    load_latest_ftp,
    load_session,
    load_sessions,
    save_ftp as storage_save_ftp,
)
from cycling.training.zones import CogganZones
from cycling.training.workouts import list_routines
from cycling.web.ble_manager import BLEManager
from cycling.web.scan_manager import ScanManager

ble_manager = BLEManager()
scan_manager = ScanManager()
templates_dir = importlib.resources.files(cycling.web) / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), cache_size=0)


def render(name: str, request: Request, **context: object) -> HTMLResponse:
    context["request"] = request
    template = jinja_env.get_template(name)
    html = template.render(context)
    return HTMLResponse(html)


app = FastAPI(title="Cycling Dashboard")

static_dir = importlib.resources.files(cycling.web) / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup() -> None:
    await scan_manager.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await ble_manager.disconnect()
    await scan_manager.stop()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    ftp_config = load_latest_ftp()
    ftp = ftp_config.value_watts if ftp_config else 200
    sessions = load_sessions(limit=5)
    return render("index.html", request, active="home", ftp=ftp, sessions=sessions)


@app.get("/live", response_class=HTMLResponse)
async def live_page(request: Request) -> HTMLResponse:
    ftp_config = load_latest_ftp()
    ftp = ftp_config.value_watts if ftp_config else 200
    zones = CogganZones(ftp)
    zone_defs_list = zones.describe()
    return render("live.html", request, active="live", ftp=ftp, zone_defs=zone_defs_list)


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    sessions = load_sessions(limit=50)
    return render("history.html", request, active="history", sessions=sessions)


@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_page(request: Request, session_id: int) -> HTMLResponse:
    s = load_session(session_id)
    if not s:
        return HTMLResponse("Session not found", status_code=404)
    zones = CogganZones(s.ftp_at_time)
    return render("session.html", request, active="history", session=s, zones=zones)


@app.get("/routines", response_class=HTMLResponse)
async def routines_page(request: Request) -> HTMLResponse:
    routines = list_routines()
    return render("routines.html", request, active="routines", routines=routines)


@app.get("/zones", response_class=HTMLResponse)
async def zones_page(request: Request) -> HTMLResponse:
    ftp_config = load_latest_ftp()
    ftp = ftp_config.value_watts if ftp_config else 200
    zones = CogganZones(ftp)
    return render("zones.html", request, active="zones", zones=zones, ftp=ftp)


@app.get("/ftp", response_class=HTMLResponse)
async def ftp_page(request: Request) -> HTMLResponse:
    ftp_config = load_latest_ftp()
    current_ftp = ftp_config.value_watts if ftp_config else 200
    return render("ftp.html", request, active="ftp", ftp=current_ftp)


@app.post("/api/connect")
async def api_connect(
    address: str = Form(...), hr_address: Optional[str] = Form(None)
) -> dict:
    resolved = resolve_identifier(address)
    if not resolved:
        return {"status": "error", "message": f"Unknown device: {address}"}
    hr_resolved = None
    if hr_address:
        hr_resolved = resolve_identifier(hr_address)
        if not hr_resolved:
            return {"status": "error", "message": f"Unknown HR device: {hr_address}"}
    scan_manager.pause()
    try:
        await ble_manager.connect(resolved, hr_resolved)
        return {"status": "ok", "message": f"Connected to {resolved}"}
    except Exception as e:
        scan_manager.resume()
        return {"status": "error", "message": str(e)}


@app.post("/api/disconnect")
async def api_disconnect() -> dict:
    await ble_manager.disconnect()
    scan_manager.resume()
    return {"status": "ok", "message": "Disconnected"}


@app.post("/api/ftp")
async def api_ftp(value: int = Form(...)) -> dict:
    storage_save_ftp(value)
    ble_manager._ftp = value
    return {"status": "ok", "message": f"FTP set to {value} W"}


@app.post("/api/record/start")
async def api_record_start() -> dict:
    if not ble_manager.is_connected:
        return {"status": "error", "message": "Not connected to a trainer"}
    if ble_manager.is_recording:
        return {"status": "error", "message": "Already recording"}
    name = ""
    if ble_manager.client:
        name = ble_manager.client.device_name or ""
    ftp_config = load_latest_ftp()
    ftp = ftp_config.value_watts if ftp_config else 200
    session_id = create_session(name, ftp)
    ble_manager.session_id = session_id
    ble_manager._recording = True
    return {"status": "ok", "session_id": session_id}


@app.post("/api/record/stop")
async def api_record_stop() -> dict:
    if not ble_manager.is_recording or ble_manager.session_id is None:
        return {"status": "error", "message": "Not recording"}
    session_id = ble_manager.session_id
    _ftp_cfg = load_latest_ftp()
    session = Session(
        id=session_id,
        start_time=ble_manager.start_time or datetime.now(),
        end_time=datetime.now(),
        device_name="",
        ftp_at_time=_ftp_cfg.value_watts if _ftp_cfg else 200,
        records=ble_manager.records,
    )
    end_session(session_id, session)
    ble_manager._recording = False
    ble_manager._session_id = None
    return {"status": "ok", "session_id": session_id}


@app.get("/api/routines")
async def api_routines() -> dict:
    return {"routines": list_routines()}


@app.post("/api/routine/start")
async def api_routine_start(name: str = Form(...)) -> dict:
    if not ble_manager.is_connected:
        return {"status": "error", "message": "Not connected to a trainer"}
    try:
        await ble_manager.routine_start(name)
        return {"status": "ok", "message": f"Started routine: {name}"}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/routine/pause")
async def api_routine_pause() -> dict:
    await ble_manager.routine_pause()
    return {"status": "ok"}


@app.post("/api/routine/stop")
async def api_routine_stop() -> dict:
    await ble_manager.routine_stop()
    return {"status": "ok"}


@app.get("/api/routine/profile")
async def api_routine_profile() -> dict:
    engine = ble_manager.routine
    return {
        "profile": engine.get_profile(),
        "total_duration": engine.get_total_duration(),
        "actuals": engine.state.actual_power,
    }


@app.get("/api/routine/preview/{name}")
async def api_routine_preview(name: str) -> dict:
    from cycling.data.storage import load_latest_ftp
    from cycling.training.workouts import get_workout
    from cycling.training.routine_engine import RoutineEngine

    template = get_workout(name)
    if not template:
        return {"profile": [], "total_duration": 0}

    ftp_config = load_latest_ftp()
    ftp = ftp_config.value_watts if ftp_config else 200

    engine = RoutineEngine()
    engine.set_ftp(ftp)
    engine.load(template)
    return {
        "profile": engine.get_profile(),
        "total_duration": engine.get_total_duration(),
    }


@app.get("/events/live")
async def sse_live(request: Request) -> StreamingResponse:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    ble_manager.subscribe(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            ble_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/events/devices")
async def sse_devices(request: Request) -> StreamingResponse:
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    scan_manager.subscribe(queue)

    if scan_manager.devices:
        await queue.put({"type": "devices", "devices": scan_manager.devices})

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            scan_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    import uvicorn
    uvicorn.run("cycling.web.server:app", host="0.0.0.0", port=8080)


def main_android(data_dir: str) -> None:
    """Entry point called from Kotlin via Chaquopy.

    The Android app passes its filesDir so the data layer uses scoped storage
    instead of ~/.cycling.
    """
    os.environ["CYCLING_DATA_DIR"] = data_dir
    init_db()
    import uvicorn
    uvicorn.run(
        "cycling.web.server:app",
        host="127.0.0.1",
        port=8080,
        log_level="info",
        loop="asyncio",
    )
