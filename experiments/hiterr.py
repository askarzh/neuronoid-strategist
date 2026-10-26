"""Ошибка точки удара: фактическое смещение мяча от центра ракетки в момент отскока минус плановое (aim)."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import os, importlib.util
spec = importlib.util.spec_from_file_location("player", os.environ.get("PLAYER", "player.py")); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
N = int(sys.argv[1])
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
hist = []; errs = Counter(); rows = []
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    b = P.find_balls(f); pad = P.find_paddle(f)
    hist.append((b[0] if len(b) == 1 else None, pad, pl.aim))
    hist = hist[-6:]
    # отскок: y мяча был максимален в hist[-3]
    if len(hist) == 6 and all(h[0] for h in hist[1:]):
        ys = [h[0][1] for h in hist[1:]]
        if ys[1] >= 171 and ys[1] >= ys[0] and ys[1] > ys[2] and ys[1] >= ys[3]:
            (bx, by), pad, aim = hist[2]
            if pad is not None and aim is not None:
                e = (bx - pad) - aim
                errs[round(e)] += 1; rows.append((t, bx - pad, aim))
print(sorted(errs.items()))
print(rows[:30])
