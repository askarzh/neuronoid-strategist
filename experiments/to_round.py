"""Играть игроком с включения до раунда N; в начале каждого раунда сохранять состояние в runs/states/rNN.state.
Номер раунда — по счёту смен надписи под ROUND (картинка должна держаться 60 кадров)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P
N = int(sys.argv[1]); delay = int(sys.argv[2]) if len(sys.argv) > 2 else 0
out = Path("runs/states"); out.mkdir(parents=True, exist_ok=True)
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
cur, cand, cand_n, rnd = None, None, 0, 0
t = 0
while True:
    k, m = pl.act(f) if t >= delay else ([], P.Mouse())
    emu.step(k, 1, m); f = emu.frame(); t += 1
    if not P.in_game(f): continue
    key = (f[124:134, 250:290] == 255).all(2).tobytes()
    if key == cur: cand_n = 0; continue
    if key == cand: cand_n += 1
    else: cand, cand_n = key, 1
    if cand_n >= 60:
        cur = cand; rnd += 1
        open(out / f"r{rnd:02d}.state", "wb").write(emu.save_state())
        Image.fromarray(f).save(out / f"r{rnd:02d}.png")
        print(f"round {rnd} at frame {t} score {P.read_score(f)} lives {P.count_lives(f)}", flush=True)
        if rnd >= N:
            for i in range(3000):
                k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame(); t += 1
                if i % 100 == 0: Image.fromarray(f).save(out / f"r{rnd:02d}_play_{i:04d}.png")
            break
