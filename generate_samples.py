"""Generate sample outputs untuk semua varian jumlah foto."""
import sys
from datetime import date
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from src.renderer.canvas import render_doc

COLORS = [
    (180, 60, 60), (60, 140, 190), (60, 180, 100),
    (190, 140, 60), (140, 60, 190), (190, 190, 60),
]

SAMPLES = [
    (1, "Apel Pagi"),
    (2, "Rapat UKM"),
    (3, "Penyuluhan Hipertensi"),
    (4, "Monev Keuangan"),
    (5, "Monitoring dan Evaluasi Keuangan|Dinas Kesehatan"),
    (6, "Posyandu Balita Sukajaya"),
]

def make_photos(n):
    return [Image.new("RGB", (800, 600), color=COLORS[i % len(COLORS)]) for i in range(n)]

Path("output").mkdir(exist_ok=True)

for n, title in SAMPLES:
    out = f"output/sample_{n}foto.jpg"
    render_doc(
        title=title,
        photos=make_photos(n),
        event_date=date(2026, 8, 11),
        location="Aula UPTD Puskesmas Cipatujah",
        output_path=out,
    )
    print(f"  {out}")

print("\nDone.")
