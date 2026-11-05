"""Regenerate app-icon.png (512 × 512) in the repository root from the bundled SVG.

Run headless with ``QT_QPA_PLATFORM=offscreen python tools/render_app_icon.py``.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from laserdesign.gui import icons

OUT = Path(__file__).resolve().parent.parent / "app-icon.png"

if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    print(icons.save_png("app", OUT, 512))
