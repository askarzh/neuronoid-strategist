"""Загрузить сохранение начала раунда 33 и играть игроком, сохраняя кадры. uv run python experiments/r33.py N every [player.py]"""
import sys, os, importlib.util
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
pf = sys.argv[3] if len(sys.argv) > 3 else "player.py"
spec = importlib.util.spec_from_file_location("player", pf); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
N, every = int(sys.argv[1]), int(sys.argv[2])
out = Path("runs/r33"); out.mkdir(parents=True, exist_ok=True)
for p in out.glob("*.png"): p.unlink()
emu = power_on(); emu.step(frames=30)
emu.load_state(open("runs/states/r33.state", "rb").read())
pl = P.Player(); pl.phase = "game"
f = emu.frame(); frames = []
lives = P.count_lives(f)
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    frames.append(f)
    if every and t % every == 0: Image.fromarray(f).save(out / f"t{t:05d}.png")
    if P.in_game(f):
        lv = P.count_lives(f)
        if lv < lives: print("life lost at", t, flush=True)
        lives = lv
np.save("runs/r33/frames.npy", np.array(frames[:1500]))
print("score", P.read_score(f), "lives", lives, "in_game", P.in_game(f))
