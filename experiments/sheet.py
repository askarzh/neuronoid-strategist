"""Собрать PNG из папки в одну сетку (контактный лист) для быстрого просмотра."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
d = Path(sys.argv[1]); files = sorted(d.glob(sys.argv[2] if len(sys.argv) > 2 else "f*.png"))
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 5
w, h = 320, 200
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + 12)), "white")
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).resize((w, h))
    x, y = (i % cols) * w, (i // cols) * (h + 12)
    sheet.paste(im, (x, y + 12)); dr.text((x + 2, y), f.stem, fill="black")
sheet.save(d / "sheet.png")
