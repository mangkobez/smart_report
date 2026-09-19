import io
import os
import sys
import subprocess
from datetime import date, datetime
from pathlib import Path

from PIL import Image
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from . import session as sess
from .recognizer import recognize
from .parser import parse_input, parse_date, fmt_date
from src.renderer.canvas import render_doc, render_apel
from src.renderer.photo import select_best
from src.renderer.pdf_doc import render_sppd_pdf, photo_to_pdf_bytes, merge_pdfs

LOCATION_DEFAULT = os.getenv("LOCATION_DEFAULT", "UPTD Puskesmas Cipatujah")
BATCH_TIMEOUT    = int(os.getenv("BATCH_TIMEOUT", "30"))
MAX_PHOTOS       = int(os.getenv("MAX_PHOTOS", "9"))
ADMIN_CHAT_ID    = os.getenv("ADMIN_CHAT_ID", "")

_LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "activity.log"

_KB_EDIT = InlineKeyboardMarkup([[InlineKeyboardButton("✏️  Edit", callback_data="edit_menu")]])


def _log_activity(user, title: str, n_photos: int) -> None:
    name     = user.full_name or "?"
    username = f"@{user.username}" if user.username else f"id:{user.id}"
    waktu    = datetime.now().strftime("%Y-%m-%d %H:%M")
    line     = f"{waktu} | {name} ({username}) | {title} | {n_photos} foto\n"
    _LOG_FILE.parent.mkdir(exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _fmt_date(d: date) -> str:
    return fmt_date(d)


def _apply_parsed(s: sess.Session, raw: str) -> tuple[bool, str]:
    """Parse raw input, isi session, kembalikan (matched, ringkasan)."""
    title_raw, location, event_date = parse_input(raw)
    title, matched = recognize(title_raw)

    s.title = title
    if location:
        s.location = location
    if event_date:
        s.event_date = event_date

    parts = [f"Judul: *{title}*" + (" ✨" if matched else "")]
    if location:
        parts.append(f"Lokasi: _{location}_")
    if event_date:
        parts.append(f"Tanggal: {_fmt_date(event_date)}")

    return matched, "\n".join(parts)


async def _generate_and_send(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                             user=None, template: str = "default") -> None:
    s = sess.get(chat_id)
    if not s.photos:
        return

    title    = s.title or "Dokumentasi Kegiatan"
    # None = belum diset → pakai default. "" = sengaja dikosongkan (kartu ucapan)
    location = s.location if s.location is not None else LOCATION_DEFAULT
    photos   = select_best(s.photos, MAX_PHOTOS)

    # Catat ke log
    if user:
        _log_activity(user, title, len(photos))

    # Notifikasi admin
    if ADMIN_CHAT_ID and user and str(chat_id) != ADMIN_CHAT_ID:
        name     = user.full_name or "?"
        username = f"@{user.username}" if user.username else f"id:{user.id}"
        waktu    = datetime.now().strftime("%H:%M")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"Dok baru dari {name} ({username}) pukul {waktu}:\n*{title}* — {len(photos)} foto",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

    img = render_doc(
        title=title,
        photos=photos,
        event_date=s.event_date,
        location=location,
        template=template,
    )

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    buf.seek(0)
    buf.name = "dokumentasi.jpg"

    context.user_data["last_gen"] = {
        "doc_type":   context.user_data.get("doc_type", "kegiatan"),
        "template":   template,
        "title":      title,
        "location":   location,
        "event_date": s.event_date,
        "photos":     list(s.photos),
    }
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=buf,
        caption=f"✅ *{title}*\n_{location}_",
        parse_mode="Markdown",
        reply_markup=_KB_EDIT,
    )
    sess.clear(chat_id)


async def _generate_and_send_pdf(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                                 user=None, template: str = "sppd_default") -> None:
    """Generate PDF dokumentasi SPPD dan kirim sebagai dokumen."""
    import json
    from pathlib import Path
    s      = sess.get(chat_id)
    photos = select_best(s.photos, MAX_PHOTOS)

    # Load PDF config — prioritas pdf_config.json, fallback config.json
    tpl_dir  = Path(__file__).parent.parent.parent / "assets" / "templates" / template
    cfg_path = tpl_dir / "pdf_config.json"
    if not cfg_path.exists():
        cfg_path = tpl_dir / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if user:
        _log_activity(user, s.title or "SPPD", len(photos))

    await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")

    tujuan = context.user_data.get("sppd_tujuan") or s.location or "—"
    lokasi = s.location or "—"

    buf = render_sppd_pdf(
        nama=s.title or "—",
        tujuan=tujuan,
        lokasi=lokasi,
        event_date=s.event_date,
        photos=photos,
        cfg=cfg,
        template_dir=tpl_dir,
    )
    # Merge dengan scan surat jika ada
    if s.scan_docs:
        buf = merge_pdfs(s.scan_docs, buf)
        filename = "sppd_lengkap.pdf"
        caption  = f"📄 *SPPD Lengkap* ({len(s.scan_docs)} scan + dokumentasi)\n_{s.title}_"
    else:
        filename = "dokumentasi_sppd.pdf"
        caption  = f"📄 *Dokumentasi Perjalanan Dinas*\n_{s.title}_"

    buf.name = filename
    await context.bot.send_document(
        chat_id=chat_id,
        document=buf,
        filename=filename,
        caption=caption,
        parse_mode="Markdown",
    )
    sess.clear(chat_id)


async def _generate_and_send_apel(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                                   user=None) -> None:
    s = sess.get(chat_id)
    template = context.user_data.get("template", "apel_default")

    if user:
        _log_activity(user, s.title or "Apel Pagi", len(s.photos))

    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")

    img = render_apel(
        title=s.title or "Morning Briefing",
        photos=s.photos,
        event_date=s.event_date,
        location=s.location,
        quote=s.quote,
        bg_idx=s.bg_photo_idx,
        template=template,
    )
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    buf.seek(0)
    buf.name = "apel_pagi.jpg"

    context.user_data["last_gen"] = {
        "doc_type":    "apel",
        "template":    template,
        "title":       s.title or "Morning Briefing",
        "location":    s.location,
        "event_date":  s.event_date,
        "quote":       s.quote,
        "bg_photo_idx": s.bg_photo_idx,
        "photos":      list(s.photos),
    }
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=buf,
        caption=f"✅ *{s.title or 'Apel Pagi'}*",
        parse_mode="Markdown",
        reply_markup=_KB_EDIT,
    )
    sess.clear(chat_id)


async def receive_scan_doc(chat_id: int, context,
                           photo=None, pdf_bytes: bytes = None) -> int:
    """Terima satu scan (foto atau PDF bytes), simpan ke session. Return jumlah scan."""
    s = sess.get(chat_id)
    if photo is not None:
        pdf = photo_to_pdf_bytes(photo)
        s.scan_docs.append(pdf)
    elif pdf_bytes is not None:
        s.scan_docs.append(pdf_bytes)
    return len(s.scan_docs)


async def _reset_timer(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user=None) -> None:
    s = sess.get(chat_id)
    if s.job:
        s.job.schedule_removal()
    s.job = context.job_queue.run_once(
        _on_timeout, BATCH_TIMEOUT, chat_id=chat_id, data=(chat_id, user)
    )


async def _on_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, user = context.job.data
    await _generate_and_send(chat_id, context, user)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _is_group(update: Update) -> bool:
    return update.effective_chat.type in (Chat.GROUP, Chat.SUPERGROUP)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_group(update):
        await update.message.reply_text(
            "Bot aktif di grup ini.\n"
            "Gunakan `/mulai judul, lokasi, tanggal` lalu kirim foto.\n"
            "Atau kirim foto langsung dengan caption sebagai judul.\n"
            "Ketik /done untuk generate.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "Halo! Kirim foto kegiatan dengan caption:\n"
            "*judul, lokasi, tanggal*\n\n"
            "Contoh caption:\n"
            "• `apel pagi`\n"
            "• `posyandu balita, Posyandu Sukajaya`\n"
            "• `rapat ukm, Aula Puskesmas, 12 agustus`\n\n"
            "Perintah:\n"
            "• /done — generate sekarang\n"
            "• /mulai — mulai sesi baru\n"
            "• /lokasi — ubah lokasi\n"
            "• /tanggal — ubah tanggal\n"
            "• /batal — batalkan sesi",
            parse_mode="Markdown",
        )


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id  = update.effective_chat.id
    s        = sess.get(chat_id)
    in_group = _is_group(update)

    caption = update.message.caption
    info    = ""
    if caption and not s.title:
        _, info = _apply_parsed(s, caption)

    # Download foto resolusi tertinggi
    tg_photo = update.message.photo[-1]
    file     = await tg_photo.get_file()
    buf      = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)
    s.photos.append(Image.open(buf).copy())

    n = len(s.photos)
    if in_group:
        # Di grup: ringkas — hanya reply foto pertama atau setiap kelipatan 3
        if n == 1:
            msg = info if info else f"Sesi dimulai. Kirim foto lainnya atau /done."
            await update.message.reply_text(msg, parse_mode="Markdown")
        elif n % 3 == 0:
            await update.message.reply_text(f"📸 {n} foto terkumpul.", parse_mode="Markdown")
    else:
        lines = [f"📸 Foto ke-{n} diterima"]
        if info:
            lines.append(info)
        lines.append(f"Tunggu {BATCH_TIMEOUT}s atau /done untuk generate.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    await _reset_timer(chat_id, context, update.effective_user)


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_group(update):
        return  # di grup hanya merespon perintah (/mulai, /done, dll.) dan foto
    chat_id = update.effective_chat.id
    s       = sess.get(chat_id)
    text    = update.message.text.strip()

    if not s.title:
        _, info = _apply_parsed(s, text)
        reply  = f"📝 {info}"
        reply += "\nKirim foto-fotonya." if not s.photos else "\nKetik /done untuk generate."
        await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Sesi aktif — judul: *{s.title}*\nKirim foto atau /done.",
            parse_mode="Markdown",
        )


async def cmd_mulai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    s       = sess.get(chat_id)

    # Reset sesi yang ada
    if s.job:
        s.job.schedule_removal()
    sess.clear(chat_id)
    s = sess.get(chat_id)

    raw = " ".join(context.args).strip() if context.args else ""
    if raw:
        _, info = _apply_parsed(s, raw)
        await update.message.reply_text(
            f"Sesi dimulai.\n{info}\nSekarang kirim foto-fotonya.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "Sesi dimulai. Kirim foto dengan caption sebagai judul,\n"
            "atau ketik `/mulai judul, lokasi, tanggal`.",
            parse_mode="Markdown",
        )


async def cmd_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args    = " ".join(context.args).strip() if context.args else ""
    if not args:
        await update.message.reply_text("Contoh: `/lokasi Aula Puskesmas Cipatujah`", parse_mode="Markdown")
        return
    sess.get(chat_id).location = args
    await update.message.reply_text(f"📍 Lokasi diset: _{args}_", parse_mode="Markdown")


async def cmd_tanggal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args    = " ".join(context.args).strip() if context.args else ""
    if not args:
        await update.message.reply_text("Contoh: `/tanggal 12 agustus` atau `/tanggal 12/08/2026`", parse_mode="Markdown")
        return
    d = parse_date(args)
    if not d:
        await update.message.reply_text("❌ Format tanggal tidak dikenali. Coba: `12 agustus` atau `12/08/2026`", parse_mode="Markdown")
        return
    sess.get(chat_id).event_date = d
    await update.message.reply_text(f"📅 Tanggal diset: {_fmt_date(d)}", parse_mode="Markdown")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not sess.has_photos(chat_id):
        await update.message.reply_text("❌ Belum ada foto dalam sesi ini.")
        return
    s = sess.get(chat_id)
    if s.job:
        s.job.schedule_removal()
    await update.message.reply_text("⏳ Sedang generate dokumentasi...")
    await _generate_and_send(chat_id, context, update.effective_user)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chat ID kamu: `{update.effective_chat.id}`",
                                    parse_mode="Markdown")


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN_CHAT_ID and str(update.effective_chat.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("Perintah ini hanya untuk admin.")
        return
    if not _LOG_FILE.exists():
        await update.message.reply_text("Belum ada aktivitas tercatat.")
        return
    lines = _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    last  = lines[-20:]  # 20 aktivitas terakhir
    await update.message.reply_text(
        "Aktivitas terakhir:\n\n" + "\n".join(last),
        parse_mode=None,
    )


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin only: git pull lalu restart bot otomatis."""
    if ADMIN_CHAT_ID and str(update.effective_chat.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Perintah ini hanya untuk admin.")
        return

    await update.message.reply_text("⏳ Menjalankan `git pull`...", parse_mode="Markdown")

    base_dir = Path(__file__).parent.parent.parent
    try:
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True, timeout=30,
            cwd=str(base_dir),
        )
        output = (result.stdout + result.stderr).strip() or "(tidak ada output)"
        if result.returncode == 0:
            await update.message.reply_text(
                f"✅ *Update berhasil*\n```\n{output[:500]}\n```\n\nBot restart dalam 3 detik...",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"❌ *Git pull gagal*\n```\n{output[:500]}\n```",
                parse_mode="Markdown",
            )
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return

    import asyncio
    await asyncio.sleep(3)

    subprocess.Popen(
        [sys.executable, "-u", "bot.py"],
        cwd=str(base_dir),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os._exit(0)


async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    s       = sess.get(chat_id)
    if s.job:
        s.job.schedule_removal()
    sess.clear(chat_id)
    await update.message.reply_text("Sesi dibatalkan.")
