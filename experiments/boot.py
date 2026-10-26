"""Включить игру и сохранять кадры каждые N кадров, чтобы посмотреть, что происходит после старта."""
import sys, time
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on

out = Path("runs/boot"); out.mkdir(parents=True, exist_ok=True)
emu = power_on()
print("fps", emu.fps)
t = time.time()
for i in range(0, 60):
    emu.step(frames=30)
    f = emu.frame()
    if i % 2 == 0:
        Image.fromarray(f).save(out / f"f{(i+1)*30:05d}.png")
print("shape", f.shape, "time", time.time() - t)
open("runs/boot/state.bin", "wb").write(emu.save_state())
