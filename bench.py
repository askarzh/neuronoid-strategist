"""Стенд: включить игру, отдать управление Player на N минут игрового времени (как судья), записать ход партии.

uv run python bench.py [минут] [папка]   — кадры раз в `every` кадров, сводка по минутам, лог событий."""
import sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from body import power_on
import player as P


def main(minutes=20.0, outdir="runs/bench", every=2000):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"): p.unlink()
    emu = power_on()
    pl = P.Player()
    n = int(minutes * 60 * emu.fps)
    t0 = time.time()
    emu.step()  # до первого кадра экрана нет
    f = emu.frame()
    score, lives, last_lives = 0, None, None
    events = []
    ring = []  # последние кадры с состоянием игрока — для разбора потерь
    for t in range(n):
        keys, mouse = pl.act(f)
        ring.append((t, f, f"ball {pl.track[-1] if pl.track else None} n={len(pl.track)} aim {pl.aim} est {pl.est:.1f} pad {P.find_paddle(f) if f.shape[0]==200 else None} dx {mouse.dx}"))
        ring = ring[-150:]
        emu.step(keys, frames=1, mouse=mouse)
        f = emu.frame()
        if P.in_game(f):
            s = P.read_score(f)
            if s is not None: score = s
            lv = P.count_lives(f)
            if last_lives is not None and lv < last_lives:
                events.append((t, "life lost", score)); Image.fromarray(f).save(out / f"lost_{t:06d}.png")
                d = out / f"lost_{t:06d}"; d.mkdir(exist_ok=True)
                with open(d / "trace.txt", "w") as fh:
                    for tt, ff, s in ring:
                        fh.write(f"{tt} {s}\n"); Image.fromarray(ff).save(d / f"{tt:06d}.png")
            last_lives = lv
        if t % every == 0:
            Image.fromarray(f).save(out / f"f{t:06d}.png")
        if t % int(60 * emu.fps) == 0:
            print(f"min {t/emu.fps/60:5.1f} score {score} lives {last_lives}", flush=True)
    Image.fromarray(f).save(out / "final.png")
    print(f"FINAL score {score} lives {last_lives}; events {events}; {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 20.0, sys.argv[2] if len(sys.argv) > 2 else "runs/bench")
