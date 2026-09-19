"""
SMARTREPORT EDITOR — Aplikasi visual untuk mengelola template, layout, keyword, dan pengaturan bot.
Jalankan: streamlit run editor.py   (atau klik run_editor.bat)
"""
import base64
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw

# ── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

TEMPLATES_DIR = BASE_DIR / "assets" / "templates"
KEYWORDS_PATH = BASE_DIR / "assets" / "keywords.json"
META_PATH     = BASE_DIR / "assets" / "templates_meta.json"
ENV_PATH      = BASE_DIR / ".env"

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def list_templates() -> list[str]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir())


def _default_cfg() -> dict:
    return {
        "canvas": {"w": 1080, "h": 1350},
        "photo_zone": {"x": 70, "y": 277, "w": 940, "h": 839},
        "photo_gap": 15, "corner_r": 9, "border_w": 4,
        "frame_corner": 14, "frame_inner": 14, "frame_color": "white",
        "title": {
            "cx": 540, "y": 142, "max_w": 960,
            "size_line1": 40, "color_line1": "gold",
            "size_line2": 30, "color_line2": "white",
            "line_h1": 50, "line_h2": 38,
        },
        "location": {"cx": 540, "y": 1170, "size": 22, "color": "white"},
        "date":     {"cx": 540, "y": 1205, "size": 20, "color": "gold"},
    }


def load_config(tpl: str) -> dict:
    p = TEMPLATES_DIR / tpl / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else _default_cfg()


def save_config(tpl: str, cfg: dict) -> None:
    (TEMPLATES_DIR / tpl / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _build_new_cfg(cfg: dict, pz_x, pz_y, pz_w, pz_h,
                   photo_gap, corner_r, border_w, frame_corner, frame_inner, frame_color,
                   t_cx, t_y, t_maxw, t_sz1, t_col1, t_sz2, t_col2, t_lh1, t_lh2,
                   l_cx, l_y, l_sz, l_col, d_cx, d_y, d_sz, d_col,
                   apel_overrides: dict | None = None) -> dict:
    """Buat config baru dan preserve section khusus (apel, dll.) yang tidak dikelola editor."""
    new_cfg = {
        "canvas": cfg.get("canvas", {"w": 1080, "h": 1350}),
        "photo_zone": {"x": pz_x, "y": pz_y, "w": pz_w, "h": pz_h},
        "photo_gap": photo_gap, "corner_r": corner_r, "border_w": border_w,
        "frame_corner": frame_corner, "frame_inner": frame_inner, "frame_color": frame_color,
        "title": {
            "cx": t_cx, "y": t_y, "max_w": t_maxw,
            "size_line1": t_sz1, "color_line1": t_col1,
            "size_line2": t_sz2, "color_line2": t_col2,
            "line_h1": t_lh1, "line_h2": t_lh2,
        },
        "location": {"cx": l_cx, "y": l_y, "size": l_sz, "color": l_col},
        "date":     {"cx": d_cx, "y": d_y, "size": d_sz, "color": d_col},
    }
    # Preserve section lain yang tidak dikelola editor
    for k, v in cfg.items():
        if k not in new_cfg:
            new_cfg[k] = v
    # Update section "apel" dengan nilai baru dari editor
    if apel_overrides is not None:
        new_cfg["apel"] = {**cfg.get("apel", {}), **apel_overrides}
    return new_cfg


JENIS_LABEL = {
    "kegiatan":     "📋  Dokumentasi Kegiatan",
    "program":      "🏥  Program Kesehatan",
    "sppd":         "✈️  Perjalanan Dinas",
    "apel":         "🌅  Apel / Briefing Pagi",
    "belasungkawa": "🕊️  Ucapan Belasungkawa",
    "ucapan":       "🎉  Ucapan Selamat",
    "ultah":        "🎂  Ucapan Ulang Tahun",
}
JENIS_KEYS = list(JENIS_LABEL.keys())


def load_meta() -> dict:
    """Kembalikan {key: {"label": str, "type": str}} — migrasi format lama otomatis."""
    if not META_PATH.exists():
        return {"default": {"label": "Teal Classic", "type": "kegiatan"}}
    raw = json.loads(META_PATH.read_text(encoding="utf-8"))
    return {
        k: ({"label": v, "type": "kegiatan"} if isinstance(v, str) else v)
        for k, v in raw.items()
    }


def save_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def load_keywords() -> list[dict]:
    return json.loads(KEYWORDS_PATH.read_text(encoding="utf-8")) if KEYWORDS_PATH.exists() else []


def save_keywords(rules: list[dict]) -> None:
    KEYWORDS_PATH.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


def load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def save_env(env: dict) -> None:
    ENV_PATH.write_text(
        "\n".join(f"{k}={v}" for k, v in env.items()) + "\n", encoding="utf-8"
    )


# Konversi nama warna ke hex untuk color picker
_NAMED_HEX = {
    "gold":   "#ffd200",
    "white":  "#ffffff",
    "teal":   "#00abaa",
    "black":  "#000000",
    "red":    "#dc2626",
    "maroon": "#800000",
    "navy":   "#0f172a",
    "silver": "#c0c0c0",
    "yellow": "#ffeb3b",
    "orange": "#ff7814",
}


def _to_hex(val: str) -> str:
    """Kembalikan hex string dari nama warna atau hex langsung."""
    if val and val.startswith("#"):
        return val
    return _NAMED_HEX.get(val, "#ffffff")


def _placeholder_photos(n: int) -> list[Image.Image]:
    palette = [
        (52, 152, 219), (46, 204, 113), (231, 76, 60),
        (155, 89, 182), (241, 196, 15), (230, 126, 34),
        (26, 188, 156),  (52, 73, 94),   (149, 165, 166),
    ]
    imgs = []
    for i in range(n):
        img = Image.new("RGB", (400, 300), palette[i % len(palette)])
        d = ImageDraw.Draw(img)
        # Ikon gambar sederhana agar terlihat seperti foto
        cx, cy = 200, 150
        d.rectangle([(cx-60, cy-45), (cx+60, cy+45)], outline=(255,255,255), width=2)
        d.ellipse([(cx-18, cy-22), (cx+18, cy+14)], outline=(255,255,255), width=2)
        d.polygon([(cx-60, cy+45), (cx-15, cy+5), (cx+20, cy+30), (cx+45, cy+10), (cx+60, cy+45)],
                  outline=(255,255,255), width=2)
        imgs.append(img)
    return imgs


def do_preview(tpl: str, n: int, title: str, location: str, tpl_type: str = "kegiatan") -> Image.Image | None:
    try:
        if tpl_type == "apel":
            from src.renderer.canvas import render_apel
            return render_apel(
                title=title, photos=_placeholder_photos(n),
                event_date=date.today(), location=location,
                quote="Kualitas bukan kebetulan, selalu hasil dari usaha yang cerdas.",
                template=tpl,
            )
        from src.renderer.canvas import render_doc
        return render_doc(
            title=title, photos=_placeholder_photos(n),
            event_date=date.today(), location=location, template=tpl,
        )
    except Exception as e:
        st.error(f"Gagal render preview: {e}")
        return None


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartReport Editor",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* ── Reset & base ─────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: #f5f7fa !important;
}
.block-container {
    padding-top: 1.8rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px;
}

/* ── Typography ───────────────────────────────────────────── */
h1 { color: #1a56db !important; font-size: 1.8rem !important; }
h4 { color: #374151 !important; font-size: 1rem !important;
     font-weight: 700 !important; margin-top: 1.4rem !important;
     padding-bottom: 6px !important;
     border-bottom: 2px solid #e5e7eb !important; }
p, label, .stMarkdown { color: #374151 !important; }

/* ── Caption / subtext ────────────────────────────────────── */
[data-testid="stCaptionContainer"] p { color: #6b7280 !important; font-size: 0.85rem !important; }

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff !important;
    border-radius: 10px !important;
    padding: 6px !important;
    gap: 4px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.08) !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 0 20px !important;
    height: 40px !important;
    border-radius: 7px !important;
    color: #6b7280 !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: #1a56db !important;
    color: #ffffff !important;
}

/* ── Cards (white boxes) ─────────────────────────────────── */
[data-testid="stForm"],
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
    padding: 4px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.06) !important;
}

/* ── Inputs ───────────────────────────────────────────────── */
input[type="text"], input[type="number"], textarea {
    border-radius: 8px !important;
    border: 1px solid #d1d5db !important;
    background: #f9fafb !important;
    color: #111827 !important;
    font-size: 14px !important;
}
input[type="number"] { font-family: monospace !important; }
input:focus, textarea:focus {
    border-color: #1a56db !important;
    box-shadow: 0 0 0 3px rgba(26,86,219,.15) !important;
}

/* ── Selectbox ────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    border-radius: 8px !important;
    border: 1px solid #d1d5db !important;
    background: #f9fafb !important;
}

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 0.45rem 1.1rem !important;
    border: none !important;
    transition: opacity .15s, transform .1s !important;
}
.stButton > button:hover { opacity: .88 !important; transform: translateY(-1px) !important; }
.stButton > button[kind="primary"] {
    background: #1a56db !important;
    color: white !important;
}
.stButton > button[kind="secondary"] {
    background: #f3f4f6 !important;
    color: #374151 !important;
    border: 1px solid #e5e7eb !important;
}

/* ── Slider ───────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #1a56db !important;
}

/* ── File uploader ────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #d1d5db !important;
    border-radius: 10px !important;
    background: #f9fafb !important;
    padding: 8px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #1a56db !important;
    background: #eff6ff !important;
}

/* ── Alert / success ─────────────────────────────────────── */
div.stAlert { border-radius: 10px !important; }

/* ── Image caption ────────────────────────────────────────── */
[data-testid="caption"] { color: #6b7280 !important; }

/* ── Expander header ──────────────────────────────────────── */
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #1f2937 !important;
    padding: 10px 14px !important;
}

/* ── Separator line ───────────────────────────────────────── */
hr { border-color: #e5e7eb !important; margin: 1.2rem 0 !important; }

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
_logo_path = BASE_DIR / "assets" / "logo" / "template_1.png"
_logo_tag  = ""
if _logo_path.exists():
    _b64 = base64.b64encode(_logo_path.read_bytes()).decode()
    _logo_tag = (
        f'<img src="data:image/png;base64,{_b64}" '
        'style="height:56px;width:56px;object-fit:contain;'
        'border-radius:10px;flex-shrink:0;">'
    )

st.markdown(f"""
<div style="background:linear-gradient(135deg,#1a56db,#1e40af);
            border-radius:14px; padding:22px 28px;
            margin-top:18px; margin-bottom:24px;
            display:flex; align-items:center; gap:18px;">
  {_logo_tag}
  <div>
    <div style="color:white; font-size:1.5rem; font-weight:700; line-height:1.2;">
      SmartReport Editor
    </div>
    <div style="color:#bfdbfe; font-size:0.88rem; margin-top:4px;">
      Kelola template, layout, keyword, dan pengaturan bot — tanpa sentuh kode
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
t_layout, t_keywords, t_bot, t_help = st.tabs([
    "📐  Template & Layout",
    "🔤  Keyword",
    "⚙️  Pengaturan Bot",
    "📖  Panduan",
])


# =============================================================================
# TAB 1 — Template & Layout
# =============================================================================
with t_layout:
    templates = list_templates()
    meta      = load_meta()

    # Filter jenis
    jenis_filter = st.radio(
        "Filter jenis:",
        options=["semua"] + JENIS_KEYS,
        horizontal=True,
        format_func=lambda k: "Semua" if k == "semua" else JENIS_LABEL[k],
        key="jenis_filter",
    )

    filtered_tpls = templates if jenis_filter == "semua" else [
        k for k in templates if meta.get(k, {}).get("type", "kegiatan") == jenis_filter
    ]

    # Top bar
    bc1, bc2, bc3 = st.columns([3, 1.4, 1.4])
    with bc1:
        selected = st.selectbox(
            "Template aktif:",
            options=filtered_tpls,
            format_func=lambda k: f"{meta[k]['label']}  [{k}]",
            key=f"tpl_sel_{jenis_filter}",
        ) if filtered_tpls else None
        if not filtered_tpls:
            st.caption(f"Belum ada template untuk jenis ini. Klik ➕ untuk membuat.")
    with bc2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕  Tambah Template", use_container_width=True):
            st.session_state["_add"] = True
    with bc3:
        st.markdown("<br>", unsafe_allow_html=True)
        can_del = selected and selected != "default"
        if can_del and st.button("🗑️  Hapus Template", use_container_width=True):
            st.session_state["_del"] = selected

    # Hapus template
    if st.session_state.get("_del"):
        todel = st.session_state["_del"]
        shutil.rmtree(TEMPLATES_DIR / todel, ignore_errors=True)
        meta.pop(todel, None)
        save_meta(meta)
        del st.session_state["_del"]
        st.warning(f"Template '{todel}' dihapus.")
        st.rerun()

    # Form tambah template
    if st.session_state.get("_add"):
        with st.form("add_tpl_form", border=True):
            st.markdown("#### Template Baru")
            fa, fb = st.columns(2)
            new_key   = fa.text_input("ID template (huruf kecil, tanpa spasi):", placeholder="belasungkawa_formal")
            new_label = fb.text_input("Nama yang ditampilkan di bot:", placeholder="Belasungkawa Formal")
            new_type  = st.selectbox(
                "Jenis dokumen:",
                options=JENIS_KEYS,
                format_func=lambda k: JENIS_LABEL[k],
                index=JENIS_KEYS.index(jenis_filter) if jenis_filter in JENIS_KEYS else 0,
            )
            new_bg    = st.file_uploader("Background PNG (1080×1350 px) — kosongkan untuk copy dari default:", type=["png"])
            ok, cnl   = st.columns(2)
            submitted  = ok.form_submit_button("Buat Template", use_container_width=True, type="primary")
            cancelled  = cnl.form_submit_button("Batal", use_container_width=True)

            if cancelled:
                st.session_state["_add"] = False
                st.rerun()
            if submitted and new_key:
                key  = re.sub(r"[^a-z0-9_]", "_", new_key.lower())
                tdir = TEMPLATES_DIR / key
                tdir.mkdir(parents=True, exist_ok=True)
                save_config(key, _default_cfg())
                if new_bg:
                    (tdir / "background.png").write_bytes(new_bg.read())
                else:
                    src = TEMPLATES_DIR / "default" / "background.png"
                    if src.exists():
                        shutil.copy(src, tdir / "background.png")
                meta[key] = {"label": new_label or key, "type": new_type}
                save_meta(meta)
                st.session_state["_add"] = False
                st.success(f"Template '{key}' berhasil dibuat!")
                st.rerun()

    if not selected:
        st.info("Belum ada template. Klik ➕ Tambah Template untuk memulai.")
    else:
        st.markdown("---")
        cfg = load_config(selected)
        K   = selected  # prefix unik untuk widget key

        # Template PDF (SPPD) — tidak diedit lewat canvas editor
        _cur_type = meta.get(selected, {}).get("type", "kegiatan")
        if _cur_type == "sppd":
            st.info(
                "✈️ Template ini adalah **PDF Perjalanan Dinas** — dikonfigurasi lewat "
                "`pdf_config.json` di folder template, bukan lewat editor canvas.",
                icon="ℹ️",
            )
            pdf_cfg_path = TEMPLATES_DIR / selected / "pdf_config.json"
            if pdf_cfg_path.exists():
                st.code(pdf_cfg_path.read_text(encoding="utf-8"), language="json")
            tpl_info  = meta.get(selected, {})
            tpl_label = st.text_input("Nama tampilan di bot:", value=tpl_info.get("label", selected), key=f"{K}_label")
            if st.button("💾  Simpan Nama", key=f"{K}_savelabel"):
                meta[selected] = {"label": tpl_label, "type": "sppd"}
                save_meta(meta)
                st.success("Nama disimpan.")
            st.stop()

        if _cur_type == "apel":
            st.info(
                "🌅 **Template Apel / Briefing Pagi** — "
                "kontrol yang aktif: **Zona Foto** (gap, radius, border, padding, frame corner). "
                "Section Judul & Lokasi/Tanggal tidak digunakan karena apel punya layout sendiri. "
                "Parameter khusus apel (ukuran font, gradien, dll.) ada di section **`\"apel\"`** "
                "di file `config.json` dan tetap dipreserve saat simpan.",
                icon="ℹ️",
            )

        col_ctrl, col_prev = st.columns([1.1, 0.9], gap="large")

        # ── Panel kiri: kontrol ──────────────────────────────────────────────
        with col_ctrl:

            # Nama, jenis & background
            st.markdown("#### Nama & Background")
            na, nb, nc = st.columns([2, 1.8, 1.8])
            tpl_info  = meta.get(selected, {})
            tpl_label = na.text_input("Nama tampilan di bot:", value=tpl_info.get("label", selected), key=f"{K}_label")
            cur_type  = tpl_info.get("type", "kegiatan")
            tpl_type  = nb.selectbox(
                "Jenis dokumen:", options=JENIS_KEYS,
                index=JENIS_KEYS.index(cur_type) if cur_type in JENIS_KEYS else 0,
                format_func=lambda k: JENIS_LABEL[k],
                key=f"{K}_type",
            )
            new_bg    = nc.file_uploader("Ganti background (PNG):", type=["png"], key=f"{K}_bgup")
            bg_path   = TEMPLATES_DIR / selected / "background.png"
            if new_bg:
                bg_path.write_bytes(new_bg.read())
                st.success("Background diperbarui!")

            if bg_path.exists():
                with st.expander("Lihat background saat ini"):
                    st.image(str(bg_path), width=280)

            # Zona foto
            st.markdown("#### Zona Foto")
            st.caption("Tentukan di mana kolase foto ditempatkan dalam canvas 1080×1350.")
            pz = cfg.get("photo_zone", {})
            za, zb = st.columns(2)
            pz_x = za.number_input("X — jarak dari kiri (px)", value=int(pz.get("x", 70)),   step=5,  key=f"{K}_px")
            pz_y = zb.number_input("Y — jarak dari atas (px)", value=int(pz.get("y", 277)),  step=5,  key=f"{K}_py")
            pz_w = za.number_input("Lebar zona foto (px)",      value=int(pz.get("w", 940)),  step=5,  key=f"{K}_pw")
            pz_h = zb.number_input("Tinggi zona foto (px)",     value=int(pz.get("h", 839)),  step=5,  key=f"{K}_ph")

            ga, gb, gc = st.columns(3)
            photo_gap    = ga.number_input("Jarak antar foto",    value=int(cfg.get("photo_gap",    15)), step=1, key=f"{K}_pgap")
            corner_r     = gb.number_input("Radius sudut foto",   value=int(cfg.get("corner_r",      9)), step=1, key=f"{K}_cr")
            border_w     = gc.number_input("Tebal border putih",  value=int(cfg.get("border_w",      4)), step=1, key=f"{K}_bw")
            fa2, fb2, fc2 = st.columns(3)
            frame_corner = fa2.number_input("Radius sudut frame", value=int(cfg.get("frame_corner", 14)), step=1, key=f"{K}_fc")
            frame_inner  = fb2.number_input("Padding dalam frame",value=int(cfg.get("frame_inner",  14)), step=1, key=f"{K}_fi")
            frame_color  = fc2.color_picker("Warna garis frame",  value=_to_hex(cfg.get("frame_color","white")), key=f"{K}_fcol")

            if tpl_type == "apel":
                # ── Kontrol khusus Apel ──────────────────────────────────────
                ac = cfg.get("apel", {})

                st.markdown("#### Judul Kegiatan")
                aa, ab, ac1 = st.columns(3)
                apel_title_x  = aa.number_input("X (dari kiri)",  value=int(ac.get("title_x",   52)), step=2, key=f"{K}_atx")
                apel_title_y  = ab.number_input("Y (dari atas)",  value=int(ac.get("title_y",  155)), step=2, key=f"{K}_aty")
                apel_title_sz = ac1.number_input("Ukuran font",   value=int(ac.get("title_size", 44)), step=1, key=f"{K}_atsz")

                st.markdown("#### Tempat & Tanggal")
                ia, ib, ic = st.columns(3)
                apel_info_x   = ia.number_input("X (dari kiri)",       value=int(ac.get("info_x",          52)), step=2, key=f"{K}_aix")
                apel_info_gap = ib.number_input("Jarak dari judul (px)",value=int(ac.get("info_gap",         12)), step=1, key=f"{K}_aigap")
                apel_info_sz  = ic.number_input("Ukuran font",          value=int(ac.get("info_font_size",   25)), step=1, key=f"{K}_aisz")

                st.markdown("#### Outline / Frame")
                oa, ob, oc = st.columns(3)
                apel_frame_gap = oa.number_input("Jarak info → frame (px)",  value=int(ac.get("frame_gap",            16)), step=1, key=f"{K}_afgap")
                apel_frame_bot = ob.number_input("Jarak frame → bawah (px)", value=int(ac.get("frame_bottom_margin",  18)), step=1, key=f"{K}_afbot")
                apel_fp2       = oc.number_input("Padding kiri-kanan frame", value=int(ac.get("frame_pad",            34)), step=2, key=f"{K}_afp2")

                st.markdown("#### Quote")
                qa, qb = st.columns(2)
                apel_quote_h  = qa.number_input("Tinggi area quote (px)", value=int(ac.get("quote_h",          115)), step=5, key=f"{K}_aqh")
                apel_quote_sz = qb.number_input("Ukuran font quote",      value=int(ac.get("quote_font_size",   24)), step=1, key=f"{K}_aqsz")

                with st.expander("Efek visual (blur, overlay, gradien)"):
                    ea, eb, ec = st.columns(3)
                    apel_blur = ea.number_input("Blur background", value=int(ac.get("blur_radius",  10)), step=1, key=f"{K}_abl")
                    apel_dark = eb.number_input("Gelap overlay",   value=int(ac.get("dark_alpha",   75)), step=5, key=f"{K}_adk")
                    apel_grad = ec.number_input("Gradien biru",    value=int(ac.get("grad_alpha",  115)), step=5, key=f"{K}_agr")

                apel_overrides = {
                    "title_x": apel_title_x, "title_y": apel_title_y, "title_size": apel_title_sz,
                    "info_x": apel_info_x, "info_font_size": apel_info_sz,
                    "info_gap": apel_info_gap,
                    "frame_gap": apel_frame_gap, "frame_bottom_margin": apel_frame_bot,
                    "frame_pad": apel_fp2,
                    "quote_h": apel_quote_h, "quote_font_size": apel_quote_sz,
                    "blur_radius": apel_blur, "dark_alpha": apel_dark, "grad_alpha": apel_grad,
                }
                # Nilai dummy untuk _build_new_cfg (standard sections diabaikan oleh render_apel)
                tc = cfg.get("title", {}); lc = cfg.get("location", {}); dc = cfg.get("date", {})
                t_cx, t_y, t_maxw = int(tc.get("cx",540)), int(tc.get("y",142)), int(tc.get("max_w",960))
                t_sz1, t_col1 = int(tc.get("size_line1",40)), _to_hex(tc.get("color_line1","gold"))
                t_sz2, t_col2 = int(tc.get("size_line2",30)), _to_hex(tc.get("color_line2","white"))
                t_lh1, t_lh2  = int(tc.get("line_h1",50)), int(tc.get("line_h2",38))
                l_cx, l_y, l_sz, l_col = int(lc.get("cx",540)), int(lc.get("y",1170)), int(lc.get("size",22)), _to_hex(lc.get("color","white"))
                d_cx, d_y, d_sz, d_col = int(dc.get("cx",540)), int(dc.get("y",1205)), int(dc.get("size",20)), _to_hex(dc.get("color","gold"))

            else:
                # ── Kontrol standar (kegiatan, program, dll.) ────────────────
                apel_overrides = None

                st.markdown("#### Judul Kegiatan")
                tc = cfg.get("title", {})
                ta, tb = st.columns(2)
                t_cx   = ta.number_input("X pusat teks judul",        value=int(tc.get("cx",       540)), step=5,  key=f"{K}_tcx")
                t_y    = tb.number_input("Y posisi judul",             value=int(tc.get("y",        142)), step=5,  key=f"{K}_ty")
                t_maxw = st.number_input("Lebar maks teks (px)",       value=int(tc.get("max_w",    960)), step=10, key=f"{K}_tmw")

                tc1, tc2 = st.columns(2)
                t_sz1  = tc1.number_input("Font baris pertama (px)",   value=int(tc.get("size_line1", 40)), step=1, key=f"{K}_ts1")
                t_sz2  = tc2.number_input("Font baris berikutnya (px)",value=int(tc.get("size_line2", 30)), step=1, key=f"{K}_ts2")
                tw1, tw2 = st.columns(2)
                t_col1 = tw1.color_picker("Warna baris 1",  value=_to_hex(tc.get("color_line1","gold")),  key=f"{K}_tc1")
                t_col2 = tw2.color_picker("Warna baris 2+", value=_to_hex(tc.get("color_line2","white")), key=f"{K}_tc2")
                th1, th2 = st.columns(2)
                t_lh1  = th1.number_input("Jarak baris 1 (px)",        value=int(tc.get("line_h1", 50)), step=2, key=f"{K}_lh1")
                t_lh2  = th2.number_input("Jarak baris 2+ (px)",       value=int(tc.get("line_h2", 38)), step=2, key=f"{K}_lh2")

                st.markdown("#### Lokasi & Tanggal")
                lc = cfg.get("location", {})
                dc = cfg.get("date", {})

                la, lb, lc2 = st.columns(3)
                l_cx  = la.number_input("Lokasi X",     value=int(lc.get("cx",   540)), step=5, key=f"{K}_lcx")
                l_y   = lb.number_input("Lokasi Y",     value=int(lc.get("y",   1170)), step=5, key=f"{K}_ly")
                l_sz  = lc2.number_input("Font lokasi", value=int(lc.get("size",  22)), step=1, key=f"{K}_lsz")
                l_col = st.color_picker("Warna lokasi", value=_to_hex(lc.get("color","white")), key=f"{K}_lcol")

                da, db, dc2 = st.columns(3)
                d_cx  = da.number_input("Tanggal X",     value=int(dc.get("cx",   540)), step=5, key=f"{K}_dcx")
                d_y   = db.number_input("Tanggal Y",     value=int(dc.get("y",   1205)), step=5, key=f"{K}_dy")
                d_sz  = dc2.number_input("Font tanggal", value=int(dc.get("size",  20)), step=1, key=f"{K}_dsz")
                d_col = st.color_picker("Warna tanggal", value=_to_hex(dc.get("color","gold")), key=f"{K}_dcol")

            st.markdown("---")
            if st.button("💾  Simpan Config", use_container_width=True, type="primary", key=f"{K}_save"):
                new_cfg = _build_new_cfg(
                    cfg, pz_x, pz_y, pz_w, pz_h,
                    photo_gap, corner_r, border_w, frame_corner, frame_inner, frame_color,
                    t_cx, t_y, t_maxw, t_sz1, t_col1, t_sz2, t_col2, t_lh1, t_lh2,
                    l_cx, l_y, l_sz, l_col, d_cx, d_y, d_sz, d_col,
                    apel_overrides=apel_overrides,
                )
                save_config(selected, new_cfg)
                meta[selected] = {"label": tpl_label, "type": tpl_type}
                save_meta(meta)
                st.success("Config tersimpan!")

        # ── Panel kanan: preview ─────────────────────────────────────────────
        with col_prev:
            st.markdown("#### Preview")
            prev_title = st.text_input(
                "Judul preview:", value="Rapat Koordinasi Lintas Sektor", key="prev_title"
            )
            prev_loc = st.text_input(
                "Lokasi preview:", value="Aula UPTD Puskesmas Cipatujah", key="prev_loc"
            )
            prev_n = st.slider("Jumlah foto:", 1, 9, 4, key="prev_n")

            if st.button("🔄  Render Preview", use_container_width=True, type="primary", key="render_btn"):
                # Auto-simpan config sebelum render agar renderer membaca nilai terbaru
                new_cfg = _build_new_cfg(
                    cfg, pz_x, pz_y, pz_w, pz_h,
                    photo_gap, corner_r, border_w, frame_corner, frame_inner, frame_color,
                    t_cx, t_y, t_maxw, t_sz1, t_col1, t_sz2, t_col2, t_lh1, t_lh2,
                    l_cx, l_y, l_sz, l_col, d_cx, d_y, d_sz, d_col,
                    apel_overrides=apel_overrides,
                )
                save_config(selected, new_cfg)
                meta[selected] = {"label": tpl_label, "type": tpl_type}
                save_meta(meta)

                with st.spinner("Rendering..."):
                    img = do_preview(selected, prev_n, prev_title, prev_loc, tpl_type)
                if img:
                    buf = io.BytesIO()
                    img.save(buf, "JPEG", quality=88)
                    st.session_state["_prev_img"] = buf.getvalue()
                    st.session_state["_prev_tpl"] = meta.get(selected, selected)

            if st.session_state.get("_prev_img"):
                st.image(st.session_state["_prev_img"],
                         caption=f"Preview — {st.session_state.get('_prev_tpl', '')}",
                         use_container_width=True)
                st.download_button(
                    "⬇️  Download preview",
                    data=st.session_state["_prev_img"],
                    file_name=f"preview_{selected}.jpg",
                    mime="image/jpeg",
                    key="dl_prev",
                )


# =============================================================================
# TAB 2 — Keyword
# =============================================================================
with t_keywords:
    st.markdown("#### Keyword Recognition")
    st.caption(
        "Jika input user ≤ 4 kata dan cocok salah satu keyword, "
        "judul diganti otomatis ke judul standar. Urutan di sini = prioritas pencocokan."
    )

    rules = load_keywords()

    if rules:
        for i, rule in enumerate(rules):
            title_kw = rule.get("title", "—")
            kws      = rule.get("keywords", [])
            with st.expander(f"**{title_kw}**  · {len(kws)} keyword", expanded=False):
                new_t = st.text_input("Judul standar:", value=title_kw, key=f"kqt_{i}")
                new_k = st.text_area(
                    "Keywords (satu per baris — dari spesifik ke umum):",
                    value="\n".join(kws), height=120, key=f"kqk_{i}"
                )
                ka, kb = st.columns(2)
                if ka.button("💾  Update", key=f"kqu_{i}", use_container_width=True):
                    rules[i] = {
                        "title": new_t.strip(),
                        "keywords": [k.strip() for k in new_k.splitlines() if k.strip()],
                    }
                    save_keywords(rules)
                    st.success("Tersimpan!")
                    st.rerun()
                if kb.button("🗑️  Hapus rule ini", key=f"kqd_{i}", use_container_width=True):
                    rules.pop(i)
                    save_keywords(rules)
                    st.rerun()
    else:
        st.info("Belum ada rule keyword.")

    st.markdown("---")
    st.markdown("#### ➕ Tambah Rule Baru")
    with st.form("kw_add_form", border=True):
        new_title = st.text_input("Judul standar:", placeholder="Posyandu Balita")
        new_kws   = st.text_area(
            "Keywords (satu per baris):",
            placeholder="posyandu balita\nposyandu bayi\nimunisasi balita",
            height=110,
        )
        if st.form_submit_button("Tambah Rule", use_container_width=True):
            if new_title.strip():
                kw_list = [k.strip() for k in new_kws.splitlines() if k.strip()]
                rules.append({"title": new_title.strip(), "keywords": kw_list})
                save_keywords(rules)
                st.success(f"Rule '{new_title.strip()}' ditambahkan!")
                st.rerun()


# =============================================================================
# TAB 3 — Bot Settings
# =============================================================================
with t_bot:
    st.markdown("#### Pengaturan Bot Telegram")
    env = load_env()

    with st.form("env_form", border=True):
        st.markdown("**Telegram**")
        ea, eb = st.columns(2)
        token = ea.text_input(
            "Bot Token:", value=env.get("TELEGRAM_TOKEN", ""),
            type="password", help="Dari @BotFather — jangan dibagikan"
        )
        admin = eb.text_input(
            "Admin Chat ID:", value=env.get("ADMIN_CHAT_ID", ""),
            help="Kirim /myid ke bot untuk mengetahui ID kamu"
        )

        st.markdown("**Perilaku Bot**")
        ba, bb = st.columns(2)
        loc = ba.text_input(
            "Lokasi Default:", value=env.get("LOCATION_DEFAULT", "UPTD Puskesmas Cipatujah"),
            help="Muncul jika user tidak mengisi lokasi"
        )
        timeout = bb.number_input(
            "Batch Timeout (detik):", min_value=5, max_value=300, step=5,
            value=int(env.get("BATCH_TIMEOUT", "30")),
            help="Bot auto-generate setelah diam N detik sejak foto terakhir"
        )
        max_p = st.number_input(
            "Maks Foto per Dokumen:", min_value=1, max_value=20,
            value=int(env.get("MAX_PHOTOS", "9")),
            help="Jika kirim lebih banyak, sistem pilih foto yang paling landscape"
        )

        if st.form_submit_button("💾  Simpan Pengaturan", use_container_width=True, type="primary"):
            save_env({
                "TELEGRAM_TOKEN": token,
                "LOCATION_DEFAULT": loc,
                "BATCH_TIMEOUT": str(int(timeout)),
                "MAX_PHOTOS": str(int(max_p)),
                "ADMIN_CHAT_ID": admin,
            })
            st.success("Pengaturan disimpan. Restart bot agar berlaku.")

    st.markdown("---")
    st.markdown("#### Cara Restart Bot")
    st.info(
        "1. Buka Task Manager (Ctrl+Shift+Esc)\n"
        "2. Cari proses **python.exe** → klik kanan → End Task\n"
        "3. Klik dua kali **run_bot_hidden.vbs**"
    )

    st.markdown("---")
    st.markdown("#### 🚀 Push ke Git")
    st.caption(
        "Commit dan push semua perubahan (config, editor, renderer) ke GitHub, "
        "lalu ketik **/update** di bot agar bot PC ikut sinkron."
    )

    def _git(cmd: list[str]) -> tuple[int, str]:
        r = subprocess.run(
            ["git"] + cmd, cwd=str(BASE_DIR),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return r.returncode, (r.stdout + r.stderr).strip()

    # Status file yang berubah
    _, status_out = _git(["status", "--short"])
    changed_lines = [l for l in status_out.splitlines() if l.strip()]
    if changed_lines:
        st.markdown("**File yang akan di-commit:**")
        st.code("\n".join(changed_lines), language="bash")
    else:
        st.success("✅ Tidak ada perubahan — repo sudah up-to-date.")

    with st.form("git_push_form", border=True):
        commit_msg = st.text_input(
            "Pesan commit:",
            placeholder="update config & layout apel",
            help="Tulis singkat apa yang diubah",
        )
        pushed = st.form_submit_button(
            "📤  Commit & Push", use_container_width=True, type="primary",
            disabled=not changed_lines,
        )

    if pushed:
        if not commit_msg.strip():
            st.warning("Isi pesan commit dulu.")
        else:
            with st.spinner("Menjalankan git..."):
                rc1, out1 = _git(["add", "-A"])
                rc2, out2 = _git(["commit", "-m", commit_msg.strip()])
                rc3, out3 = _git(["push"])
            if rc2 != 0 and "nothing to commit" in out2:
                st.info("Tidak ada yang perlu di-commit.")
            elif rc3 != 0:
                st.error(f"Push gagal:\n```\n{out3}\n```")
            else:
                st.success("✅ Berhasil push! Ketik **/update** di bot untuk sync.")
                st.code(out3 or out2, language="bash")
                st.rerun()


# =============================================================================
# TAB 4 — Panduan
# =============================================================================
with t_help:
    st.markdown("""
#### 📐 Template & Layout

**Cara edit template:**
1. Pilih template dari dropdown di atas
2. Ubah nilai di panel kiri (zona foto, judul, warna, dll.)
3. Klik **Render Preview** untuk lihat hasilnya langsung
4. Klik **Simpan Config** jika sudah puas

**Cara tambah template:**
1. Buat desain background di Canva/Photoshop ukuran **1080×1350 px** (PNG)
2. Klik **➕ Tambah Template**
3. Isi ID, nama tampilan, upload background, klik Buat
4. Edit koordinat zona foto agar sesuai desain background baru

---

#### Penjelasan field layout

| Field | Keterangan |
|---|---|
| Zona Foto X / Y | Pojok kiri atas area kolase dalam pixel |
| Zona Foto W / H | Lebar × tinggi area kolase |
| Jarak antar foto | Gap antara foto-foto dalam kolase |
| Radius sudut foto | Kelingkaran pojok foto (0 = kotak, lebih besar = lebih bulat) |
| Tebal border putih | Ketebalan border di sekitar setiap foto |
| Padding dalam frame | Jarak antara garis frame luar dan foto pertama |
| X pusat teks judul | Biasanya 540 (tengah canvas 1080px) |
| Jarak baris | Jarak vertikal antar baris teks |

---

#### 🔤 Keyword

- Setiap rule: **judul standar** + beberapa **keyword pemicu**
- Hanya aktif jika input user **≤ 4 kata**
- Susun dari keyword paling spesifik ke paling umum agar tidak bentrok
- Contoh: `posyandu balita` harus di atas `posyandu`

---

#### ⚙️ Bot Settings

| Pengaturan | Keterangan |
|---|---|
| Bot Token | Token rahasia dari @BotFather |
| Admin Chat ID | Dapatkan dengan kirim `/myid` ke bot |
| Lokasi Default | Ditampilkan jika user tidak mengisi lokasi |
| Batch Timeout | Detik tunggu setelah foto terakhir sebelum auto-generate |
| Maks Foto | Jika kirim lebih dari ini, diambil yang paling landscape |

> Setelah ubah pengaturan atau keyword, **restart bot** agar perubahan aktif.
    """)
