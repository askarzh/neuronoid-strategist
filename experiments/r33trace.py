"""Трасса состояния игрока в раунде 33 (с сохранения). uv run python experiments/r33trace.py T0 T1"""
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P
t0, t1 = int(sys.argv[1]), int(sys.argv[2])
out = Path("runs/r33tr"); out.mkdir(parents=True, exist_ok=True)
emu = power_on(); emu.step(frames=30); emu.load_state(open("runs/states/r33.state", "rb").read())
pl = P.Player(); pl.phase = "game"; f = emu.frame()
for t in range(t1):
    k, m = pl.act(f)
    if t >= t0:
        print(t, "balls", P.find_balls(f), "pad", P.find_paddle(f), "est", pl.est, "still", pl.still, "shots", [tr[-1] for tr in pl.shots], "tgt", round(pl.last_target,1) if hasattr(pl,"last_target") else None, "lock", pl.locked, "aim", pl.aim, "lag", pl.lag, "dx", m.dx, "L" if m.left else "")
        Image.fromarray(f).save(out / f"t{t:05d}.png")
    emu.step(k, 1, m); f = emu.frame()
