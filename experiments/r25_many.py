"""Раунд 25: из сохранения начала раунда много продолжений (k кадров без ввода), замер времени прохождения.
Непрошедшие сохраняют кадры и состояние для разбора. uv run python experiments/r25_many.py state ks limit [player]"""
import sys, importlib.util
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
st_path, ks, limit = sys.argv[1], [int(x) for x in sys.argv[2].split(",")], int(sys.argv[3])
pf = sys.argv[4] if len(sys.argv) > 4 else "player.py"
s = importlib.util.spec_from_file_location("player", pf); P = importlib.util.module_from_spec(s); s.loader.exec_module(P)
emu = power_on(); emu.step(frames=30); st = open(st_path, "rb").read()
tag = Path(st_path).parent.name
for k in ks:
    emu.load_state(st)
    for _ in range(k): emu.step()
    pl = P.Player(); pl.phase = "game"; f = emu.frame(); key0 = None; res = None
    for t in range(limit):
        a, m = pl.act(f); emu.step(a, 1, m); f = emu.frame()
        if P.in_game(f):
            key = (f[124:134, 250:290] == 255).all(2).tobytes()
            key0 = key0 or key
            if key != key0: res = t; break
    if res is None:
        out = Path(f"runs/stuck_{tag}_{k}"); out.mkdir(parents=True, exist_ok=True)
        open(out / "end.state", "wb").write(emu.save_state())
        for i in range(0, 3000, 100):
            a, m = pl.act(f); emu.step(a, 1, m); f = emu.frame()
            Image.fromarray(f).save(out / f"t{i:04d}.png")
            for _ in range(99):
                a, m = pl.act(f); emu.step(a, 1, m); f = emu.frame()
    print(tag, "k", k, "cleared in", res, "score", P.read_score(f), flush=True)
