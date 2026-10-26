"""Эффект капсул: при первом появлении капсулы каждого цвета ветвимся — ловим (встроенной логикой игрока)
или избегаем — и сравниваем скорость мяча, ширину ракетки, число мячей, реакцию на клики."""
import sys, copy
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Mouse
import player as P

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
out = Path("runs/capfx"); out.mkdir(parents=True, exist_ok=True)
ALL = set(P.CAPSULE_COLORS.values())

def branch(emu, pl, tag, frames=500):
    f = emu.frame(); speeds = []; balls = []; halves = []
    for t in range(frames):
        k, m = pl.act(f)
        if t > 150 and t % 8 < 2: m = Mouse(dx=m.dx, left=True)   # пробуем кликать
        emu.step(k, 1, m); f = emu.frame()
        if P.in_game(f):
            if len(pl.track) >= 6:
                tr = pl.track; n = len(tr)
                speeds.append(((tr[-1][0]-tr[0][0])**2 + (tr[-1][1]-tr[0][1])**2) ** 0.5 / (n-1))
            balls.append(len(P.find_balls(f))); halves.append(P.paddle_half(f))
        if t in (120, 200, 300):
            Image.fromarray(f).resize((640, 400), Image.NEAREST).save(out / f"{tag}_{t}.png")
    sp = np.array(speeds)
    return f"speed early {sp[:100].mean() if len(sp) else 0:.2f} late {sp[-100:].mean() if len(sp) else 0:.2f} maxballs {max(balls or [0])} half {max([h for h in halves if h] or [0])} score {P.read_score(f)}"

emu = power_on(); pl = P.Player(); pl.avoid = set(ALL); emu.step(); f = emu.frame()
done = set(); prev = []
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    caps = pl.caps_prev
    for name, x, y in caps:
        if name in done or not 60 < y < 120: continue
        done.add(name)
        st = emu.save_state(); saved = copy.deepcopy(pl.__dict__)
        for tag, avoid in (("avoid", ALL), ("catch", ALL - {name})):
            emu.load_state(st); pl.__dict__ = copy.deepcopy(saved); pl.avoid = set(avoid)
            print(name, t, tag, branch(emu, pl, f"{name}_{tag}"), flush=True)
        emu.load_state(st); pl.__dict__ = copy.deepcopy(saved); pl.avoid = set(ALL)
