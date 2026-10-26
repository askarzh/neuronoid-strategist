"""Стенд: включить игру, отдать управление Player на N кадров (как судья), сохранять кадры и сводку.

uv run python bench.py [минут игрового времени] [папка]"""
import sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from body import power_on
import player as P

def main(minutes=20.0, outdir="runs/bench", every=700):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"): p.unlink()
    emu = power_on()
    pl = P.Player()
    n = int(minutes * 60 * emu.fps)
    t0 = time.time()
    emu.step()  # до первого кадра экрана нет
    f = emu.frame()
    for t in range(n):
        keys, mouse = pl.act(f)
        emu.step(keys, frames=1, mouse=mouse)
        f = emu.frame()
        if t % every == 0:
            Image.fromarray(f).save(out / f"f{t:06d}.png")
    Image.fromarray(f).save(out / f"final.png")
    print(f"done {n} frames in {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 20.0, sys.argv[2] if len(sys.argv) > 2 else "runs/bench")
