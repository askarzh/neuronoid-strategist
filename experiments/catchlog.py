"""Ловим все капсулы; после каждой поимки сохраняем ракетку крупно и проверяем реакцию на клик."""
import sys, copy
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Mouse
import player as P

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
out = Path("runs/catchlog"); out.mkdir(parents=True, exist_ok=True)
for p in out.glob("*.png"): p.unlink()
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
watch = {}  # capsule seen near paddle -> check disappearance
last_caps = []
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    caps = P.find_capsules(f)
    # капсула исчезла у ракетки (y низа >= 170) -> поймана
    for name, x, y in last_caps:
        if y >= 168 and not any(c[1] == x and c[0] == name for c in caps):
            pad = P.find_paddle(f)
            caught = pad is not None and abs(pad - x) < pl.pad_half + 4
            if caught:
                st = emu.save_state(); saved = copy.deepcopy(pl.__dict__)
                g = f
                for i in range(40):
                    k, m = pl.act(g); emu.step(k, 1, m); g = emu.frame()
                Image.fromarray(g[150:200, 30:225]).resize((780, 200), Image.NEAREST).save(out / f"{t:06d}_{name}_noclick.png")
                emu.load_state(st); pl.__dict__ = copy.deepcopy(saved); g = f
                for i in range(40):
                    k, m = pl.act(g); emu.step(k, 1, Mouse(dx=m.dx, left=(i % 6 < 2))); g = emu.frame()
                Image.fromarray(g).resize((960, 600), Image.NEAREST).save(out / f"{t:06d}_{name}_click.png")
                emu.load_state(st); pl.__dict__ = copy.deepcopy(saved)
                print(t, "caught", name, "halfwidth", P.paddle_half(g), flush=True)
    last_caps = caps
