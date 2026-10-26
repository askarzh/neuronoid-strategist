"""Проверка: работает ли загрузка сохранения из другого процесса, если сначала прогнать эмулятор до игры."""
import sys, pickle
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P
mode = sys.argv[1]
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
if mode == "save":
    for t in range(5000):
        k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    open("runs/x.state", "wb").write(emu.save_state())
    for t in range(300):
        k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    Image.fromarray(f).save("runs/x_ref.png")
else:
    pre = int(sys.argv[2])
    for t in range(pre):
        k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    emu.load_state(open("runs/x.state", "rb").read())
    for t in range(300):
        emu.step(); 
    Image.fromarray(emu.frame()).save(f"runs/x_load{pre}.png")
    print(emu.frame().shape)
