"""Regenerate the GUI screenshots used in docs/gui.md.

Run headless with ``QT_QPA_PLATFORM=offscreen python tools/gui_screenshots.py``.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from laserdesign.gui import presets  # noqa: E402
from laserdesign.gui.main_window import MainWindow  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "gui" / "images"

SHOTS = [
    ("cw_nd_yvo4", 0, "step1_gain_medium.png"),
    ("cw_nd_yvo4", 1, "step2_pump.png"),
    ("modelocked_nd_yvo4", 2, "step3_resonator.png"),
    ("qswitched_nd_yag", 3, "step4_operation.png"),
    ("cw_nd_yvo4", 4, "step5_results_cw.png"),
    ("qswitched_nd_yag", 4, "step5_results_qswitch.png"),
    ("modelocked_nd_yvo4", 4, "step5_results_modelock.png"),
    ("side_pumped_nd_yag", 1, "step2_pump_side.png"),
    ("ring_nd_yvo4", 2, "step3_resonator_ring.png"),
    ("passive_nd_yag_cr_yag", 3, "step4_operation_passive.png"),
    ("passive_nd_yag_cr_yag", 4, "step5_results_passive.png"),
    ("klm_ti_sapphire", 4, "step5_results_klm.png"),
]


def main():
    app = QApplication.instance() or QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    win = MainWindow()
    win.show()
    for preset, step, filename in SHOTS:
        win.load_spec(getattr(presets, preset)())
        win.go(step)
        app.processEvents()
        win.refresh()
        app.processEvents()
        win.grab().save(str(OUT / filename))
        print("wrote", OUT / filename)


if __name__ == "__main__":
    main()
