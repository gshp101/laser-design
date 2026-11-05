"""The bundled GUI icons load, render and follow the palette colour."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtSvg")

from laserdesign.gui import icons
from laserdesign.gui.pages import ALL_PAGES, MODE_KEYS


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def expected_names():
    names = {"app", "pump-end", "pump-side", "cavity-standing", "cavity-ring"}
    names |= {page.icon_name for page in ALL_PAGES}
    names |= {f"mode-{k}" for k in MODE_KEYS}
    return names


def test_every_used_icon_is_bundled():
    assert expected_names() <= set(icons.icon_names())


@pytest.mark.parametrize("name", sorted(expected_names()))
def test_icon_renders(app, name):
    image = icons.render(name, 48)
    opaque = sum(image.pixelColor(x, y).alpha() > 0 for x in range(48) for y in range(48))
    assert opaque > 40
    assert not icons.icon(name).isNull()


def test_outline_follows_colour(app):
    def has(image, rgb):
        return any(image.pixelColor(x, y).alpha() == 255 and
                   (image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                    image.pixelColor(x, y).blue()) == rgb
                   for x in range(96) for y in range(96))
    assert has(icons.render("step-resonator", 96, "#00ff00"), (0, 255, 0))
    assert not has(icons.render("step-resonator", 96, "#0000ff"), (0, 255, 0))


def test_save_png(app, tmp_path):
    path = icons.save_png("app", tmp_path / "icon.png", 512)
    from PySide6.QtGui import QImage
    image = QImage(str(path))
    assert (image.width(), image.height()) == (512, 512)


def test_window_has_icons(app):
    from laserdesign.gui.main_window import MainWindow
    w = MainWindow()
    try:
        assert not w.windowIcon().isNull()
        assert all(not w.steps.item(i).icon().isNull() for i in range(w.steps.count()))
        assert w.pages[0].header_icon.pixmap() is not None
    finally:
        w.close()
