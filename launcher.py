"""
SMARTREPORT PANEL KONTROL
Jalankan: klik dua kali run_launcher.vbs
"""
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

BASE_DIR     = Path(__file__).parent
LOG_ACTIVITY = BASE_DIR / "logs" / "activity.log"
VBS_BOT      = BASE_DIR / "run_bot_hidden.vbs"
EDITOR_URL   = "http://localhost:8501"
STREAMLIT    = BASE_DIR / ".venv" / "Scripts" / "streamlit.exe"

# ── Status checks ─────────────────────────────────────────────────────────────

def is_bot_running() -> bool:
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'",
             "get", "commandline", "/format:list"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return "bot.py" in r.stdout
    except Exception:
        return False


def is_editor_running() -> bool:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        ok = s.connect_ex(("127.0.0.1", 8501)) == 0
        s.close()
        return ok
    except Exception:
        return False


# ── Actions ───────────────────────────────────────────────────────────────────

def start_bot() -> None:
    if VBS_BOT.exists():
        os.startfile(str(VBS_BOT))
    else:
        subprocess.Popen(
            [str(BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"), "-u", "bot.py"],
            cwd=str(BASE_DIR),
        )


def stop_bot() -> None:
    subprocess.run(
        ["wmic", "process", "where", "name='python.exe' and commandline like '%bot.py%'",
         "delete"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def start_editor() -> None:
    log_path = BASE_DIR / "logs" / "editor.log"
    log_path.parent.mkdir(exist_ok=True)
    log = open(log_path, "w", encoding="utf-8")
    subprocess.Popen(
        [str(STREAMLIT), "run", "editor.py",
         "--server.port", "8501",
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=str(BASE_DIR),
        stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


# ── UI ────────────────────────────────────────────────────────────────────────

BG      = "#f0f4f8"
CARD_BG = "#ffffff"
BLUE    = "#1a56db"
GREEN   = "#16a34a"
RED     = "#dc2626"
GREY    = "#6b7280"
TEXT    = "#111827"
MUTED   = "#9ca3af"


def _card(parent, title: str) -> tk.Frame:
    wrap = tk.Frame(parent, bg=BG)
    wrap.pack(fill="x", padx=18, pady=(0, 10))
    tk.Label(wrap, text=title, font=("Segoe UI", 9, "bold"),
             bg=BG, fg=GREY).pack(anchor="w", pady=(0, 4))
    card = tk.Frame(wrap, bg=CARD_BG, bd=0, highlightthickness=1,
                    highlightbackground="#e2e8f0")
    card.pack(fill="x")
    return card


def _btn(parent, text, color, command, width=None) -> tk.Button:
    kw = dict(
        text=text, font=("Segoe UI", 10), bg=color, fg="white",
        relief="flat", padx=14, pady=7, cursor="hand2",
        activebackground=color, activeforeground="white",
        command=command, bd=0,
    )
    if width:
        kw["width"] = width
    b = tk.Button(parent, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_darken(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


def _darken(hex_color: str) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r, g, b = max(0, r-25), max(0, g-25), max(0, b-25)
    return f"#{r:02x}{g:02x}{b:02x}"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SmartReport")
        self.root.geometry("440x580")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self._center()
        self._build()
        self._schedule_refresh()

    def _center(self):
        self.root.update_idletasks()
        w, h = 440, 580
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self):
        # ── Header ──────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BLUE)
        hdr.pack(fill="x")
        tk.Label(hdr, text="SmartReport", font=("Segoe UI", 17, "bold"),
                 bg=BLUE, fg="white").pack(side="left", padx=20, pady=14)
        tk.Label(hdr, text="Panel Kontrol", font=("Segoe UI", 10),
                 bg=BLUE, fg="#93c5fd").pack(side="left", pady=14)

        tk.Frame(self.root, bg=BG, height=16).pack()

        # ── Bot card ─────────────────────────────────────────────────────
        bot_card = _card(self.root, "BOT TELEGRAM")
        bot_card.configure(padx=16, pady=14)

        row1 = tk.Frame(bot_card, bg=CARD_BG)
        row1.pack(fill="x", pady=(0, 12))
        tk.Label(row1, text="Status", font=("Segoe UI", 10),
                 bg=CARD_BG, fg=GREY).pack(side="left")
        self.bot_dot = tk.Label(row1, text="●", font=("Segoe UI", 15),
                                bg=CARD_BG, fg=MUTED)
        self.bot_dot.pack(side="left", padx=(10, 5))
        self.bot_lbl = tk.Label(row1, font=("Segoe UI", 10, "bold"),
                                bg=CARD_BG, fg=MUTED, text="Mengecek...")
        self.bot_lbl.pack(side="left")

        row2 = tk.Frame(bot_card, bg=CARD_BG)
        row2.pack(fill="x")
        self.btn_start = _btn(row2, "▶  Start Bot", GREEN, self._start_bot)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = _btn(row2, "■  Stop Bot", RED, self._stop_bot)
        self.btn_stop.pack(side="left")

        # ── Editor card ──────────────────────────────────────────────────
        ed_card = _card(self.root, "EDITOR TEMPLATE")
        ed_card.configure(padx=16, pady=14)

        row3 = tk.Frame(ed_card, bg=CARD_BG)
        row3.pack(fill="x", pady=(0, 12))
        tk.Label(row3, text="Status", font=("Segoe UI", 10),
                 bg=CARD_BG, fg=GREY).pack(side="left")
        self.ed_dot = tk.Label(row3, text="●", font=("Segoe UI", 15),
                               bg=CARD_BG, fg=MUTED)
        self.ed_dot.pack(side="left", padx=(10, 5))
        self.ed_lbl = tk.Label(row3, font=("Segoe UI", 10, "bold"),
                               bg=CARD_BG, fg=MUTED, text="Mengecek...")
        self.ed_lbl.pack(side="left")

        row4 = tk.Frame(ed_card, bg=CARD_BG)
        row4.pack(fill="x")
        self.btn_editor = _btn(row4, "🎨  Buka Editor", BLUE, self._open_editor)
        self.btn_editor.pack(side="left", padx=(0, 8))

        tk.Label(ed_card,
                 text="Edit template, keyword, dan pengaturan bot\ntanpa perlu ubah kode.",
                 font=("Segoe UI", 9), bg=CARD_BG, fg=MUTED, justify="left"
                 ).pack(anchor="w", pady=(10, 0))

        # ── Log card ─────────────────────────────────────────────────────
        log_card = _card(self.root, "AKTIVITAS TERAKHIR")
        log_card.configure(padx=0, pady=0)

        self.log_box = tk.Text(
            log_card, height=8, font=("Consolas", 9),
            bg="#1e293b", fg="#94a3b8", relief="flat",
            state="disabled", wrap="none",
            padx=12, pady=10,
            insertbackground="#94a3b8",
        )
        self.log_box.pack(fill="both")

        # ── Footer ───────────────────────────────────────────────────────
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=18, pady=(6, 16))
        tk.Button(
            foot, text="🔄  Refresh", font=("Segoe UI", 9),
            bg="#e2e8f0", fg=TEXT, relief="flat", padx=10, pady=4,
            cursor="hand2", bd=0,
            command=self._refresh,
        ).pack(side="left")
        self.time_lbl = tk.Label(foot, font=("Segoe UI", 8), bg=BG, fg=MUTED)
        self.time_lbl.pack(side="right")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _refresh(self):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        bot_ok = is_bot_running()
        ed_ok  = is_editor_running()
        self.root.after(0, self._apply_status, bot_ok, ed_ok)
        self.root.after(0, self._load_log)

    def _apply_status(self, bot_ok: bool, ed_ok: bool):
        import datetime
        self.time_lbl.config(
            text=f"Terakhir: {datetime.datetime.now().strftime('%H:%M:%S')}"
        )

        if bot_ok:
            self.bot_dot.config(fg=GREEN)
            self.bot_lbl.config(text="Berjalan", fg=GREEN)
            self.btn_start.config(state="disabled", bg="#86efac")
            self.btn_stop.config(state="normal", bg=RED)
        else:
            self.bot_dot.config(fg=RED)
            self.bot_lbl.config(text="Tidak aktif", fg=RED)
            self.btn_start.config(state="normal", bg=GREEN)
            self.btn_stop.config(state="disabled", bg="#fca5a5")

        if ed_ok:
            self.ed_dot.config(fg=GREEN)
            self.ed_lbl.config(text="Berjalan — port 8501", fg=GREEN)
        else:
            self.ed_dot.config(fg=MUTED)
            self.ed_lbl.config(text="Belum dijalankan", fg=MUTED)

    def _load_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", tk.END)
        if LOG_ACTIVITY.exists():
            lines = LOG_ACTIVITY.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-10:]:
                self.log_box.insert(tk.END, line + "\n")
        else:
            self.log_box.insert(tk.END, "(belum ada aktivitas tercatat)")
        self.log_box.config(state="disabled")
        self.log_box.see(tk.END)

    def _schedule_refresh(self):
        self._refresh()
        self.root.after(5000, self._schedule_refresh)

    # ── Button actions ────────────────────────────────────────────────────────

    def _start_bot(self):
        start_bot()
        self.root.after(2500, self._refresh)

    def _stop_bot(self):
        if messagebox.askyesno("Konfirmasi", "Hentikan bot Telegram sekarang?",
                               icon="warning"):
            stop_bot()
            self.root.after(1500, self._refresh)

    def _open_editor(self):
        def _task():
            if not is_editor_running():
                start_editor()
                import time
                # Tunggu sampai port 8501 benar-benar listen (maks 15 detik)
                for _ in range(15):
                    time.sleep(1)
                    if is_editor_running():
                        break
            webbrowser.open(EDITOR_URL)
            self.root.after(500, self._refresh)

        threading.Thread(target=_task, daemon=True).start()
        self.ed_lbl.config(text="Memulai...", fg="#d97706")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
