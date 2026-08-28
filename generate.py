"""
CLI untuk Sprint 0 — generate dokumentasi dari folder foto.

Usage:
    python generate.py --folder ./foto --title "Monev Keuangan"
    python generate.py --folder ./foto --title "Posyandu Sukajaya" --date 2026-08-10
    python generate.py --folder ./foto --title "Rapat UKM" --out ./output/hasil.jpg
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.renderer import load_photos, render_doc


def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Format tanggal tidak valid: '{s}'. Gunakan YYYY-MM-DD.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SMARTREPORT AUTO — Sprint 0")
    parser.add_argument("--folder", required=True, help="Folder berisi foto")
    parser.add_argument("--title", required=True, help="Judul kegiatan")
    parser.add_argument("--date", dest="event_date", type=parse_date, default=None,
                        help="Tanggal kegiatan (YYYY-MM-DD). Default: hari ini.")
    parser.add_argument("--location", default=None, help="Nama tempat kegiatan (opsional)")
    parser.add_argument("--out", default=None, help="Path output JPG. Default: output/DOC-<timestamp>.jpg")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"[ERROR] Folder tidak ditemukan: {folder}")
        sys.exit(1)

    photos = load_photos(folder)
    if not photos:
        print(f"[ERROR] Tidak ada foto di folder: {folder}")
        sys.exit(1)

    print(f"  Judul   : {args.title}")
    print(f"  Tanggal : {args.event_date or date.today()}")
    print(f"  Foto    : {len(photos)} foto")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = args.out or output_dir / f"DOC-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"

    render_doc(
        title=args.title,
        photos=photos,
        event_date=args.event_date,
        location=args.location,
        output_path=output_path,
    )

    print(f"\n✅ Selesai → {output_path}")


if __name__ == "__main__":
    main()
