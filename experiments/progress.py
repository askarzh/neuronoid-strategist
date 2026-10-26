"""Сколько кирпичей осталось по ходу игры (каждые K кадров): где игрок тратит время."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P
N, K = int(sys.argv[1]), int(sys.argv[2])
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if t % K == 0 and P.in_game(f):
        g = P.read_bricks(f)
        print(t, "normal", int((g == 1).sum()), "silver", int((g == 2).sum()), "gold", int((g == 3).sum()), "score", P.read_score(f), "balls", len(P.find_balls(f)))
