"""Раунд 25: сохранить момент, когда остался последний разбиваемый кирпич, и замерить, сколько кадров на его
добивание тратят разные версии игрока при разных малых сдвигах старта (k кадров без ввода).
uv run python experiments/last_brick.py make | test player.py k1,k2,..."""
import sys, importlib.util
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Mouse
def load(pf):
    s = importlib.util.spec_from_file_location("player", pf); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
emu = power_on(); emu.step(frames=30)
if sys.argv[1] == "make":
    P = load("runs/player_boss3.py")
    emu.load_state(open("runs/j46/r25.state", "rb").read())
    pl = P.Player(); pl.phase = "game"; f = emu.frame(); hist = []
    for t in range(40000):
        k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
        if t % 10 == 0 and P.in_game(f):
            g = P.read_bricks(f); hist = (hist + [int(((g == 1) | (g == 2)).sum())])[-30:]
            if len(hist) == 30 and max(hist) == 1:
                open("runs/last25.state", "wb").write(emu.save_state()); print("saved at", t); break
else:
    P = load(sys.argv[2]); st = open("runs/last25.state", "rb").read()
    for k in [int(x) for x in sys.argv[3].split(",")]:
        emu.load_state(st)
        for _ in range(k): emu.step()
        pl = P.Player(); pl.phase = "game"; f = emu.frame(); key0 = None; res = "not cleared"
        for t in range(30000):
            a, m = pl.act(f); emu.step(a, 1, m); f = emu.frame()
            if P.in_game(f):
                key = (f[124:134, 250:290] == 255).all(2).tobytes()
                key0 = key0 or key
                if key != key0: res = f"cleared in {t}"; break
        print(sys.argv[2], "k", k, res, flush=True)
