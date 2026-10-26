"""Прогнать Player до кадра T0, потом записывать кадры и внутреннее состояние игрока до T1.
uv run python experiments/trace.py T0 T1 папка"""
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P

t0, t1, outdir = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
for p in out.glob("*.png"): p.unlink()
emu = power_on(); pl = P.Player()
emu.step(); f = emu.frame()
for t in range(t1):
    keys, mouse = pl.act(f)
    if t >= t0:
        ball = P.find_ball(f); pad = P.find_paddle(f)
        print(t, "ball", ball, "trk", pl.track[-3:], "aim", pl.aim, "pad", pad, "est", pl.est, "dx", mouse.dx, "L" if mouse.left else "")
        Image.fromarray(f).save(out / f"t{t:06d}.png")
    emu.step(keys, frames=1, mouse=mouse)
    f = emu.frame()
