import time
import pigpio

class MatrixScanner:
    def __init__(self, pi: pigpio.pi, rows: dict[str, int], cols: dict[str, int],
                 key_map: list[dict], debounce_ms: int = 12):
        self.pi = pi
        self.rows = rows
        self.cols = cols
        self.key_map = key_map
        self.debounce = debounce_ms / 1000.0
        # Richtungsannahme: Rows aktiv LOW, Cols mit Pull-Ups lesen.
        for _, pin in rows.items():
            self.pi.set_mode(pin, pigpio.OUTPUT)
            self.pi.write(pin, 1)  # inaktiv = HIGH
        for _, pin in cols.items():
            self.pi.set_mode(pin, pigpio.INPUT)
            self.pi.set_pull_up_down(pin, pigpio.PUD_UP)

        # Lookup: (row_pin, col_pin) -> key_id
        self.lookup = {}
        for k in key_map:
            rp = rows[k["row"]]
            cp = cols[k["col"]]
            self.lookup[(rp, cp)] = k["id"]

        self.state = {k["id"]: False for k in key_map}
        self.last_change = {k["id"]: 0.0 for k in key_map}

    def scan_once(self):
        events = []
        tnow = time.time()
        for rname, rpin in self.rows.items():
            # aktivieren: LOW
            self.pi.write(rpin, 0)
            # kurze Settle-Zeit
            time.sleep(0.0002)
            for cname, cpin in self.cols.items():
                val = self.pi.read(cpin)  # 0 wenn gedrückt (gegen GND)
                key_id = self.lookup.get((rpin, cpin))
                if not key_id:
                    continue
                pressed = (val == 0)
                if pressed != self.state[key_id]:
                    # Debounce
                    if (tnow - self.last_change[key_id]) >= self.debounce:
                        self.state[key_id] = pressed
                        self.last_change[key_id] = tnow
                        events.append(("press" if pressed else "release", key_id))
            # deaktivieren: HIGH
            self.pi.write(rpin, 1)
        return events