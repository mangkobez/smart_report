"""
Setup template background.

Cukup copy file template PNG (yang sudah berisi header + footer + dekorasi)
ke folder template. Tidak perlu build apapun.

Usage:
    python build_background.py                    # default template
    python build_background.py posyandu           # template lain

File sumber: assets/logo/<nama>.png
File tujuan: assets/templates/<nama>/background.png
"""
import sys
import shutil
from pathlib import Path

ASSETS_DIR    = Path(__file__).parent / "assets"
LOGO_DIR      = ASSETS_DIR / "logo"
TEMPLATES_DIR = ASSETS_DIR / "templates"

# Mapping nama template → file sumber
SOURCES = {
    "default":    "template_1.png",
    # tambah template lain di sini:
    # "posyandu": "template_posyandu.png",
    # "rapat":    "template_rapat.png",
}

name = sys.argv[1] if len(sys.argv) > 1 else "default"

if name not in SOURCES:
    print(f"[ERROR] Template '{name}' tidak ada di SOURCES.")
    sys.exit(1)

src  = LOGO_DIR / SOURCES[name]
dst  = TEMPLATES_DIR / name / "background.png"
dst.parent.mkdir(parents=True, exist_ok=True)

if not src.exists():
    print(f"[ERROR] File tidak ditemukan: {src}")
    sys.exit(1)

shutil.copy(src, dst)
print(f"✅ {src.name} → {dst}")
