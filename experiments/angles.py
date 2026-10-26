"""Как смещение точки удара (мяч − центр ракетки) влияет на отскок. Из одного момента пробуем смещения.
uv run python experiments/angles.py T0 [шаг]"""
import sys, copy
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P

class Off(P.Player):
    off = None
    def choose_offset(self, land, vel):
        return super().choose_offset(land, vel) if self.off is None else self.off

def pad_width(f):
    row = (f[177, 40:217] == 255).all(1); xs = np.flatnonzero(row)
    return len(xs)

T0 = int(sys.argv[1]); step = int(sys.argv[2]) if len(sys.argv) > 2 else 2
emu = power_on(); pl = Off(); emu.step(); f = emu.frame()
for t in range(T0):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
while True:
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    v = pl.track and len(pl.track) > 3 and pl.track[-1][1] - pl.track[0][1] > 0
    if v and 95 < pl.track[-1][1] < 120: break
print("paddle W-run", pad_width(f))
st = emu.save_state(); saved = copy.deepcopy(pl.__dict__)
for off in range(-22, 23, step):
    emu.load_state(st); pl.__dict__ = copy.deepcopy(saved); pl.off = off
    traj = []
    f = emu.frame()
    for t in range(90):
        k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
        b = P.find_balls(f); traj.append((b[0] if b else None, P.find_paddle(f)))
    ys = [b[1] if b else -1 for b, _ in traj]
    i = int(np.argmax(ys)); (bx, by), pad = traj[i]
    after = [b for b, _ in traj[i+1:i+10] if b]
    vx = vy = None
    if len(after) >= 6 and by <= 175:
        vx = (after[-1][0]-after[0][0])/(len(after)-1); vy = (after[-1][1]-after[0][1])/(len(after)-1)
        vx, vy = round(vx, 2), round(vy, 2)
    print(f"off {off:+3d}  y {by} real {bx-pad:+.1f}  out ({vx}, {vy})")
