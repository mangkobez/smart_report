from pathlib import Path
from PIL import Image, ImageOps, ExifTags


SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# EXIF orientation tag value → degrees to rotate
_EXIF_ROTATION = {3: 180, 6: 270, 8: 90}


def _fix_orientation(img: Image.Image) -> Image.Image:
    """Rotate image to match EXIF orientation tag."""
    try:
        exif = img.getexif()
        orientation_tag = next(
            k for k, v in ExifTags.TAGS.items() if v == "Orientation"
        )
        orientation = exif.get(orientation_tag)
        if orientation in _EXIF_ROTATION:
            img = img.rotate(_EXIF_ROTATION[orientation], expand=True)
    except (AttributeError, StopIteration, Exception):
        pass
    return img


def load_photos(folder: str | Path) -> list[Image.Image]:
    """Load all supported images from folder, sorted by filename."""
    folder = Path(folder)
    paths = sorted(
        p for p in folder.iterdir()
        if p.suffix.lower() in SUPPORTED_EXT
    )
    images = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img = _fix_orientation(img)
        images.append(img)
    return images


def select_best(photos: list[Image.Image], max_n: int = 9) -> list[Image.Image]:
    """
    Dari banyak foto, pilih max_n yang paling landscape (lebar > tinggi).
    Foto landscape diprioritaskan karena lebih cocok untuk kolase dokumentasi.
    """
    if len(photos) <= max_n:
        return photos
    # Urutkan: landscape (rasio besar) duluan
    ranked = sorted(photos, key=lambda p: p.width / p.height, reverse=True)
    return ranked[:max_n]


def smart_crop(img: Image.Image, slot_w: int, slot_h: int) -> Image.Image:
    """
    Resize and center-crop image to fit slot dimensions exactly.
    Maintains aspect ratio — no stretching.
    """
    src_w, src_h = img.size
    scale = max(slot_w / src_w, slot_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - slot_w) // 2
    top = (new_h - slot_h) // 2
    img = img.crop((left, top, left + slot_w, top + slot_h))
    return img
