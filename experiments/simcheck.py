"""Точность симуляции: на каждом отскоке от ракетки сравнить предсказанную первую траекторию с фактической."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P

class Rec(P.Player):
    def choose_offset(self, land, vel):
        off = super().choose_offset(land, vel)
        speed = (vel[0] ** 2 + vel[1] ** 2) ** 0.5
        u = dict(P.ZONES)[off] if off in dict(P.ZONES) else None
        self.pred = None
        if u is not None:
            # предсказанный путь до первого кирпича
            path = []
            self.pred = (land, u, speed, P.simulate(self.grid, land, P.BALL_HIT_Y, u[0]*speed, u[1]*speed)[:2], self.grid.copy())
        return off

N = int(sys.argv[1])
emu = power_on(); pl = Rec(); pl.pred = None; emu.step(); f = emu.frame()
pending = None; rows = []
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    tr = pl.track
    # отскок от ракетки: мяч у низа и пошёл вверх
    if pl.pred is not None and tr and len(tr) == 3 and tr[-1][1] < tr[0][1] and tr[0][1] >= 168:
        pending = (t, pl.pred, P.read_bricks(f)); pl.pred = None
    if pending is not None:
        g = P.read_bricks(f)
        diff = np.argwhere((pending[2] != 0) & (g != pending[2]))
        if len(diff):
            t0, (land, u, sp, (pt, ph), _), _ = pending
            rows.append((pt, ph, t - t0, tuple(diff[0])))
            pending = None
        elif t - pending[0] > 400:
            pending = None
ok = sum(1 for pt, ph, at, ah in rows if ph is not None and tuple(ph) == ah)
near = sum(1 for pt, ph, at, ah in rows if ph is not None and abs(pt - at) < 10)
print("bounces with a brick hit:", len(rows), "predicted same brick:", ok, "time within 10f:", near)
for r in rows[:40]: print(r)
