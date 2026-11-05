"""Icons for the GUI, drawn for this project and shipped as SVG files.

Step and choice icons are 24 px line drawings whose outlines use
``currentColor``. Qt's SVG renderer does not resolve ``currentColor``, so
:func:`icon` substitutes a colour (by default the palette's text colour)
before rendering. Call it again after a palette change to follow light and
dark mode. The laser beam is drawn in a fixed red in every icon.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

#: Sizes (px) pre-rendered into each QIcon; the larger ones serve high-DPI screens.
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96)
APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


@cache
def svg_text(name: str) -> str:
    """Return the SVG source of icon ``name`` (file name without ``.svg``)."""
    return (files(__package__) / "icons" / f"{name}.svg").read_text(encoding="utf-8")


def icon_names() -> list[str]:
    """Names of all bundled icons."""
    return sorted(p.name[:-4] for p in (files(__package__) / "icons").iterdir()
                  if p.name.endswith(".svg"))


def _text_color() -> QColor:
    app = QGuiApplication.instance()
    if app is None:
        return QColor("#17202e")
    return app.palette().color(QPalette.ColorRole.WindowText)


def render(name: str, size: int, color: QColor | str | None = None) -> QImage:
    """Render icon ``name`` to a transparent ``size`` × ``size`` image."""
    color = QColor(color) if color is not None else _text_color()
    svg = svg_text(name).replace("currentColor", color.name())
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def icon(name: str, color: QColor | str | None = None) -> QIcon:
    """A :class:`QIcon` for ``name`` with outlines in ``color`` (default: text colour)."""
    sizes = APP_ICON_SIZES if name == "app" else ICON_SIZES
    result = QIcon()
    for size in sizes:
        result.addPixmap(QPixmap.fromImage(render(name, size, color)))
    return result


def app_icon() -> QIcon:
    """The application icon (window title bar, taskbar, dock)."""
    return icon("app")


def save_png(name: str, path: str | Path, size: int = 512) -> Path:
    """Render icon ``name`` to a PNG file, e.g. the 512 px app icon."""
    path = Path(path)
    if not render(name, size).save(str(path), "PNG"):
        raise OSError(f"could not write {path}")
    return path
