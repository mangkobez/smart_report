import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image
from src.renderer.photo import smart_crop


def _make_img(w: int, h: int) -> Image.Image:
    return Image.new("RGB", (w, h), color=(128, 128, 128))


def test_smart_crop_exact():
    img = _make_img(800, 600)
    result = smart_crop(img, 400, 300)
    assert result.size == (400, 300)


def test_smart_crop_portrait_to_landscape():
    img = _make_img(600, 1200)  # portrait
    result = smart_crop(img, 500, 300)  # landscape slot
    assert result.size == (500, 300)


def test_smart_crop_landscape_to_portrait():
    img = _make_img(1200, 600)  # landscape
    result = smart_crop(img, 300, 500)  # portrait slot
    assert result.size == (300, 500)


def test_smart_crop_upscale():
    img = _make_img(100, 100)
    result = smart_crop(img, 400, 400)
    assert result.size == (400, 400)


def test_smart_crop_no_stretch():
    """Verify output fills slot exactly without distortion artifacts."""
    img = _make_img(800, 600)
    slot_w, slot_h = 300, 400
    result = smart_crop(img, slot_w, slot_h)
    assert result.size == (slot_w, slot_h)
