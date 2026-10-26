"""Включить игру, выполнить сценарий действий, сохранить кадры. Сценарий: список (keys, frames, every[, mouse]).
Сохранения между процессами не работают (игра выпадает в DOS), поэтому каждый эксперимент воспроизводит ввод с включения."""
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Key, Mouse

BOOT = [([], 300, 0), ([Key.E], 3, 0), ([], 200, 0), ([Key.M], 3, 0)]

def play(emu, script, out=None, t=0):
    for keys, frames, every, *m in script:
        mouse = m[0] if m else None
        for i in range(frames):
            emu.step(keys, frames=1, mouse=mouse); t += 1
            if out and every and (i + 1) % every == 0:
                Image.fromarray(emu.frame()).save(out / f"f{t:05d}.png")
    return t

def run(script, outdir, emu=None):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"): p.unlink()
    emu = emu or power_on()
    play(emu, script, out)
    return emu
