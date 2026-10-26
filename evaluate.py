"""Оценка игрока по нескольким «сидам» (задержка первого действия), по 2 эмулятора параллельно.
uv run python evaluate.py player.py метка [сиды...]"""
import os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

pf, tag = sys.argv[1], sys.argv[2]
seeds = [int(s) for s in sys.argv[3:]] or [0, 57, 113, 200]

def run(seed):
    env = dict(os.environ, PLAYER=pf)
    out = subprocess.run([sys.executable, "bench.py", "20", f"runs/eval_{tag}_{seed}", str(seed)],
                         capture_output=True, text=True, env=env).stdout
    m = re.search(r"FINAL score (\d+) lives (\d+); events (.*); ", out)
    r = re.search(r"rounds \(start frame, score\): (.*)", out)
    nr = len(eval(r.group(1))) if r else 0
    return seed, int(m.group(1)), m.group(3).count("life lost"), nr

with ThreadPoolExecutor(2) as ex:
    res = list(ex.map(run, seeds))
for s, sc, lost, nr in res:
    print(f"{tag} seed {s:4d}: score {sc:7d}  lost {lost}  round-changes {nr}")
print(f"{tag} MEAN {sum(r[1] for r in res)/len(res):.0f}  lost total {sum(r[2] for r in res)}")
