import pigpio

class Encoder:
    def __init__(self, pi: pigpio.pi, name: str, A: int, B: int, callback):
        self.pi = pi
        self.name = name
        self.A, self.B = A, B
        self.callback = callback  # def cb(name:str, delta:int)
        self.level_A = 0
        self.level_B = 0

        for p in (A, B):
            self.pi.set_mode(p, pigpio.INPUT)
            self.pi.set_pull_up_down(p, pigpio.PUD_UP)

        self.cbA = self.pi.callback(A, pigpio.EITHER_EDGE, self._edge)
        self.cbB = self.pi.callback(B, pigpio.EITHER_EDGE, self._edge)

    def _edge(self, gpio, level, tick):
        if gpio == self.A:
            self.level_A = level
        else:
            self.level_B = level
        # 2-Bit-Zustände auswerten:
        if self.level_A == 0 and self.level_B == 1:
            self.callback(self.name, +1)
        elif self.level_A == 1 and self.level_B == 0:
            self.callback(self.name, -1)

    def cancel(self):
        self.cbA.cancel()
        self.cbB.cancel()