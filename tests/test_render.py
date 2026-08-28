import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image
from src.renderer.canvas import render_doc, _load_config

_cfg = _load_config()
CANVAS_W = _cfg["canvas"]["w"]
CANVAS_H = _cfg["canvas"]["h"]


def _make_photos(n: int) -> list[Image.Image]:
    colors = [
        (200, 80, 80), (80, 160, 200), (80, 200, 120),
        (200, 160, 80), (160, 80, 200), (200, 200, 80),
    ]
    return [Image.new("RGB", (800, 600), color=colors[i % len(colors)]) for i in range(n)]


def test_render_returns_correct_size():
    photos = _make_photos(4)
    result = render_doc("Monev Keuangan", photos, date(2026, 8, 11))
    assert result.size == (CANVAS_W, CANVAS_H)


def test_render_1_photo():
    result = render_doc("Rapat UKM", _make_photos(1), date(2026, 8, 11))
    assert result.size == (CANVAS_W, CANVAS_H)


def test_render_2_photos():
    result = render_doc("Penyuluhan Hipertensi", _make_photos(2), date(2026, 8, 11))
    assert result.size == (CANVAS_W, CANVAS_H)


def test_render_3_photos():
    result = render_doc("Posyandu Sukajaya", _make_photos(3), date(2026, 8, 11))
    assert result.size == (CANVAS_W, CANVAS_H)


def test_render_6_photos():
    result = render_doc("CKG Remaja", _make_photos(6), date(2026, 8, 11))
    assert result.size == (CANVAS_W, CANVAS_H)


def test_render_saves_file(tmp_path):
    photos = _make_photos(4)
    out = tmp_path / "test_output.jpg"
    render_doc("Test Save", photos, date(2026, 8, 11), output_path=out)
    assert out.exists()
    assert out.stat().st_size > 10_000  # file tidak kosong
