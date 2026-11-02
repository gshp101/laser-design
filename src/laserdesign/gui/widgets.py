"""Small reusable Qt widgets: unit-aware spin boxes and a matplotlib canvas."""

from __future__ import annotations

import math

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QSizePolicy,
                               QWidget)


class UnitSpin(QDoubleSpinBox):
    """A spin box that shows a value in display units but stores SI.

    ``scale`` is the size of one display unit in SI, e.g. ``1e-3`` for mm.
    """

    def __init__(self, value: float = 0.0, scale: float = 1.0, suffix: str = "",
                 minimum: float = 0.0, maximum: float = 1e6, decimals: int = 3,
                 step: float = 1.0, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.scale = scale
        self.setDecimals(decimals)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setKeyboardTracking(False)
        self.setAlignment(Qt.AlignRight)
        if tooltip:
            self.setToolTip(tooltip)
        self.set_si(value)

    def si(self) -> float:
        """Current value in SI units."""
        return self.value() * self.scale

    def set_si(self, value: float) -> None:
        self.blockSignals(True)
        self.setValue(value / self.scale)
        self.blockSignals(False)


class RadiusInput(QWidget):
    """Mirror radius input with a 'flat' checkbox (R = inf)."""

    changed = Signal()

    def __init__(self, value: float = math.inf, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.flat = QCheckBox("flat")
        self.spin = UnitSpin(100e-3, 1e-3, "mm", minimum=-1e5, maximum=1e5, decimals=1,
                             step=10, tooltip="Radius of curvature; positive = concave")
        lay.addWidget(self.spin, 1)
        lay.addWidget(self.flat)
        self.flat.toggled.connect(self._toggle)
        self.spin.valueChanged.connect(lambda _: self.changed.emit())
        self.set_si(value)

    def _toggle(self, checked: bool) -> None:
        self.spin.setEnabled(not checked)
        self.changed.emit()

    def si(self) -> float:
        return math.inf if self.flat.isChecked() else self.spin.si()

    def set_si(self, value: float) -> None:
        self.flat.blockSignals(True)
        flat = not math.isfinite(value)
        self.flat.setChecked(flat)
        self.spin.setEnabled(not flat)
        if not flat:
            self.spin.set_si(value)
        self.flat.blockSignals(False)


class PlotCanvas(FigureCanvasQTAgg):
    """A matplotlib figure embedded in Qt."""

    def __init__(self, nrows: int = 1, ncols: int = 1, width: float = 5, height: float = 3.5,
                 parent=None):
        self.figure = Figure(figsize=(width, height), layout="constrained")
        super().__init__(self.figure)
        self.setParent(parent)
        self.axes = self.figure.subplots(nrows, ncols, squeeze=False).ravel().tolist()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(220)

    def clear(self) -> None:
        for ax in self.axes:
            ax.clear()

    def message(self, text: str) -> None:
        """Replace the plots with a centred message (e.g. 'unstable')."""
        self.clear()
        for ax in self.axes:
            ax.set_axis_off()
        self.axes[0].text(0.5, 0.5, text, ha="center", va="center", wrap=True,
                          transform=self.axes[0].transAxes, color="0.3")
        self.draw_idle()


def info_label(text: str = "") -> QLabel:
    """A selectable, word-wrapped label for computed results."""
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lab.setTextFormat(Qt.RichText)
    return lab
