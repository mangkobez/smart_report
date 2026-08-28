import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.renderer.layout import get_layout


def test_layout_1():
    g = get_layout(1)
    assert g.rows == 1 and g.cols == 1 and g.wide_slots == []


def test_layout_2():
    g = get_layout(2)
    assert g.rows == 1 and g.cols == 2


def test_layout_3():
    g = get_layout(3)
    assert g.rows == 2 and g.cols == 2
    assert 0 in g.wide_slots  # top photo spans full width


def test_layout_4():
    g = get_layout(4)
    assert g.rows == 2 and g.cols == 2 and g.wide_slots == []


def test_layout_6():
    g = get_layout(6)
    assert g.rows == 3 and g.cols == 2


def test_layout_fallback_7():
    g = get_layout(7)
    assert g.cols == 2
    assert g.rows == 4
