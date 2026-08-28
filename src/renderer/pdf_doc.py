"""
PDF renderer untuk Dokumentasi Perjalanan Dinas (SPPD).
Menggunakan Pillow — generate A4 sebagai image lalu simpan sebagai PDF.
"""
import io
from datetime import date
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .photo import smart_crop

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
FONTS_DIR  = ASSETS_DIR / "fonts"

PAGE_W, PAGE_H = 1654, 2339   # A4 @ 200 DPI
MARGIN         = 100


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
    try:
        return ImageFont.truetype(str(FONTS_DIR / name), size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _tw(text: str, font) -> int:
    bb = font.getbbox(text)
    return bb[2] - bb[0]


def _th(text: str, font) -> int:
    bb = font.getbbox(text)
    return bb[3] - bb[1]


def _text_center(draw: ImageDraw.ImageDraw, cx: int, y: int,
                 text: str, font, color=(0, 0, 0)) -> int:
    draw.text((cx - _tw(text, font) // 2, y), text, font=font, fill=color)
    return y + _th(text, font)


def _hline(draw: ImageDraw.ImageDraw, y: int, thick: int = 2,
           x0: int = MARGIN, x1: int = None) -> None:
    if x1 is None:
        x1 = PAGE_W - MARGIN
    draw.rectangle([(x0, y), (x1, y + thick - 1)], fill=(0, 0, 0))


# ---------------------------------------------------------------------------
# Header (kop surat)
# Prioritas: kop.png/kop.jpg di template_dir → generate dari teks (fallback)
# ---------------------------------------------------------------------------

A4_RATIO_MIN, A4_RATIO_MAX = 1.35, 1.50  # A4 = 1.414


def _draw_kop(canvas: Image.Image, draw: ImageDraw.ImageDraw,
              cfg: dict, template_dir: Path | None = None) -> int:
    """
    Jika kop adalah halaman A4 penuh → paste sebagai background full-page,
    kembalikan info_y dari config.
    Jika kop adalah strip header → paste sebagai header, kembalikan y berikutnya.
    Fallback: gambar teks kop.
    """
    for name in ("kop.png", "kop.jpg", "kop.jpeg"):
        kop_path = template_dir / name if template_dir else None
        if kop_path and kop_path.exists():
            try:
                kop_img = Image.open(kop_path).convert("RGB")
                ratio   = kop_img.height / kop_img.width
                if A4_RATIO_MIN <= ratio <= A4_RATIO_MAX:
                    # Full-page template — paste sebagai background
                    kop_img = kop_img.resize((PAGE_W, PAGE_H), Image.LANCZOS)
                    canvas.paste(kop_img, (0, 0))
                    return cfg.get("info_y", 720)
                else:
                    # Header strip biasa
                    kop_w = PAGE_W - MARGIN * 2
                    kop_h = int(kop_w * ratio)
                    kop_img = kop_img.resize((kop_w, kop_h), Image.LANCZOS)
                    canvas.paste(kop_img, (MARGIN, MARGIN))
                    return MARGIN + kop_h + 20
            except Exception:
                break

    # Fallback: gambar teks kop
    y  = MARGIN
    cx = PAGE_W // 2
    kop_lines = cfg.get("kop_lines", [
        ("PEMERINTAH KABUPATEN TASIKMALAYA", 28, True),
        ("DINAS KESEHATAN", 26, True),
        ("UPTD PUSKESMAS CIPATUJAH", 32, True),
        ("Jl. Raya Cipatujah Kec. Cipatujah Kab. Tasikmalaya 46188", 20, False),
        ("Telp. (0265) 581XXX  Email: pkmcipatujah@gmail.com", 18, False),
    ])
    for text, size, bold in kop_lines:
        f = _font(size, bold)
        y = _text_center(draw, cx, y, text, f) + 4
    y += 8
    _hline(draw, y, thick=4)
    _hline(draw, y + 7, thick=1)
    return y + 22


# ---------------------------------------------------------------------------
# Judul dokumen
# ---------------------------------------------------------------------------

def _draw_title(draw: ImageDraw.ImageDraw, y: int, title: str) -> int:
    cx = PAGE_W // 2
    f  = _font(36, bold=True)
    y  = _text_center(draw, cx, y, title, f)
    return y + 20


# ---------------------------------------------------------------------------
# Info fields (Nama / Tujuan / Lokasi / Tanggal)
# ---------------------------------------------------------------------------

def _draw_info(draw: ImageDraw.ImageDraw, y: int,
               nama: str, tujuan: str, lokasi: str, tanggal: str,
               jabatan: str = "",
               left_x: int = MARGIN, right_x: int = None) -> int:
    if right_x is None:
        right_x = PAGE_W - MARGIN
    col1  = 360
    col2  = 28
    f_l   = _font(26, bold=True)
    f_v   = _font(26)
    lh    = 44
    max_w = right_x - left_x - col1 - col2 - 10

    rows = [("Nama Pelaksana", nama)]
    if jabatan:
        rows.append(("NIP / Jabatan", jabatan))
    rows += [
        ("Tujuan / Keperluan", tujuan),
        ("Lokasi Kegiatan", lokasi),
        ("Tanggal", tanggal),
    ]

    def _write_value(value: str, vy: int) -> int:
        f_tw = _tw(value, f_v)
        if f_tw > max_w:
            words = value.split()
            line, lines = "", []
            for w in words:
                test = (line + " " + w).strip()
                if _tw(test, f_v) <= max_w:
                    line = test
                else:
                    lines.append(line)
                    line = w
            if line:
                lines.append(line)
            vx = MARGIN + col1 + col2
            for ln in lines:
                draw.text((vx, vy), ln, font=f_v, fill=(0, 0, 0))
                vy += lh
            return vy
        else:
            draw.text((MARGIN + col1 + col2, vy), value, font=f_v, fill=(0, 0, 0))
            return vy + lh

    for label, value in rows:
        draw.text((left_x, y), label, font=f_l, fill=(0, 0, 0))
        draw.text((left_x + col1, y), ":", font=f_l, fill=(0, 0, 0))
        y = _write_value(value, y)

    y += 12
    _hline(draw, y, x0=left_x, x1=right_x)
    return y + 24


# ---------------------------------------------------------------------------
# Foto grid (formal — rectangular)
# ---------------------------------------------------------------------------

def _draw_photos(canvas: Image.Image, photos: list[Image.Image],
                 y_start: int, cfg: dict,
                 left_x: int = MARGIN, right_x: int = None) -> int:
    if right_x is None:
        right_x = PAGE_W - MARGIN
    cols    = cfg.get("cols", 2)
    gap     = cfg.get("gap", 24)
    ratio   = cfg.get("ratio", 0.75)   # height/width of each photo (4:3 default)
    avail_w = right_x - left_x
    ph_w    = (avail_w - gap * (cols - 1)) // cols
    ph_h    = int(ph_w * ratio)
    draw    = ImageDraw.Draw(canvas)
    y       = y_start

    for i, photo in enumerate(photos):
        col = i % cols
        row = i // cols
        px  = left_x + col * (ph_w + gap)
        py  = y + row * (ph_h + gap)

        if py + ph_h > PAGE_H - MARGIN:
            break

        cropped = smart_crop(photo, ph_w, ph_h).convert("RGB")
        canvas.paste(cropped, (px, py))
        draw.rectangle([(px, py), (px + ph_w - 1, py + ph_h - 1)],
                       outline=(160, 160, 160), width=2)

    rows = max(1, (len(photos) + cols - 1) // cols)
    return y + rows * (ph_h + gap) - gap


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def render_sppd_pdf(
    nama: str,
    tujuan: str,
    lokasi: str,
    event_date: date,
    photos: list[Image.Image],
    cfg: dict | None = None,
    jabatan: str = "",
    template_dir: Path | None = None,
) -> io.BytesIO:
    """Generate A4 PDF dokumentasi SPPD. Kembalikan BytesIO (PDF)."""
    if cfg is None:
        cfg = {}

    from src.bot.parser import fmt_date
    from datetime import date as _date
    tanggal_str = fmt_date(event_date) if event_date else fmt_date(_date.today())

    canvas = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    draw   = ImageDraw.Draw(canvas)

    left_x  = cfg.get("left_x",  MARGIN)
    right_x = cfg.get("right_x", PAGE_W - MARGIN)

    y = _draw_kop(canvas, draw, cfg, template_dir)
    # Judul sudah ada di template kop (full-page) — hanya gambar jika teks kop
    if not any((template_dir / n).exists()
               for n in ("kop.png", "kop.jpg", "kop.jpeg")
               if template_dir):
        y = _draw_title(draw, y, cfg.get("doc_title", "DOKUMENTASI PERJALANAN DINAS"))
    y = _draw_info(draw, y, nama, tujuan, lokasi, tanggal_str, jabatan,
                   left_x=left_x, right_x=right_x)
    photos_y = cfg.get("photos_y", y)
    y = _draw_photos(canvas, photos, photos_y, cfg.get("photo_grid", {}),
                     left_x=left_x, right_x=right_x)

    buf = io.BytesIO()
    canvas.save(buf, "PDF", resolution=200)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Scan helpers
# ---------------------------------------------------------------------------

def photo_to_pdf_bytes(photo: Image.Image) -> bytes:
    """Konversi satu foto menjadi satu halaman PDF A4 (full-fit, bg putih)."""
    PAD  = 20   # margin minimal agar tidak terpotong
    page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    img  = photo.convert("RGB")
    aw, ah = PAGE_W - PAD * 2, PAGE_H - PAD * 2
    # Scale proporsional agar mengisi penuh salah satu sisi
    scale = min(aw / img.width, ah / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    ox  = PAD + (aw - nw) // 2
    oy  = PAD + (ah - nh) // 2
    page.paste(img, (ox, oy))
    buf = io.BytesIO()
    page.save(buf, "PDF", resolution=200)
    return buf.getvalue()


def merge_pdfs(scans: list[bytes], doc_pdf: io.BytesIO) -> io.BytesIO:
    """Gabungkan scan surat (halaman pertama) + dokumentasi foto (halaman terakhir)."""
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    for scan_bytes in scans:
        reader = PdfReader(io.BytesIO(scan_bytes))
        for page in reader.pages:
            writer.add_page(page)
    doc_pdf.seek(0)
    for page in PdfReader(doc_pdf).pages:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out
