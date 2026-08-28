from dataclasses import dataclass


@dataclass
class GridConfig:
    rows: int
    cols: int
    # slot indices that are "wide" (span 2 cols), used for odd-count layouts
    wide_slots: list[int]


def get_layout(n_photos: int) -> GridConfig:
    """Return grid config based on photo count."""
    layouts = {
        1: GridConfig(rows=1, cols=1, wide_slots=[]),
        2: GridConfig(rows=1, cols=2, wide_slots=[]),
        3: GridConfig(rows=2, cols=2, wide_slots=[0]),   # top photo spans full width
        4: GridConfig(rows=2, cols=2, wide_slots=[]),
        5: GridConfig(rows=3, cols=2, wide_slots=[0, 1]),  # 2 wide + 3 normal
        6: GridConfig(rows=3, cols=2, wide_slots=[]),
    }
    if n_photos in layouts:
        return layouts[n_photos]
    # fallback: 2-column grid, last row may be incomplete
    rows = (n_photos + 1) // 2
    return GridConfig(rows=rows, cols=2, wide_slots=[])
