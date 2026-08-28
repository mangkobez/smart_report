"""
Flow bertahap dengan pilihan jenis dokumen:
/mulai → Pilih Jenis → ... flow per jenis ... → Pilih Template → Foto → Generate
"""
import io
import json
from datetime import date
from pathlib import Path

from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)

from . import session as sess
from .recognizer import recognize
from .parser import parse_date, fmt_date
from .handlers import _generate_and_send, _generate_and_send_pdf, receive_scan_doc, LOCATION_DEFAULT

# ── States ─────────────────────────────────────────────────────────────────────
DOC_TYPE, SUBTYPE, INPUT_A, INPUT_B, INPUT_C, TEMPLATE_SEL, PHOTOS, SPPD_DOCS = range(8)

# ── Katalog jenis dokumen ──────────────────────────────────────────────────────
JENIS_DOC = {
    "kegiatan":     "📋  Dokumentasi Kegiatan",
    "program":      "🏥  Program Kesehatan",
    "sppd":         "✈️  Perjalanan Dinas (SPPD)",
    "belasungkawa": "🕊️  Ucapan Belasungkawa",
    "ucapan":       "🎉  Ucapan Selamat",
    "ultah":        "🎂  Ucapan Ulang Tahun",
}

SUB_UCAPAN = {
    "dilantik":    "Selamat Atas Dilantiknya",
    "wisuda":      "Selamat Wisuda",
    "paripurna":   "Selamat Atas Sidang Paripurna",
    "pensiun":     "Selamat Purna Tugas",
    "penghargaan": "Selamat Atas Penghargaan",
    "lainnya":     "Selamat",
}


# ── Template loader ────────────────────────────────────────────────────────────
def _load_meta() -> dict:
    """Kembalikan {key: {label, type}} — support format lama dan baru."""
    p = Path(__file__).parent.parent.parent / "assets" / "templates_meta.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        result = {}
        for k, v in raw.items():
            result[k] = {"label": v, "type": "kegiatan"} if isinstance(v, str) else v
        return result
    except Exception:
        return {"default": {"label": "Teal Classic", "type": "kegiatan"}}


# ── Keyboard helpers ───────────────────────────────────────────────────────────
def _fmt(d: date) -> str:
    return fmt_date(d)


def _kb_doc_type() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"jenis:{key}")]
        for key, label in JENIS_DOC.items()
    ])


def _kb_sub_ucapan() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"sub:{key}")]
        for key, label in SUB_UCAPAN.items()
    ])


def _kb_skip(data: str = "skip", label: str = "Lewati") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data)]])


def _kb_today() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Hari ini — {_fmt(date.today())}", callback_data="today")
    ]])


def _kb_template(doc_type: str | None = None) -> InlineKeyboardMarkup:
    meta = _load_meta()
    rows = [
        [InlineKeyboardButton(info["label"], callback_data=f"tpl:{key}")]
        for key, info in meta.items()
        if doc_type is None or info.get("type", "kegiatan") == doc_type
    ]
    if not rows:  # fallback: tampilkan semua jika tidak ada yang cocok
        rows = [
            [InlineKeyboardButton(info["label"], callback_data=f"tpl:{key}")]
            for key, info in meta.items()
        ]
    return InlineKeyboardMarkup(rows)


# ── Entry: /mulai ──────────────────────────────────────────────────────────────
async def mulai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    s = sess.get(chat_id)
    if s.job:
        s.job.schedule_removal()
    sess.clear(chat_id)
    context.user_data.clear()

    await update.message.reply_text(
        "Pilih jenis dokumen yang akan dibuat:",
        reply_markup=_kb_doc_type(),
    )
    return DOC_TYPE


# ── DOC_TYPE: pilih jenis ──────────────────────────────────────────────────────
async def got_doc_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q   = update.callback_query
    await q.answer()
    key = q.data.replace("jenis:", "")
    context.user_data["doc_type"] = key

    if key == "kegiatan":
        await q.edit_message_text(
            "✅ *Dokumentasi Kegiatan*\n\n"
            "Langkah 1 dari 4 — *Judul Kegiatan*\n"
            "Ketik judul kegiatan:",
            parse_mode="Markdown",
        )
        return INPUT_A

    elif key == "program":
        s = sess.get(update.effective_chat.id)
        s.title = ""  # judul sudah tertanam di background template
        await q.edit_message_text(
            "✅ *Program Kesehatan*\n\n"
            "Ketik nama tempat / lokasi kegiatan:",
            parse_mode="Markdown",
            reply_markup=_kb_skip("skip_loc", "Lewati (pakai default)"),
        )
        return INPUT_B

    elif key == "sppd":
        await q.edit_message_text(
            "✅ *Dokumentasi Perjalanan Dinas*\n\n"
            "Ketik *nama lengkap* pelaksana perjalanan dinas:",
            parse_mode="Markdown",
        )
        return INPUT_A

    elif key == "belasungkawa":
        await q.edit_message_text(
            "✅ *Ucapan Belasungkawa*\n\n"
            "Ketik nama almarhum / almarhumah:",
            parse_mode="Markdown",
        )
        return INPUT_A

    elif key == "ucapan":
        await q.edit_message_text(
            "✅ *Ucapan Selamat*\n\n"
            "Pilih jenis ucapan:",
            parse_mode="Markdown",
            reply_markup=_kb_sub_ucapan(),
        )
        return SUBTYPE

    elif key == "ultah":
        await q.edit_message_text(
            "✅ *Ucapan Ulang Tahun*\n\n"
            "Ketik nama yang berulang tahun:",
            parse_mode="Markdown",
        )
        return INPUT_A

    return DOC_TYPE


# ── SUBTYPE: jenis ucapan selamat ──────────────────────────────────────────────
async def got_subtype(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q   = update.callback_query
    await q.answer()
    sub = q.data.replace("sub:", "")
    prefix = SUB_UCAPAN.get(sub, "Selamat")
    context.user_data["ucapan_prefix"] = prefix

    await q.edit_message_text(
        f"✅ *{prefix}*\n\n"
        "Ketik nama penerima ucapan:",
        parse_mode="Markdown",
    )
    return INPUT_A


# ── INPUT_A: judul kegiatan / nama orang ──────────────────────────────────────
async def got_input_a(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    doc_type = context.user_data.get("doc_type", "kegiatan")
    text     = update.message.text.strip()
    s        = sess.get(chat_id)

    if doc_type == "kegiatan":
        title, matched = recognize(text)
        s.title = title
        tag = " ✨" if matched else ""
        await update.message.reply_text(
            f"Judul: *{title}*{tag}\n\n"
            "Langkah 2 dari 4 — *Lokasi*\n"
            "Ketik nama tempat kegiatan:",
            parse_mode="Markdown",
            reply_markup=_kb_skip("skip_loc", f"Lewati (pakai default)"),
        )
        return INPUT_B

    elif doc_type == "sppd":
        s.title = text
        await update.message.reply_text(
            f"Nama: *{text}*\n\n"
            "*Tujuan / Keperluan Perjalanan Dinas:*\n"
            "Ketik tujuan perjalanan:",
            parse_mode="Markdown",
        )
        return INPUT_B

    elif doc_type == "belasungkawa":
        nama = text
        s.title      = f"Turut Berduka Cita Atas Wafatnya|{nama}"
        s.event_date = date.today()
        await update.message.reply_text(
            f"Nama: *{nama}*\n\n"
            "*Jabatan / Instansi* — opsional\n"
            "Ketik jabatan atau klik Lewati:",
            parse_mode="Markdown",
            reply_markup=_kb_skip("skip_info"),
        )
        return INPUT_B

    elif doc_type == "ucapan":
        nama   = text
        prefix = context.user_data.get("ucapan_prefix", "Selamat")
        s.title      = f"{prefix}|{nama}"
        s.event_date = date.today()
        await update.message.reply_text(
            f"Nama: *{nama}*\n\n"
            "*Jabatan / Posisi Baru* — opsional\n"
            "Ketik jabatan atau klik Lewati:",
            parse_mode="Markdown",
            reply_markup=_kb_skip("skip_info"),
        )
        return INPUT_B

    elif doc_type == "ultah":
        nama = text
        s.title      = f"Selamat Ulang Tahun|{nama}"
        s.location   = ""
        s.event_date = date.today()
        await update.message.reply_text(
            f"Nama: *{nama}*\n\n"
            "Pilih template:",
            parse_mode="Markdown",
            reply_markup=_kb_template("ultah"),
        )
        return TEMPLATE_SEL

    return INPUT_A


# ── INPUT_B: lokasi (kegiatan) / jabatan (ucapan/belasungkawa) ────────────────
async def got_input_b(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    doc_type = context.user_data.get("doc_type", "kegiatan")
    text     = update.message.text.strip()
    s        = sess.get(chat_id)

    if doc_type == "sppd":
        if "sppd_tujuan" not in context.user_data:
            context.user_data["sppd_tujuan"] = text
            await update.message.reply_text(
                f"Tujuan: _{text}_\n\n"
                "*Lokasi Kegiatan* — tempat kegiatan berlangsung:\n"
                "Ketik nama lokasi / gedung / tempat:",
                parse_mode="Markdown",
            )
            return INPUT_B
        else:
            s.location = text
            await update.message.reply_text(
                f"Lokasi: _{text}_\n\n"
                "Tanggal kegiatan:",
                parse_mode="Markdown",
                reply_markup=_kb_today(),
            )
            return INPUT_C
    elif doc_type in ("kegiatan", "program"):
        s.location = text
        await update.message.reply_text(
            f"Lokasi: _{text}_\n\n"
            "Ketik tanggal kegiatan:",
            parse_mode="Markdown",
            reply_markup=_kb_today(),
        )
        return INPUT_C
    else:
        s.location = text
        await update.message.reply_text(
            f"Keterangan: _{text}_\n\n"
            "Pilih template:",
            parse_mode="Markdown",
            reply_markup=_kb_template(doc_type),
        )
        return TEMPLATE_SEL


async def skip_input_b(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q        = update.callback_query
    await q.answer()
    chat_id  = update.effective_chat.id
    doc_type = context.user_data.get("doc_type", "kegiatan")

    if doc_type in ("kegiatan", "program"):
        await q.edit_message_text(
            f"Lokasi: _{LOCATION_DEFAULT}_ (default)\n\n"
            "Ketik tanggal kegiatan:",
            parse_mode="Markdown",
            reply_markup=_kb_today(),
        )
        return INPUT_C
    else:
        sess.get(chat_id).location = ""
        await q.edit_message_text(
            "Pilih template:",
            parse_mode="Markdown",
            reply_markup=_kb_template(doc_type),
        )
        return TEMPLATE_SEL


# ── INPUT_C: tanggal (kegiatan saja) ──────────────────────────────────────────
async def got_input_c(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    doc_type = context.user_data.get("doc_type", "kegiatan")
    d = parse_date(update.message.text.strip())
    if not d:
        await update.message.reply_text(
            "Format tidak dikenali. Coba: `12 agustus` atau `12/08/2026`",
            parse_mode="Markdown",
            reply_markup=_kb_today(),
        )
        return INPUT_C
    sess.get(chat_id).event_date = d
    await update.message.reply_text(
        f"Tanggal: {_fmt(d)}\n\n"
        "Pilih Template:",
        parse_mode="Markdown",
        reply_markup=_kb_template(doc_type),
    )
    return TEMPLATE_SEL


async def today_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q        = update.callback_query
    await q.answer()
    doc_type = context.user_data.get("doc_type", "kegiatan")
    sess.get(update.effective_chat.id).event_date = date.today()
    await q.edit_message_text(
        f"Tanggal: {_fmt(date.today())}\n\n"
        "Pilih Template:",
        parse_mode="Markdown",
        reply_markup=_kb_template(doc_type),
    )
    return TEMPLATE_SEL


# ── TEMPLATE_SEL: pilih template ──────────────────────────────────────────────
async def got_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q     = update.callback_query
    await q.answer()
    key   = q.data.replace("tpl:", "")
    meta  = _load_meta()
    info  = meta.get(key, {})
    label = info.get("label", key) if isinstance(info, dict) else info
    context.user_data["template"] = key

    await q.edit_message_text(
        f"Template: *{label}*\n\n"
        "Silakan kirim foto-foto.\n"
        "Ketik /done jika sudah selesai.",
        parse_mode="Markdown",
    )
    return PHOTOS


# ── PHOTOS: upload foto ────────────────────────────────────────────────────────
async def conv_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    s        = sess.get(chat_id)

    tg_photo = update.message.photo[-1]
    file     = await tg_photo.get_file()
    buf      = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)
    s.photos.append(Image.open(buf).copy())

    n = len(s.photos)
    if n == 1:
        await update.message.reply_text(
            f"Foto ke-{n} diterima. Kirim lagi atau /done untuk generate."
        )
    elif n % 3 == 0:
        await update.message.reply_text(f"{n} foto terkumpul.")
    return PHOTOS


async def conv_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    s        = sess.get(chat_id)

    if not s.photos:
        await update.message.reply_text("Belum ada foto. Kirim minimal 1 foto dulu.")
        return PHOTOS

    template = context.user_data.get("template", "default")
    doc_type = context.user_data.get("doc_type", "kegiatan")
    if doc_type == "sppd":
        await update.message.reply_text(
            "📎 Kirim foto atau file PDF *Surat Tugas* dan *SPPD* untuk dilampirkan.\n\n"
            "• Foto langsung dari kamera → kirim sebagai foto\n"
            "• File hasil scan → kirim sebagai dokumen\n\n"
            "Ketik /selesai jika sudah semua, atau /lewati jika tidak ada lampiran.",
            parse_mode="Markdown",
        )
        return SPPD_DOCS
    await update.message.reply_text("Sedang generate dokumen...")
    await _generate_and_send(chat_id, context, update.effective_user, template=template)
    return ConversationHandler.END


async def sppd_docs_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima foto surat (kamera) di state SPPD_DOCS."""
    chat_id  = update.effective_chat.id
    tg_photo = update.message.photo[-1]
    file     = await tg_photo.get_file()
    buf      = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)
    photo = Image.open(buf).copy()
    n = await receive_scan_doc(chat_id, context, photo=photo)
    await update.message.reply_text(
        f"✅ Foto surat ke-{n} diterima.\n"
        "Kirim lagi, atau /selesai untuk generate PDF gabungan.",
    )
    return SPPD_DOCS


async def sppd_docs_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima file PDF surat di state SPPD_DOCS."""
    chat_id = update.effective_chat.id
    doc     = update.message.document
    if not doc or not doc.mime_type == "application/pdf":
        await update.message.reply_text(
            "❌ Hanya file PDF yang diterima. Kirim ulang atau /selesai."
        )
        return SPPD_DOCS
    file = await doc.get_file()
    buf  = io.BytesIO()
    await file.download_to_memory(buf)
    n = await receive_scan_doc(chat_id, context, pdf_bytes=buf.getvalue())
    await update.message.reply_text(
        f"✅ File PDF surat ke-{n} diterima.\n"
        "Kirim lagi, atau /selesai untuk generate PDF gabungan.",
    )
    return SPPD_DOCS


async def sppd_docs_selesai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generate dan kirim PDF SPPD (dengan atau tanpa scan)."""
    chat_id  = update.effective_chat.id
    template = context.user_data.get("template", "sppd_default")
    n_scan   = len(sess.get(chat_id).scan_docs)
    msg = "Sedang generate PDF" + (f" dan menggabungkan {n_scan} scan..." if n_scan else "...")
    await update.message.reply_text(msg)
    await _generate_and_send_pdf(chat_id, context, update.effective_user, template=template)
    return ConversationHandler.END


async def sppd_docs_lewati(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lewati lampiran scan, langsung generate PDF dokumentasi saja."""
    chat_id  = update.effective_chat.id
    template = context.user_data.get("template", "sppd_default")
    await update.message.reply_text("Sedang generate PDF dokumentasi...")
    await _generate_and_send_pdf(chat_id, context, update.effective_user, template=template)
    return ConversationHandler.END


async def conv_batal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    s = sess.get(chat_id)
    if s.job:
        s.job.schedule_removal()
    sess.clear(chat_id)
    context.user_data.clear()
    await update.message.reply_text("Sesi dibatalkan.")
    return ConversationHandler.END


# ── Builder ────────────────────────────────────────────────────────────────────
def build() -> ConversationHandler:
    txt = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CommandHandler("mulai", mulai)],
        states={
            DOC_TYPE: [
                CallbackQueryHandler(got_doc_type, pattern="^jenis:"),
            ],
            SUBTYPE: [
                CallbackQueryHandler(got_subtype, pattern="^sub:"),
            ],
            INPUT_A: [
                MessageHandler(txt, got_input_a),
            ],
            INPUT_B: [
                MessageHandler(txt, got_input_b),
                CallbackQueryHandler(skip_input_b, pattern="^skip_"),
            ],
            INPUT_C: [
                MessageHandler(txt, got_input_c),
                CallbackQueryHandler(today_date, pattern="^today$"),
            ],
            TEMPLATE_SEL: [
                CallbackQueryHandler(got_template, pattern="^tpl:"),
            ],
            PHOTOS: [
                MessageHandler(filters.PHOTO, conv_photo),
                CommandHandler("done", conv_done),
            ],
            SPPD_DOCS: [
                MessageHandler(filters.PHOTO, sppd_docs_photo),
                MessageHandler(filters.Document.PDF, sppd_docs_file),
                CommandHandler("selesai", sppd_docs_selesai),
                CommandHandler("lewati", sppd_docs_lewati),
            ],
        },
        fallbacks=[CommandHandler("batal", conv_batal)],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
