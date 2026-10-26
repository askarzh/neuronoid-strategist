"""Точность физики симуляции: после отскока от ракетки берём фактическую скорость мяча (по 6 кадрам) и
симулируем от фактической точки; сравниваем первый разбитый кирпич и момент."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P
N = int(sys.argv[1])
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
pend = None; res = []; hist = []
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): pend = None; continue
    balls = P.find_balls(f)
    hist = (hist + [balls[0] if len(balls) == 1 else None])[-8:]
    if pend is None and len(hist) == 8 and all(hist):
        ys = [h[1] for h in hist]
        # первые 2 точки — у ракетки, дальше 6 точек прямо вверх
        if ys[0] >= 171 and ys[1] < ys[0] and all(ys[i+1] < ys[i] for i in range(1, 7)):
            (x0, y0), (x1, y1) = hist[1], hist[7]
            vx, vy = (x1 - x0) / 6, (y1 - y0) / 6
            g = P.read_bricks(f)
            st, h, _, _, _ = P.simulate(g, x1, y1, vx, vy)
            pend = (t, h, st, g)
    elif pend is not None:
        g = P.read_bricks(f)
        d = np.argwhere((pend[3] != 0) & (g != pend[3]))
        if len(d):
            res.append((pend[1], tuple(int(v) for v in d[0]), pend[2], t - pend[0])); pend = None
        elif t - pend[0] > 300:
            res.append((pend[1], None, pend[2], None)); pend = None
same = sum(1 for a, b, *_ in res if a is not None and b is not None and tuple(a) == b)
print("cases", len(res), "same brick", same)
for r in res[:40]: print(r)
