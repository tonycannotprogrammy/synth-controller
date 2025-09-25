from __future__ import annotations

import asyncio
from pathlib import Path

import uvicorn

from .audio import NoteSynth
from .config_store import ConfigStore, default_config
from .controller import SynthController
from .web.server import app as web_app

CONFIG_PATH = Path(__file__).parent / "config.yaml"


async def main() -> None:
    store = ConfigStore(CONFIG_PATH)
    try:
        store.load()
    except FileNotFoundError:
        default_config(CONFIG_PATH)
    controller = SynthController(store, NoteSynth())
    web_app.state.controller = controller
    web_app.state.config_store = store
    cfg = uvicorn.Config("synth.web.server:app", host="127.0.0.1", port=8080, log_level="info")
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
