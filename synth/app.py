from __future__ import annotations

import asyncio
from pathlib import Path

import pigpio
import uvicorn

from .audio import NoteSynth
from .config_store import ConfigStore, default_config
from .controller import SynthController
from .encoder import Encoder
from .matrix import MatrixScanner
from .web.server import app as web_app, push_event

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _ensure_config(store: ConfigStore) -> None:
    try:
        store.load()
    except FileNotFoundError:
        default_config(store.path)


async def main() -> None:
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpio daemon not running; start with `sudo pigpiod`")

    store = ConfigStore(CONFIG_PATH)
    _ensure_config(store)
    controller = SynthController(store, NoteSynth())
    web_app.state.controller = controller
    web_app.state.config_store = store

    config = controller.config
    rows = {key: int(pin) for key, pin in config.matrix.rows.items()}
    cols = {key: int(pin) for key, pin in config.matrix.cols.items()}
    keys = [item.model_dump(mode="python") for item in config.matrix.keys]
    debounce = int(config.app.debounce_ms)
    scanner = MatrixScanner(pi, rows, cols, keys, debounce_ms=debounce)

    loop = asyncio.get_running_loop()

    async def process_key(kind: str, key_id: str) -> None:
        event = controller.handle_key_event(kind, key_id)
        await push_event(event)

    async def process_encoder(name: str, delta: int) -> None:
        event = controller.handle_encoder_event(name, delta)
        await push_event(event)

    encoders: list[Encoder] = []
    for cfg in config.encoders:
        def _cb(name: str, delta: int) -> None:
            loop.call_soon_threadsafe(
                lambda n=name, d=delta: asyncio.create_task(process_encoder(n, d))
            )

        encoders.append(Encoder(pi, cfg.name, int(cfg.A), int(cfg.B), _cb))

    async def scan_loop() -> None:
        while True:
            for kind, key_id in scanner.scan_once():
                await process_key(kind, key_id)
            await asyncio.sleep(0.002)

    async def web_loop() -> None:
        host = config.app.web_host
        port = int(config.app.web_port)
        uv_config = uvicorn.Config("synth.web.server:app", host=host, port=port, log_level="info")
        server = uvicorn.Server(uv_config)
        await server.serve()

    try:
        await asyncio.gather(scan_loop(), web_loop())
    finally:
        for enc in encoders:
            enc.cancel()
        pi.stop()


if __name__ == "__main__":
    asyncio.run(main())
