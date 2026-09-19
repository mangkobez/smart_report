"""
Template-based renderer.

Setiap template = satu folder berisi:
  background.png  — desain lengkap (header + footer + dekorasi)
  config.json     — koordinat zona foto dan posisi teks

Sistem hanya mengurusi: paste foto + tulis teks.
"""
import json
from datetime import date
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .photo import smart_crop


ASSETS_DIR    = Path(__file__).parent.parent.parent / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
DEFAULT_TPL   = "default"

COLOR_MAP = {
    "gold":   (255, 210, 0),
    "white":  (255, 255, 255),
    "teal":   (0, 171, 169),
    "black":  (0, 0, 0),
    "red":    (220, 38, 38),
    "maroon": (128, 0, 0),
    "navy":   (15, 23, 42),
    "silver": (192, 192, 192),
    "yellow": (255, 235, 59),
    "orange": (255, 120, 20),
}


def _resolve_color(val) -> tuple:
    """Terima nama warna, hex string (#rrggbb), atau tuple RGB."""
    if isinstance(val, (list, tuple)):
        return tuple(val[:3])
    if isinstance(val, str) and val.startswith("#"):
        h = val.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return COLOR_MAP.get(val, (255, 255, 255))

BULAN  = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
          "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config(template: str = DEFAULT_TPL) -> dict:
    path = TEMPLATES_DIR / template / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            str(ASSETS_DIR / "fonts" / "NotoSans-Regular.ttf"), size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _bold(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            str(ASSETS_DIR / "fonts" / "NotoSans-Bold.ttf"), size)
    except (IOError, OSError):
        return _font(size)


def _italic_bold(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            str(ASSETS_DIR / "fonts" / "NotoSans-BoldItalic.ttf"), size)
    except (IOError, OSError):
        return _bold(size)


def _montserrat_black(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            str(ASSETS_DIR / "fonts" / "Montserrat-Black.ttf"), size)
    except (IOError, OSError):
        return _bold(size)


def _lora_italic(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            str(ASSETS_DIR / "fonts" / "Lora-Italic.ttf"), size)
    except (IOError, OSError):
        return _italic_bold(size)


def _remove_white_bg(img: Image.Image, thresh: int = 240) -> Image.Image:
    """Ubah piksel putih/near-white jadi transparan."""
    img = img.convert("RGBA")
    data = list(img.getdata())
    new = [
        (r, g, b, 0) if r >= thresh and g >= thresh and b >= thresh else (r, g, b, a)
        for r, g, b, a in data
    ]
    img.putdata(new)
    return img


def _tw(text: str, font) -> int:
    bb = font.getbbox(text)
    return bb[2] - bb[0]


def _wrap(text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if _tw(test, font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def _draw_text_centered(draw: ImageDraw.ImageDraw,
                        cx: int, y: int,
                        text: str, font, color: tuple) -> None:
    draw.text((cx - _tw(text, font) // 2, y), text, font=font, fill=color)


# ---------------------------------------------------------------------------
# Photo placement
# ---------------------------------------------------------------------------

def _rounded_photo(img: Image.Image, w: int, h: int,
                   corner_r: int, border_w: int) -> Image.Image:
    iw = max(w - 2 * border_w, 1)
    ih = max(h - 2 * border_w, 1)
    cropped = smart_crop(img, iw, ih)

    photo_mask = Image.new("L", (iw, ih), 0)
    ImageDraw.Draw(photo_mask).rounded_rectangle(
        [(0, 0), (iw - 1, ih - 1)],
        radius=max(corner_r - border_w, 2), fill=255)

    frame = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    fm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(fm).rounded_rectangle(
        [(0, 0), (w - 1, h - 1)], radius=corner_r, fill=255)
    frame.putalpha(fm)

    p = cropped.convert("RGBA")
    p.putalpha(photo_mask)
    frame.paste(p, (border_w, border_w), p)
    return frame


def _put(canvas: Image.Image, photo: Image.Image,
         x: int, y: int, w: int, h: int,
         corner_r: int, border_w: int) -> None:
    f = _rounded_photo(photo, w, h, corner_r, border_w)
    canvas.paste(f, (x, y), f.split()[3])


def _put_custom_rows(canvas: Image.Image, photos: list[Image.Image],
                     ax: int, ay: int, aw: int, ah: int,
                     rows_cfg: list[dict], gap: int, kw: dict) -> None:
    """Tempatkan foto sesuai konfigurasi rows kustom dari config.json."""
    n_rows      = len(rows_cfg)
    total_ratio = sum(r.get("h_ratio", 1.0) for r in rows_cfg)
    usable_h    = ah - gap * (n_rows - 1)
    photo_idx   = 0
    y           = ay

    for i, row in enumerate(rows_cfg):
        if photo_idx >= len(photos):
            break
        count      = row.get("count", 1)
        row_h      = int(usable_h * row.get("h_ratio", 1.0 / n_rows) / total_ratio)
        align      = row.get("align", "left")
        grid_cols  = row.get("cols", count)
        row_photos = photos[photo_idx:photo_idx + count]
        photo_idx += count
        n = len(row_photos)
        if n == 0:
            break

        col_w = (aw - gap * (grid_cols - 1)) // grid_cols

        if align == "center":
            total_w = n * col_w + (n - 1) * gap
            start_x = ax + (aw - total_w) // 2
            for j, p in enumerate(row_photos):
                _put(canvas, p, start_x + j * (col_w + gap), y, col_w, row_h, **kw)
        elif n == 1:
            _put(canvas, row_photos[0], ax, y, aw, row_h, **kw)
        else:
            pw = (aw - gap * (n - 1)) // n
            for j, p in enumerate(row_photos):
                _put(canvas, p, ax + j * (pw + gap), y, pw, row_h, **kw)

        y += row_h + gap


def _place_photos(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                  photos: list[Image.Image], cfg: dict) -> None:
    pz       = cfg["photo_zone"]
    gap      = cfg.get("photo_gap", 8)
    corner_r = cfg.get("corner_r", 8)
    border_w = cfg.get("border_w", 2)
    fi       = cfg.get("frame_inner", 10)
    fc       = cfg.get("frame_corner", 14)

    fx, fy   = pz["x"], pz["y"]
    fw, fh   = pz["w"], pz["h"]

    # Outer frame — skip jika frame_color "none"/"transparent"
    raw_fc = cfg.get("frame_color", "white")
    if raw_fc not in ("none", "transparent"):
        draw.rounded_rectangle(
            [(fx, fy), (fx + fw, fy + fh)],
            radius=fc, outline=_resolve_color(raw_fc), width=3)

    # Area dalam frame
    ax, ay = fx + fi, fy + fi
    aw, ah = fw - 2 * fi, fh - 2 * fi
    n = len(photos)
    if n == 0:
        return

    kw = dict(corner_r=corner_r, border_w=border_w)

    # Gunakan custom rows jika dikonfigurasi
    grid_cfg = cfg.get("grid", {})
    if "rows" in grid_cfg:
        _put_custom_rows(canvas, photos, ax, ay, aw, ah, grid_cfg["rows"], gap, kw)
        return

    if n == 1:
        _put(canvas, photos[0], ax, ay, aw, ah, **kw)

    elif n == 2:
        h = (ah - gap) // 2
        _put(canvas, photos[0], ax, ay, aw, h, **kw)
        _put(canvas, photos[1], ax, ay + h + gap, aw, h, **kw)

    elif n == 3:
        th = int(ah * 0.52)
        bh = ah - th - gap
        bw = (aw - gap) // 2
        _put(canvas, photos[0], ax, ay, aw, th, **kw)
        _put(canvas, photos[1], ax, ay + th + gap, bw, bh, **kw)
        _put(canvas, photos[2],
             ax + bw + gap, ay + th + gap, aw - bw - gap, bh, **kw)

    elif n == 4:
        cw = (aw - gap) // 2
        ch = (ah - gap) // 2
        for i, p in enumerate(photos):
            r, c = divmod(i, 2)
            _put(canvas, p,
                 ax + c * (cw + gap), ay + r * (ch + gap), cw, ch, **kw)

    elif n in (5, 6):
        th = int(ah * 0.56)
        bh = ah - th - gap
        cl = int(aw * 0.54)
        cr = aw - cl - gap
        rh = (th - gap) // 2

        _put(canvas, photos[0], ax, ay, cl, th, **kw)
        _put(canvas, photos[1], ax + cl + gap, ay, cr, rh, **kw)
        _put(canvas, photos[2], ax + cl + gap, ay + rh + gap, cr, rh, **kw)

        bot = photos[3:]
        nb  = len(bot)
        bw  = (aw - gap * (nb - 1)) // nb
        for i, p in enumerate(bot):
            _put(canvas, p,
                 ax + i * (bw + gap), ay + th + gap, bw, bh, **kw)

    else:
        cols = 3
        rows = (n + cols - 1) // cols
        ch   = (ah - gap * (rows - 1)) // rows
        for r in range(rows):
            row_photos = photos[r * cols : (r + 1) * cols]
            nb  = len(row_photos)
            rw  = (aw - gap * (nb - 1)) // nb  # lebar menyesuaikan jumlah foto di baris
            for c, p in enumerate(row_photos):
                _put(canvas, p,
                     ax + c * (rw + gap), ay + r * (ch + gap), rw, ch, **kw)


# ---------------------------------------------------------------------------
# Text zones
# ---------------------------------------------------------------------------

def _draw_title(draw: ImageDraw.ImageDraw, title: str, cfg: dict) -> None:
    if "title" not in cfg or not title:
        return
    tc = cfg["title"]
    if tc.get("hidden"):
        return
    cx      = tc.get("cx", tc.get("x", 620))
    max_w   = tc.get("max_w", 1100)
    font_l  = _bold(tc.get("size_line1", 44))
    font_s  = _bold(tc.get("size_line2", 34))
    col1    = _resolve_color(tc.get("color_line1", "gold"))
    col2    = _resolve_color(tc.get("color_line2", "white"))
    lh1     = tc.get("line_h1", 54)
    lh2     = tc.get("line_h2", 44)

    # Pisahkan dengan | untuk paksa line break, lalu wrap tiap segmen
    segments = [s.strip() for s in title.upper().split("|")]
    lines: list[str] = []
    for seg in segments:
        lines.extend(_wrap(seg, font_l, max_w))

    y = tc["y"]
    for i, line in enumerate(lines):
        f, color, lh = (font_l, col1, lh1) if i == 0 else (font_s, col2, lh2)
        _draw_text_centered(draw, cx, y, line, f, color)
        y += lh


def _draw_info(draw: ImageDraw.ImageDraw,
               location: str | None, event_date: date, cfg: dict) -> None:
    date_str = f"{HARI_ID[event_date.weekday()]}, {event_date.day} {BULAN[event_date.month]} {event_date.year}"

    if location and "location" in cfg:
        lc = cfg["location"]
        _draw_text_centered(
            draw, lc.get("cx", lc.get("x", 620)), lc["y"],
            location,
            _bold(lc.get("size", 26)),
            _resolve_color(lc.get("color", "white")))

    if "date" in cfg:
        dc = cfg["date"]
        _draw_text_centered(
            draw, dc.get("cx", dc.get("x", 620)), dc["y"],
            date_str,
            _bold(dc.get("size", 24)),
            _resolve_color(dc.get("color", "gold")))


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_doc(
    title: str,
    photos: list[Image.Image],
    event_date: date | None = None,
    location: str | None = None,
    template: str = DEFAULT_TPL,
    output_path: str | Path | None = None,
) -> Image.Image:
    if event_date is None:
        event_date = date.today()

    cfg = _load_config(template)
    cw  = cfg["canvas"]["w"]
    ch  = cfg["canvas"]["h"]

    # Background — load template langsung sebagai RGB (sudah include header+footer)
    bg_path = TEMPLATES_DIR / template / "background.png"
    if bg_path.exists():
        bg = Image.open(bg_path)
        if bg.mode == "RGBA":
            # Composite RGBA di atas canvas teal
            base = Image.new("RGB", (cw, ch), (1, 171, 170))
            base.paste(bg.convert("RGB"), (0, 0), bg.split()[3])
            canvas = base
        else:
            canvas = bg.convert("RGB")
        if canvas.size != (cw, ch):
            canvas = canvas.resize((cw, ch), Image.LANCZOS)
    else:
        canvas = Image.new("RGB", (cw, ch), (0, 171, 169))
    draw   = ImageDraw.Draw(canvas)

    _draw_title(draw, title, cfg)
    _place_photos(canvas, draw, photos, cfg)
    _draw_info(draw, location, event_date, cfg)

    if output_path:
        canvas.save(str(output_path), "JPEG", quality=92)

    return canvas


# ---------------------------------------------------------------------------
# Apel / Briefing renderer
# ---------------------------------------------------------------------------

def render_apel(
    title: str,
    photos: list[Image.Image],
    event_date: date,
    location: str | None,
    quote: str,
    bg_idx: int = 0,
    template: str = "apel_default",
    output_path: str | Path | None = None,
) -> Image.Image:
    """Render template Apel Pagi: background blur + overlay + frame kolase + quote."""
    from PIL import ImageFilter

    # Baca config — nilai di config.json bisa diedit lewat editor web
    cfg      = _load_config(template) if (TEMPLATES_DIR / template / "config.json").exists() else {}
    ac       = cfg.get("apel", {})   # section khusus apel
    W, H     = cfg.get("canvas", {}).get("w", 1080), cfg.get("canvas", {}).get("h", 1350)

    BLUR_R       = ac.get("blur_radius",     10)
    DARK_ALPHA   = ac.get("dark_alpha",      75)
    GRAD_ALPHA   = ac.get("grad_alpha",     115)
    TITLE_X      = ac.get("title_x",         52)
    TITLE_Y      = ac.get("title_y",        155)
    TITLE_SIZE   = ac.get("title_size",      44)
    INFO_X       = ac.get("info_x",          52)
    INFO_FSIZE   = ac.get("info_font_size",  25)
    ICON_SZ      = ac.get("icon_sz",         22)
    FRAME_PAD    = ac.get("frame_pad",       34)
    QUOTE_H      = ac.get("quote_h",         155)
    QUOTE_Y_PAD  = ac.get("quote_y_pad",      36)
    Q_FSIZE      = ac.get("quote_font_size",  24)
    QUOTE_PAD_X  = ac.get("quote_pad_x",      20)
    FOOTER_RATIO = ac.get("footer_ratio",  0.09)
    INFO_GAP     = ac.get("info_gap",             12)
    FRAME_GAP    = ac.get("frame_gap",            16)
    FRAME_BOT    = ac.get("frame_bottom_margin",  18)

    PHOTO_GAP    = cfg.get("photo_gap",   40)
    CORNER_R     = cfg.get("corner_r",    14)
    BORDER_W     = cfg.get("border_w",     3)
    INNER        = cfg.get("frame_inner", 14)
    FRAME_CORNER = cfg.get("frame_corner", 22)

    PILL_PAD_X, PILL_PAD_Y = 12, 7

    # Foto background dan kolase (semua foto masuk kolase)
    if photos:
        bg_idx = max(0, min(bg_idx, len(photos) - 1))
        bg_photo = photos[bg_idx]
        collage_photos = list(photos)
    else:
        bg_photo = None
        collage_photos = []

    # 1. Background: foto di-blur, mengisi penuh canvas
    if bg_photo:
        bg = smart_crop(bg_photo, W, H).convert("RGBA")
    else:
        bg = Image.new("RGBA", (W, H), (15, 35, 65, 255))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=BLUR_R))

    # 2. Dark overlay ringan
    dark = Image.new("RGBA", (W, H), (15, 35, 65, DARK_ALPHA))
    canvas = Image.alpha_composite(bg, dark)

    # 3. Blue gradient overlay dari kiri ke tengah
    GRAD_STEPS = 64
    grad_src = Image.new("RGBA", (GRAD_STEPS, 1))
    for i in range(GRAD_STEPS):
        a = int(GRAD_ALPHA * (1 - i / (GRAD_STEPS - 1)))
        grad_src.putpixel((i, 0), (15, 40, 90, a))
    grad_layer = grad_src.resize((W // 2 + 100, H), Image.NEAREST)
    grad_canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad_canvas.paste(grad_layer, (0, 0))
    canvas = Image.alpha_composite(canvas, grad_canvas)

    # 4. Tempel overlay.png langsung
    tpl_dir = TEMPLATES_DIR / template
    ovl_path = tpl_dir / "overlay.png"
    if ovl_path.exists():
        ovl = Image.open(ovl_path).convert("RGBA")
        if ovl.size != (W, H):
            ovl = ovl.resize((W, H), Image.LANCZOS)
        canvas = Image.alpha_composite(canvas, ovl)

    # 5. Judul: rata kiri, Montserrat Black, outline tipis
    draw = ImageDraw.Draw(canvas)
    fnt_title = _montserrat_black(TITLE_SIZE)
    title_lines = _wrap(title.upper(), fnt_title, W - 100)
    bb_t = fnt_title.getbbox("A")
    lh_t = (bb_t[3] - bb_t[1]) + 8
    title_x, title_y = TITLE_X, TITLE_Y

    for line in title_lines:
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            draw.text((title_x + dx, title_y + dy), line, font=fnt_title, fill=(0, 0, 0, 180))
        draw.text((title_x, title_y), line, font=fnt_title, fill=(255, 255, 255, 255))
        title_y += lh_t

    # 6. Info: lokasi + tanggal dalam SATU baris  [pin] Lokasi  |  [cal] Tanggal
    fnt_info = _bold(INFO_FSIZE)
    bb_i     = fnt_info.getbbox("A")
    text_h   = bb_i[3] - bb_i[1]
    info_y   = title_y + INFO_GAP

    loc_text = location or "UPTD Puskesmas Cipatujah"
    date_str = (
        f"{HARI_ID[event_date.weekday()]}, "
        f"{event_date.day} {BULAN[event_date.month]} {event_date.year}"
    )

    SEP   = "   |   "
    loc_w = _tw(loc_text, fnt_info)
    sep_w = _tw(SEP,      fnt_info)
    dat_w = _tw(date_str, fnt_info)

    pill_h = text_h + PILL_PAD_Y * 2
    row_w  = PILL_PAD_X + ICON_SZ + 8 + loc_w + sep_w + ICON_SZ + 8 + dat_w + PILL_PAD_X

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld    = ImageDraw.Draw(layer)
    px0, py0 = INFO_X, info_y

    iy = py0 + (text_h - ICON_SZ) // 2
    ty = py0 - bb_i[1]
    cx = px0

    # Pin icon (lokasi)
    pin_file = ASSETS_DIR / "icons" / "icon_pin.png"
    if pin_file.exists():
        from PIL import ImageOps as _IO
        _p  = Image.open(pin_file).convert("L")
        _p  = _IO.invert(_p)
        _pw = Image.new("RGBA", _p.size, (255, 255, 255, 255))
        _pw.putalpha(_p)
        _pw = _pw.resize((ICON_SZ, ICON_SZ), Image.LANCZOS)
        layer.paste(_pw, (cx, iy), _pw.split()[3])
    else:
        IC = ICON_SZ * 4
        ic_img = Image.new("RGBA", (IC, IC), (0, 0, 0, 0))
        icd = ImageDraw.Draw(ic_img)
        HCX, HR = IC // 2, int(IC * 0.40)
        HCY = int(IC * 0.40)
        icd.ellipse([(HCX-HR, HCY-HR), (HCX+HR, HCY+HR)], fill=(255, 255, 255, 220))
        icd.polygon([
            (HCX - int(IC*0.16), HCY + int(IC*0.24)),
            (HCX + int(IC*0.16), HCY + int(IC*0.24)),
            (HCX, IC - int(IC*0.05)),
        ], fill=(255, 255, 255, 220))
        HOLE_R = int(HR * 0.40)
        icd.ellipse([(HCX-HOLE_R, HCY-HOLE_R), (HCX+HOLE_R, HCY+HOLE_R)], fill=(0, 0, 0, 0))
        ic_img = ic_img.resize((ICON_SZ, ICON_SZ), Image.LANCZOS)
        layer.paste(ic_img, (cx, iy), ic_img.split()[3])
    cx += ICON_SZ + 8
    ld.text((cx, ty), loc_text, font=fnt_info, fill=(255, 255, 255, 255))
    cx += loc_w

    # Separator
    ld.text((cx, ty), SEP, font=fnt_info, fill=(255, 255, 255, 130))
    cx += sep_w

    # Calendar icon (tanggal)
    bx0_c, by0_c = cx, iy
    bx1_c, by1_c = cx + ICON_SZ, iy + ICON_SZ
    ld.rounded_rectangle([(bx0_c, by0_c), (bx1_c, by1_c)], radius=2, fill=(255, 255, 255, 220))
    ld.rounded_rectangle([(bx0_c, by0_c), (bx1_c, by0_c + 6)], radius=2, fill=(80, 120, 200, 255))
    for col in range(3):
        for row in range(2):
            dx = bx0_c + 3 + col * 6
            dy = by0_c + 9 + row * 6
            ld.rectangle([(dx, dy), (dx + 3, dy + 3)], fill=(50, 80, 160, 200))
    cx += ICON_SZ + 8
    ld.text((cx, ty), date_str, font=fnt_info, fill=(255, 255, 255, 255))

    canvas = Image.alpha_composite(canvas, layer)
    info_y += text_h + PILL_PAD_Y * 2 + 6

    # 7. Frame outline mengelilingi kolase + quote
    frame_x0, frame_x1 = FRAME_PAD, W - FRAME_PAD
    frame_y0 = info_y + FRAME_GAP
    footer_h = int(H * FOOTER_RATIO)
    frame_y1 = H - footer_h - FRAME_BOT

    frame_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(frame_layer).rounded_rectangle(
        [(frame_x0, frame_y0), (frame_x1, frame_y1)],
        radius=FRAME_CORNER,
        outline=(255, 255, 255, 170),
        width=3,
        fill=(255, 255, 255, 18),
    )
    canvas = Image.alpha_composite(canvas, frame_layer)

    # 8. Foto kolase di dalam frame (foto landscape, gap lebar)
    photo_x0 = frame_x0 + INNER
    photo_y0 = frame_y0 + INNER
    photo_x1 = frame_x1 - INNER
    photo_y1 = frame_y1 - QUOTE_H - QUOTE_Y_PAD - INNER

    canvas_rgb = canvas.convert("RGB")
    if collage_photos:
        fake_cfg = {
            "photo_zone": {
                "x": photo_x0, "y": photo_y0,
                "w": photo_x1 - photo_x0,
                "h": photo_y1 - photo_y0,
            },
            "photo_gap":  PHOTO_GAP,
            "corner_r":   CORNER_R,
            "border_w":   BORDER_W,
            "frame_inner":  0,
            "frame_corner": 0,
            "frame_color": "none",
        }
        _place_photos(canvas_rgb, ImageDraw.Draw(canvas_rgb), collage_photos, fake_cfg)


    # 9. Quote: composite overlay statis (box + marks) + teks dinamis di atasnya
    canvas = canvas_rgb.convert("RGBA")
    if quote:
        fnt_quote  = _lora_italic(Q_FSIZE)
        frame_w    = frame_x1 - frame_x0
        frame_cx   = (frame_x0 + frame_x1) // 2
        q_lines    = _wrap(quote, fnt_quote, frame_w - 120)
        bb_q       = fnt_quote.getbbox("A")
        lh_q       = (bb_q[3] - bb_q[1]) + 12
        q_total_h  = max(1, len(q_lines)) * lh_q - 12

        # Box dan marks sudah ada di overlay.png — di sini hanya teks
        q_pill_y0 = frame_y1 - QUOTE_H - QUOTE_Y_PAD
        Q_TEXT_CY = ac.get("quote_text_cy", q_pill_y0 + QUOTE_H // 2)
        text_start_y = Q_TEXT_CY - q_total_h // 2
        q_y = text_start_y - bb_q[1]
        d_q = ImageDraw.Draw(canvas)
        for ln in q_lines:
            lx = frame_cx - _tw(ln, fnt_quote) // 2
            d_q.text((lx, q_y), ln, font=fnt_quote, fill=(255, 255, 255, 255))
            q_y += lh_q

    result = canvas.convert("RGB")
    if output_path:
        result.save(str(output_path), "JPEG", quality=92)
    return result
