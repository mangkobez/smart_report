"""
Pencocokan judul otomatis dari input user.

Aturan:
- Case-insensitive
- Keyword lebih panjang dicek lebih dulu (sudah urut di JSON)
- Kembalikan title standar jika cocok, atau input asli jika tidak ada match
"""
import json
from pathlib import Path

_KEYWORDS_PATH = Path(__file__).parent.parent.parent / "assets" / "keywords.json"
_rules: list[dict] = []


def _load() -> None:
    global _rules
    with open(_KEYWORDS_PATH, encoding="utf-8") as f:
        _rules = json.load(f)


def recognize(text: str) -> tuple[str, bool]:
    """
    Kembalikan (judul, matched).
    - judul: title standar jika ada match, else text asli
    - matched: True jika ada keyword yang cocok

    Keyword hanya override jika mencakup >=50% kata dari input,
    sehingga judul panjang yang kebetulan mengandung satu keyword tidak ditimpa.
    """
    if not _rules:
        _load()

    normalized   = text.lower().strip()
    input_words  = len(normalized.split())

    for rule in _rules:
        for kw in rule["keywords"]:
            if kw in normalized:
                kw_words = len(kw.split())
                if kw_words * 2 >= input_words:
                    return rule["title"], True

    return text.strip(), False
