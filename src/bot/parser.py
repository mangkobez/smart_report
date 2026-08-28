"""
Parse input user menjadi komponen: title_raw, location, event_date.
Format: "judul, lokasi, tanggal"  (urutan lokasi & tanggal bebas)
"""
import re
from datetime import date

BULAN = {
    "januari": 1,  "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3,    "mar": 3,
    "april": 4,    "apr": 4,
    "mei": 5,
    "juni": 6,     "jun": 6,
    "juli": 7,     "jul": 7,
    "agustus": 8,  "agt": 8,  "aug": 8,
    "september": 9,"sep": 9,  "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10,
    "november": 11,"nov": 11,
    "desember": 12,"des": 12, "dec": 12,
}

HARI = {
    "senin", "selasa", "rabu", "kamis", "jumat", "jum'at", "sabtu", "minggu",
}

HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _strip_hari(t: str) -> str:
    """Hapus prefix nama hari (opsional koma/spasi) dari string tanggal."""
    for hari in HARI:
        if t.startswith(hari):
            rest = t[len(hari):].lstrip(" ,")
            if rest:
                return rest
    return t


def parse_date(text: str) -> date | None:
    t     = _strip_hari(text.lower().strip())
    today = date.today()

    # "12 agustus 2026" atau "12 agustus"
    m = re.match(r"^(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?$", t)
    if m:
        month = BULAN.get(m.group(2))
        if month:
            try:
                return date(int(m.group(3) or today.year), month, int(m.group(1)))
            except ValueError:
                pass

    # "12/08/2026", "12/8", "12-08-2026"
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{4}))?$", t)
    if m:
        try:
            return date(int(m.group(3) or today.year), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    return None


def fmt_date(d: date) -> str:
    """Format tanggal lengkap dengan nama hari: Senin, 12 Agustus 2026."""
    bulan_nama = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    return f"{HARI_ID[d.weekday()]}, {d.day} {bulan_nama[d.month]} {d.year}"


def parse_input(raw: str) -> tuple[str, str | None, date | None]:
    """
    Kembalikan (title_raw, location, event_date).
    Bagian pertama selalu dianggap judul.
    Bagian selanjutnya: dicoba parse sebagai tanggal dulu, sisanya = lokasi.
    """
    parts = [p.strip() for p in re.split(r"[,\n]", raw) if p.strip()]
    if not parts:
        return raw.strip(), None, None

    title_raw  = parts[0]
    location   = None
    event_date = None

    for part in parts[1:]:
        d = parse_date(part)
        if d:
            event_date = d
        elif location is None:
            location = part

    return title_raw, location, event_date
