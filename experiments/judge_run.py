"""Партия по протоколу судьи: power_on(), step(frames=W) без ввода, затем Player на каждом кадре.
Сохраняет состояние в начале каждого раунда (runs/jW/rNN.state) и кадры раз в 500 кадров после раунда R.
Останавливается через 3000 кадров после конца игры (после раунда 33) или через N кадров.
uv run python experiments/judge_run.py W N [R]   (PLAYER=файл — другая версия игрока)"""
import os, sys, importlib.util
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
_s = importlib.util.spec_from_file_location("player", os.environ.get("PLAYER", "player.py"))
P = importlib.util.module_from_spec(_s); _s.loader.exec_module(P)

W, N = int(sys.argv[1]), int(sys.argv[2]); R = int(sys.argv[3]) if len(sys.argv) > 3 else 99
out = Path(f"runs/j{W}"); out.mkdir(parents=True, exist_ok=True)
emu = power_on(); emu.step(frames=W); f = emu.frame(); pl = P.Player()
cur, cand, cn, rnd, last_game, lives = None, None, 0, 0, 0, None
for t in range(N):
    if rnd >= 33 and t - last_game > 3000:
        break
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f):
        continue
    last_game = t
    lv = P.count_lives(f)
    if lives is not None and lv < lives:
        print(f"life lost at {t} (round {rnd})", flush=True)
    lives = lv
    if rnd >= R and t % 500 == 0:
        Image.fromarray(f).save(out / f"f{t:06d}.png")
    key = (f[124:134, 250:290] == 255).all(2).tobytes()
    if key == cur:
        cn = 0
        continue
    if key == cand:
        cn += 1
    else:
        cand, cn = key, 1
    if cn >= 60:
        cur = cand; rnd += 1
        open(out / f"r{rnd:02d}.state", "wb").write(emu.save_state())
        print(f"round {rnd} at {t} score {P.read_score(f)} lives {lv}", flush=True)
print("end", t, "last game frame", last_game, "score", P.read_score(f), "round", rnd, "lives", lives)
