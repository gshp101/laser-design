"""Entry point: ``laserdesign-gui`` or ``python -m laserdesign.gui``."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Start the GUI. An optional argument is a design file to open."""
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    argv = sys.argv if argv is None else argv
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("laserdesign")
    win = MainWindow()
    if len(argv) > 1:
        win.open_path(Path(argv[1]))
    win.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
