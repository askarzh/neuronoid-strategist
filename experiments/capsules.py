"""Найти падающие объекты (капсулы): компоненты в поле вне кирпичей, которые движутся строго вниз.
Сохраняет крупные кадры уникальных спрайтов и печатает, когда они появлялись."""
import sys
from pathlib import Path
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from body import power_on
import player as P

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
out = Path("runs/caps"); out.mkdir(parents=True, exist_ok=True)
emu = power_on(); pl = P.Player(); emu.step(); f = emu.frame()
prev = []; seen = {}
for t in range(N):
    k, m = pl.act(f); emu.step(k, 1, m); f = emu.frame()
    if t % 2 or not P.in_game(f): continue
    mask = (f[8:176, 40:217].sum(2) > 0).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask)
    cur = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 13 <= w <= 17 and 6 <= h <= 9 and a > 40:
            cur.append((x + 40, y + 8, w, h))
    for (x, y, w, h) in cur:
        # был ли такой же объект на том же x чуть выше 2 кадра назад
        if any(px == x and 0 < y - py <= 4 for (px, py, _, _) in prev):
            crop = f[y:y + h, x:x + w]
            key = crop.tobytes()
            cols = tuple(sorted({tuple(c) for c in crop.reshape(-1, 3)}))
            if cols not in seen:
                seen[cols] = (t, x, y)
                Image.fromarray(crop).resize((w * 10, h * 10), Image.NEAREST).save(out / f"cap_{t:06d}.png")
                print("new capsule", t, x, y, w, h, cols, flush=True)
    prev = cur
