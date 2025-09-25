import asyncio, yaml, pigpio
from pathlib import Path
from .matrix import MatrixScanner
from .encoder import Encoder
from .web.server import app as web_app, notify_key, notify_enc
import uvicorn

CFG = yaml.safe_load((Path(__file__).parent/"config.yaml").read_text())

async def main():
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpio daemon not running")

    rows = {k:int(v) for k,v in CFG["matrix"]["rows"].items()}
    cols = {k:int(v) for k,v in CFG["matrix"]["cols"].items()}
    keys = CFG["matrix"]["keys"]
    debounce = int(CFG["app"]["debounce_ms"])

    scanner = MatrixScanner(pi, rows, cols, keys, debounce_ms=debounce)

    encs = []
    for e in CFG["encoders"]:
        encs.append(Encoder(pi, e["name"], int(e["A"]), int(e["B"]),
                            lambda name, d: asyncio.create_task(notify_enc(name, d))))

    async def scan_loop():
        while True:
            for kind, kid in scanner.scan_once():
                await notify_key(kind, kid)
            await asyncio.sleep(0.002)  # ~500 Hz Scan

    async def web_loop():
        host = CFG["app"]["web_host"]; port = int(CFG["app"]["web_port"])
        config = uvicorn.Config("synth.web.server:app", host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    await asyncio.gather(scan_loop(), web_loop())

if __name__ == "__main__":
    asyncio.run(main())