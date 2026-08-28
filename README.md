# SMARTREPORT AUTO
Sistem dokumentasi otomatis UPTD Puskesmas Cipatujah via Telegram bot.

Kirim foto ke bot → generate dokumentasi JPG siap upload Instagram — otomatis.

---

## Setup

### 1. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Konfigurasi `.env`
Salin `.env.example` menjadi `.env` lalu isi:
```
TELEGRAM_TOKEN=token_dari_botfather
LOCATION_DEFAULT=UPTD Puskesmas Cipatujah
BATCH_TIMEOUT=30
```

### 3. Jalankan bot
```bash
.venv\Scripts\python bot.py
```

---

## Cara Pakai

### Format caption foto pertama
```
judul, lokasi, tanggal
```
Lokasi dan tanggal **opsional** — urutan bebas.

**Contoh:**
| Caption | Hasil |
|---|---|
| `apel pagi` | Judul otomatis, lokasi & tanggal default |
| `posyandu balita, Posyandu Sukajaya` | + lokasi custom |
| `rapat ukm, Aula Puskesmas, 12 agustus` | + lokasi + tanggal |
| `monev keuangan, 10/08/2026` | + tanggal (format angka) |

### Format tanggal yang didukung
- `12 agustus` atau `12 agustus 2026`
- `12/08` atau `12/08/2026`
- `12-08-2026`

### Perintah bot
| Perintah | Fungsi |
|---|---|
| `/done` | Generate dokumentasi sekarang |
| `/batal` | Batalkan sesi |
| `/lokasi Aula Puskesmas` | Ubah lokasi setelah foto dikirim |
| `/tanggal 12 agustus` | Ubah tanggal setelah foto dikirim |

### Pemisah judul `\|`
Untuk judul panjang, gunakan `|` untuk paksa ganti baris:
```
Monitoring dan Evaluasi Keuangan|Dinas Kesehatan
```

---

## Keyword Otomatis
Bot mengenali kata kunci umum dan mengubahnya jadi judul standar (✨).
Daftar lengkap & cara tambah: [`assets/keywords.json`](assets/keywords.json)

**Contoh:**
| Input | Judul |
|---|---|
| `apel` | Apel Pagi |
| `posyandu balita` | Posyandu Balita |
| `monev keuangan` | Monitoring dan Evaluasi Keuangan\|Dinas Kesehatan |
| `lokmin` | Lokakarya Mini |
| `penyuluhan` | Penyuluhan Kesehatan |

---

## Generate Manual (CLI)
```bash
.venv\Scripts\python generate.py \
  --folder ./foto \
  --title "Apel Pagi" \
  --date 2026-08-12 \
  --location "Halaman UPTD Puskesmas Cipatujah" \
  --out ./output/hasil.jpg
```

---

## Struktur Folder
```
SmartReport/
├── bot.py                  # Entry point Telegram bot
├── generate.py             # CLI manual
├── assets/
│   ├── keywords.json       # Daftar keyword → judul standar
│   ├── fonts/              # Font Noto Sans (opsional)
│   └── templates/
│       └── default/
│           ├── background.png   # Template desain (1080×1350)
│           └── config.json      # Koordinat zona foto & teks
├── src/
│   ├── bot/
│   │   ├── handlers.py     # Handler Telegram
│   │   ├── session.py      # Manajemen sesi per chat
│   │   ├── recognizer.py   # Pencocokan keyword
│   │   └── parser.py       # Parse judul/lokasi/tanggal
│   └── renderer/
│       ├── canvas.py       # Generate gambar
│       ├── photo.py        # Load & crop foto
│       └── layout.py       # Layout grid foto
└── tests/                  # Unit tests
```

---

## Output
- Ukuran: **1080×1350px** (Instagram portrait 4:5)
- Format: JPEG, quality 92
- Template: teal branding UPTD Puskesmas Cipatujah
