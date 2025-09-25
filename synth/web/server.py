import asyncio, json, yaml
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
clients: set[WebSocket] = set()
STATE = {"keys": {}, "encoders": {}}
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"

@app.get("/")
async def index(req: Request):
    return templates.TemplateResponse("index.html", {"request": req, "state": STATE})

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(60)  # keep alive
    finally:
        clients.remove(ws)

async def broadcast(msg: dict):
    dead = []
    for c in clients:
        try:
            await c.send_text(json.dumps(msg))
        except Exception:
            dead.append(c)
    for d in dead:
        clients.discard(d)

@app.get("/config", response_class=HTMLResponse)
def get_config():
    return f"<pre>{CONFIG_PATH.read_text()}</pre>"

@app.post("/config")
async def post_config(req: Request):
    text = await req.body()
    yaml.safe_load(text)  # validate
    CONFIG_PATH.write_text(text.decode("utf-8"))
    return {"ok": True}

# Helfer für app.py:
async def notify_key(kind: str, key_id: str):
    STATE["keys"][key_id] = (kind == "press")
    await broadcast({"type": "key", "kind": kind, "id": key_id})

async def notify_enc(name: str, delta: int):
    STATE["encoders"][name] = STATE["encoders"].get(name, 0) + delta
    await broadcast({"type": "enc", "name": name, "delta": delta})