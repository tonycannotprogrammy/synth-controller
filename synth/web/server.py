from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
clients: set[WebSocket] = set()

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


def _get_controller():
    ctrl = getattr(app.state, "controller", None)
    if ctrl is None:
        raise HTTPException(status_code=503, detail="controller not ready")
    return ctrl


async def notify_clients(message: dict) -> None:
    dead = []
    payload = json.dumps(message)
    for client in list(clients):
        try:
            await client.send_text(payload)
        except Exception:
            dead.append(client)
    for ws in dead:
        clients.discard(ws)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctrl = getattr(app.state, "controller", None)
    state = ctrl.get_runtime_state() if ctrl else {}
    config = ctrl.get_public_config() if ctrl else {}
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "initial_state": json.dumps({"state": state, "config": config}),
        },
    )


@app.get("/api/config")
async def api_get_config():
    ctrl = _get_controller()
    return {
        "config": ctrl.get_public_config(),
        "state": ctrl.get_runtime_state(),
    }


@app.put("/api/config")
async def api_replace_config(request: Request):
    ctrl = _get_controller()
    payload = await request.json()
    try:
        config = await ctrl.replace(payload)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    await notify_clients({"type": "config", "config": config.jsonable()})
    return {"config": config.jsonable()}


@app.post("/api/keys/{key_id}/note")
async def api_set_key_note(key_id: str, request: Request):
    ctrl = _get_controller()
    payload = await request.json()
    note = payload.get("note")
    if not isinstance(note, str):
        raise HTTPException(status_code=400, detail="note must be a string")
    try:
        config = await ctrl.set_key_note(key_id, note)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    await notify_clients({"type": "config", "config": config.jsonable()})
    return {"ok": True}


@app.post("/api/encoders/{name}")
async def api_update_encoder(name: str, request: Request):
    ctrl = _get_controller()
    payload = await request.json()
    try:
        config = await ctrl.update_encoder(name, payload)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    await notify_clients({"type": "config", "config": config.jsonable()})
    return {"ok": True}


@app.post("/api/synth")
async def api_update_synth(request: Request):
    ctrl = _get_controller()
    payload = await request.json()
    try:
        config = await ctrl.update_synth_settings(payload)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    await notify_clients({"type": "config", "config": config.jsonable()})
    return {"ok": True}


@app.post("/api/test-note/{key_id}")
async def api_test_key(key_id: str):
    ctrl = _get_controller()
    try:
        info = await ctrl.test_key(key_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    return info


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    ctrl = getattr(app.state, "controller", None)
    if ctrl:
        await ws.send_json(
            {"type": "state", "state": ctrl.get_runtime_state(), "config": ctrl.get_public_config()}
        )
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:  # pragma: no cover
        raise
    finally:
        clients.discard(ws)


async def push_event(event: dict) -> None:
    await notify_clients(event)
