"""Эффект капсул: при первом появлении капсулы каждого цвета ветвимся — ловим / не ловим — и сравниваем."""
import sys, copy
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Mouse
import player as P

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
out = Path("runs/capfx"); out.mkdir(parents=True, exist_ok=True)

class Catcher(P.Player):
    catch_x = None
    def choose_target(self, ball, vel):
        t = super().choose_target(ball, vel)
        if self.catch_x is not None:
            caps = [c for c in P.find_capsules(self.f) if abs(c[1] - self.catch_x) < 2]
            if caps and vel is not None:
                # ловим, если мяч не на подлёте
                steps = (P.BALL_HIT_Y - ball[1]) / vel[1] if vel[1] > 0 else 999
                if steps > 12:
                    return caps[0][1]
        return t
    def play(self, f):
        self.f = f
        return super().play(f)

def summary(emu, pl, frames, tag, click=False):
    log = []
    f = emu.frame()
    for t in range(frames):
        k, m = pl.act(f)
        if click and t % 30 == 0: m = Mouse(dx=m.dx, left=True)
        emu.step(k, 1, m); f = emu.frame()
        if t in (60, 150, 300, frames - 1):
            Image.fromarray(f).save(out / f"{tag}_{t}.png")
        if t % 30 == 0 and P.in_game(f):
            log.append((len(P.find_balls(f)), P.paddle_half(f), P.count_lives(f), P.read_score(f)))
    return log

emu = power_on(); pl = Catcher(); emu.step(); f = emu.frame()
done = set()
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    for name, x, y in P.find_capsules(f):
        if name in done or y > 120: continue
        done.add(name)
        st = emu.save_state(); saved = copy.deepcopy({k: v for k, v in pl.__dict__.items() if k != "f"})
        for tag, cx in (("avoid", None), ("catch", x)):
            emu.load_state(st); pl.__dict__.update(copy.deepcopy(saved)); pl.catch_x = cx
            log = summary(emu, pl, 400, f"{name}_{tag}", click=(tag == "catch"))
            print(name, t, tag, "balls/halfwidth/lives/score:", log[::2], flush=True)
        emu.load_state(st); pl.__dict__.update(copy.deepcopy(saved)); pl.catch_x = None
