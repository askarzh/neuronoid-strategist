"""Сколько капсул появилось и сколько поймано (по скачкам счёта на 1000+ при исчезновении капсулы у ракетки)."""
import sys, os, importlib.util
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
pf = os.environ.get("PLAYER", "player.py")
spec = importlib.util.spec_from_file_location("player", pf); P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
N = int(sys.argv[1])
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
seen, caught, missed = Counter(), Counter(), Counter()
active = {}   # (name, x) -> last y
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if not P.in_game(f): continue
    cur = {(n, x): y for n, x, y in pl.caps_prev}
    for key, y in cur.items():
        if key not in active: seen[key[0]] += 1
    for key, y in active.items():
        if key not in cur:
            if y >= 168:
                pad = P.find_paddle(f)
                if pad is not None and abs(pad - key[1]) <= pl.pad_half + 3: caught[key[0]] += 1
                else: missed[key[0]] += 1
            # исчезла высоко — ложная/перекрыта
    active = cur
print("seen", dict(seen)); print("caught", dict(caught)); print("missed", dict(missed))
