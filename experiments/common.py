"""Общее для экспериментов: дойти до начала партии в одном процессе."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on, Key, Mouse

def to_game(emu):
    """С включения: EGA, мышь, клик на заставке, ждать до экрана раунда 1. Возвращает число кадров."""
    script = [([], 300), ([Key.E], 3), ([], 200), ([Key.M], 3), ([], 1100), ("click", 3), ([], 1300)]
    n = 0
    for k, fr in script:
        for _ in range(fr):
            if k == "click": emu.step(mouse=Mouse(left=True))
            else: emu.step(k)
            n += 1
    return n
