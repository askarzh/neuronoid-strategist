"""Играть игроком с сохранения N кадров; печатать раунды/счёт. uv run python experiments/from_state.py state N [player.py]"""
import sys, importlib.util
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
spec = importlib.util.spec_from_file_location("player", sys.argv[3] if len(sys.argv) > 3 else "player.py"); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
emu = power_on(); emu.step(frames=30); emu.load_state(open(sys.argv[1], "rb").read())
pl = P.Player(); pl.phase = "game"; f = emu.frame()
key0 = None
for t in range(int(sys.argv[2])):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if P.in_game(f):
        key = (f[124:134, 250:290] == 255).all(2).tobytes()
        if key0 is None: key0 = key
        if key != key0: print("next round at", t, "score", P.read_score(f)); break
    if t % 5000 == 0: print(t, P.read_score(f) if P.in_game(f) else None, flush=True)
