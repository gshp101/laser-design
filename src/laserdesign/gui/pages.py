"""The wizard pages: gain medium, pump, resonator, operation and results.

Every page follows the same small protocol so the main window can treat them
uniformly:

* ``load(spec)`` fills the widgets from a :class:`DesignSpec`;
* ``store(spec)`` writes the widgets back into it;
* ``refresh(spec)`` recomputes the page's live preview;
* the ``edited`` signal fires whenever the user changes an input.

Pages never hold physics state of their own; everything is recomputed from
the spec with :func:`laserdesign.gui.spec.build_laser`.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QRadioButton, QSplitter, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import gain, modelocking, pump, thermal
from ..abcd import StandingWaveCavity
from ..design import SidePumpedRodLaser
from ..materials import MATERIALS, get_material
from ..passive_qswitch import ABSORBERS
from . import icons
from .spec import (CRYSTAL_LENS_NAME, DesignSpec, absorber, build_laser, kerr_model,
                   library_location, round_trip_mode)
from .widgets import PlotCanvas, RadiusInput, UnitSpin, info_label

UM, MM, CM = 1e-6, 1e-3, 1e-2
HEADER_ICON = 36  # px, icon beside each page title


def _fmt(x: float, digits: int = 3) -> str:
    if x is None or not np.isfinite(x):
        return "∞" if x is not None and np.isinf(x) else "–"
    return f"{x:.{digits}g}"


class Page(QWidget):
    """Base class for wizard pages."""

    title = ""
    help_text = ""
    #: Name of the page's icon in ``laserdesign/gui/icons``.
    icon_name = ""
    edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False

    def _emit(self, *_args) -> None:
        if not self._loading:
            self.edited.emit()

    def load(self, spec: DesignSpec) -> None:  # pragma: no cover - overridden
        pass

    def store(self, spec: DesignSpec) -> None:  # pragma: no cover - overridden
        pass

    def refresh(self, spec: DesignSpec) -> None:  # pragma: no cover - overridden
        pass

    def _header(self, layout) -> None:
        row = QHBoxLayout()
        self.header_icon = QLabel()
        self.header_icon.setFixedSize(HEADER_ICON, HEADER_ICON)
        row.addWidget(self.header_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(QLabel(f"<h2>{self.title}</h2>"), 1)
        layout.addLayout(row)
        h = QLabel(f"<p>{self.help_text}</p>")
        h.setWordWrap(True)
        layout.addWidget(h)

    def refresh_icons(self) -> None:
        """Redraw the page's icons in the current palette (light or dark)."""
        if self.icon_name and hasattr(self, "header_icon"):
            self.header_icon.setPixmap(
                icons.icon(self.icon_name).pixmap(HEADER_ICON, HEADER_ICON))


# ====================================================================== #
# 1. Gain medium
# ====================================================================== #
#: Editable material properties: (attribute, label, display scale, suffix, decimals)
MATERIAL_FIELDS = [
    ("emission_cross_section", "Emission cross section", 1e-23, "×10⁻¹⁹ cm²", 3),
    ("upper_state_lifetime", "Upper-state lifetime", 1e-6, "µs", 1),
    ("refractive_index", "Refractive index", 1.0, "", 3),
    ("dn_dT", "dn/dT", 1e-6, "×10⁻⁶ /K", 2),
    ("thermal_conductivity", "Thermal conductivity", 1.0, "W/(m·K)", 2),
    ("pump_absorption_cross_section", "Pump absorption cross section", 1e-24,
     "×10⁻²⁰ cm²", 3),
    ("gain_bandwidth", "Gain bandwidth", 1e9, "GHz", 0),
]


class GainMediumPage(Page):
    title = "1. Gain medium"
    icon_name = "step-gain-medium"
    help_text = ("Choose the crystal, its doping and length. The material values are typical "
                 "literature numbers; edit any of them to match your crystal's data sheet.")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self._header(lay)
        form = QFormLayout()
        self.material = QComboBox()
        for key, mat in MATERIALS.items():
            self.material.addItem(mat.name, key)
        self.doping = UnitSpin(0.3, 1.0, "at.%", 0.001, 50, 3, 0.05)
        self.length = UnitSpin(6e-3, MM, "mm", 0.05, 500, 2, 0.5,
                               tooltip="Path length in the crystal, or rod length")
        self.brewster = QCheckBox("Brewster-cut (faces at Brewster's angle)")
        self.brewster.setToolTip("Models the crystal's astigmatism, e.g. Ti:sapphire in an "
                                 "X or Z cavity")
        form.addRow("Material", self.material)
        form.addRow("Doping", self.doping)
        form.addRow("Crystal / rod length", self.length)
        form.addRow("", self.brewster)
        lay.addLayout(form)

        box = QGroupBox("Material properties (edit to override)")
        bl = QFormLayout(box)
        self.props: dict[str, UnitSpin] = {}
        for attr, label, scale, suffix, dec in MATERIAL_FIELDS:
            spin = UnitSpin(0, scale, suffix, 0, 1e9, dec, 10 ** -dec if dec else 1)
            spin.valueChanged.connect(self._emit)
            self.props[attr] = spin
            bl.addRow(label, spin)
        self.reset = QPushButton("Reset to database values")
        self.reset.clicked.connect(self._reset)
        bl.addRow(self.reset)
        lay.addWidget(box)
        self.info = info_label()
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.material.currentIndexChanged.connect(self._material_changed)
        self.doping.valueChanged.connect(self._emit)
        self.length.valueChanged.connect(self._emit)
        self.brewster.toggled.connect(self._emit)
        self._overrides: dict = {}

    def _show_material(self, key: str, overrides: dict) -> None:
        mat = get_material(key).replace(**overrides) if overrides else get_material(key)
        for attr, spin in self.props.items():
            spin.set_si(getattr(mat, attr))
        self.doping.setSuffix(" " + mat.doping_unit)

    def _material_changed(self) -> None:
        if self._loading:
            return
        self._show_material(self.material.currentData(), {})
        self._emit()

    def _reset(self) -> None:
        self._show_material(self.material.currentData(), {})
        self._emit()

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        idx = self.material.findData(spec.material.lower())
        self.material.setCurrentIndex(max(idx, 0))
        self.doping.set_si(spec.doping)
        self.length.set_si(spec.crystal_length)
        self.brewster.setChecked(spec.crystal_brewster)
        self._show_material(spec.material, spec.material_overrides)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.material = self.material.currentData()
        spec.doping = self.doping.si()
        spec.crystal_length = self.length.si()
        spec.crystal_brewster = self.brewster.isChecked()
        base = get_material(spec.material)
        overrides = {}
        for attr, spin in self.props.items():
            v = spin.si()
            if not math.isclose(v, getattr(base, attr), rel_tol=1e-6):
                overrides[attr] = v
        spec.material_overrides = overrides

    def refresh(self, spec: DesignSpec) -> None:
        mat = spec.gain_medium()
        alpha = mat.pump_absorption_coefficient(spec.doping)
        absorbed = pump.absorbed_fraction(alpha, spec.crystal_length)
        kind = "quasi-three-level" if mat.is_quasi_three_level else "four-level"
        self.info.setText(
            f"<b>{mat.name}</b> ({kind}), λ<sub>laser</sub> = {mat.laser_wavelength / 1e-9:.1f} nm, "
            f"λ<sub>pump</sub> = {mat.pump_wavelength / 1e-9:.1f} nm<br>"
            f"Pump absorption coefficient α = {alpha / 100:.2f} /cm; single-pass absorption "
            f"{absorbed * 100:.1f} %<br>"
            f"Saturation fluence {mat.saturation_fluence / 1e4:.3g} J/cm², saturation "
            f"intensity {mat.saturation_intensity / 1e7:.3g} kW/cm²<br>"
            f"Heat fraction {mat.effective_heat_fraction:.2f}; σ·τ = "
            f"{mat.emission_cross_section * mat.upper_state_lifetime * 1e4 * 1e23:.3g}×10⁻²³ cm²·s "
            "(higher means lower threshold)")


# ====================================================================== #
# 2. Pump
# ====================================================================== #
class PumpPage(Page):
    title = "2. Pump"
    icon_name = "step-pump"
    help_text = ("Choose end pumping (a focused beam along the laser axis) or side pumping "
                 "(a rod pumped uniformly from the side by diodes or lamps). Fibre-coupled "
                 "diodes are best described by their M² (fibre radius × NA × π / λ).")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self._header(left)
        top = QFormLayout()
        self.geometry = QComboBox()
        self.geometry.addItem("End-pumped (focused beam)", "end")
        self.geometry.addItem("Side-pumped rod (uniform)", "side")
        self.power = UnitSpin(20, 1.0, "W", 0.01, 1e5, 2, 1)
        top.addRow("Pump geometry", self.geometry)
        top.addRow("Pump power", self.power)
        left.addLayout(top)

        self.geo_stack = QStackedWidget()
        end_w = QWidget()
        form = QFormLayout(end_w)
        form.setContentsMargins(0, 0, 0, 0)
        self.waist = UnitSpin(200e-6, UM, "µm", 1, 1e5, 1, 10)
        self.m2 = UnitSpin(30, 1.0, "", 1, 1e4, 1, 5)
        self.position = UnitSpin(1e-3, MM, "mm", -100, 100, 2, 0.5)
        self.passes = QComboBox()
        self.passes.addItems(["Single pass", "Double pass"])
        self.alpha_override = UnitSpin(0, CM ** -1, "/cm", 0, 1e4, 2, 0.5)
        self.alpha_override.setSpecialValueText("from material")
        form.addRow("Waist radius", self.waist)
        form.addRow("Beam quality M²", self.m2)
        form.addRow("Waist depth in crystal", self.position)
        form.addRow("Pumping", self.passes)
        form.addRow("Effective absorption", self.alpha_override)
        self.geo_stack.addWidget(end_w)

        side_w = QWidget()
        sf = QFormLayout(side_w)
        sf.setContentsMargins(0, 0, 0, 0)
        self.rod_radius = UnitSpin(2e-3, MM, "mm", 0.1, 100, 2, 0.25)
        self.abs_eff = UnitSpin(0.7, 0.01, "%", 1, 100, 1, 5,
                                tooltip="Fraction of the pump light absorbed in the rod")
        self.rod_lens = QComboBox()
        for key, label in (("average", "Average of radial and tangential"),
                           ("radial", "Radial polarisation"),
                           ("tangential", "Tangential polarisation"),
                           ("dn_dT", "dn/dT only (no stress)")):
            self.rod_lens.addItem(label, key)
        self.fill = UnitSpin(0, 0.01, "%", 0, 100, 0, 5,
                             tooltip="0 = TEM00 (aperture-limited); otherwise the multimode "
                                     "beam radius as a fraction of the rod radius")
        self.fill.setSpecialValueText("TEM00")
        sf.addRow("Rod radius", self.rod_radius)
        sf.addRow("Absorption efficiency", self.abs_eff)
        sf.addRow("Thermal lens in resonator", self.rod_lens)
        sf.addRow("Multimode fill", self.fill)
        self.geo_stack.addWidget(side_w)
        left.addWidget(self.geo_stack)

        self.info = info_label()
        left.addWidget(self.info)
        left.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(left)
        self.plot = PlotCanvas(2, 1, 5, 5)
        split = QSplitter()
        split.addWidget(wrap)
        split.addWidget(self.plot)
        split.setStretchFactor(1, 1)
        split.setSizes([480, 720])
        lay.addWidget(split)
        for w in (self.power, self.waist, self.m2, self.position, self.alpha_override,
                  self.rod_radius, self.abs_eff, self.fill):
            w.valueChanged.connect(self._emit)
        for w in (self.passes, self.rod_lens):
            w.currentIndexChanged.connect(self._emit)
        self.geometry.currentIndexChanged.connect(self._geometry_changed)

    def _geometry_changed(self, idx: int) -> None:
        self.geo_stack.setCurrentIndex(idx)
        self._emit()

    def refresh_icons(self) -> None:
        super().refresh_icons()
        for i in range(self.geometry.count()):
            self.geometry.setItemIcon(i, icons.icon(f"pump-{self.geometry.itemData(i)}"))

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.geometry.setCurrentIndex(self.geometry.findData(spec.pump_geometry))
        self.geo_stack.setCurrentIndex(self.geometry.currentIndex())
        self.power.set_si(spec.pump_power)
        self.waist.set_si(spec.pump_waist)
        self.m2.set_si(spec.pump_m2)
        self.position.set_si(spec.pump_waist_position)
        self.passes.setCurrentIndex(spec.pump_passes - 1)
        self.alpha_override.set_si(spec.effective_absorption or 0.0)
        self.rod_radius.set_si(spec.rod_radius)
        self.abs_eff.set_si(spec.absorption_efficiency)
        self.rod_lens.setCurrentIndex(self.rod_lens.findData(spec.rod_thermal_lens))
        self.fill.set_si(spec.multimode_fill or 0.0)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.pump_geometry = self.geometry.currentData()
        spec.pump_power = self.power.si()
        spec.pump_waist = self.waist.si()
        spec.pump_m2 = self.m2.si()
        spec.pump_waist_position = self.position.si()
        spec.pump_passes = self.passes.currentIndex() + 1
        a = self.alpha_override.si()
        spec.effective_absorption = a if a > 0 else None
        spec.rod_radius = self.rod_radius.si()
        spec.absorption_efficiency = self.abs_eff.si()
        spec.rod_thermal_lens = self.rod_lens.currentData()
        fill = self.fill.si()
        spec.multimode_fill = fill if fill > 0 else None

    def refresh(self, spec: DesignSpec) -> None:
        try:
            laser = build_laser(spec)
        except ValueError as exc:
            self.info.setText(f"<span style='color:#b00'>{exc}</span>")
            return
        if isinstance(laser, SidePumpedRodLaser):
            self._refresh_side(spec, laser)
            return
        mat = laser.material
        alpha = laser.absorption_coefficient
        eta = laser.absorbed_fraction
        w_eff = laser.pump_radius
        p_abs = spec.pump_power * eta
        p_heat = p_abs * mat.effective_heat_fraction
        f_th = laser.thermal_focal_length(spec.pump_power)
        n = mat.refractive_index
        z_r = np.pi * n * spec.pump_waist**2 / (spec.pump_m2 * mat.pump_wavelength)
        self.info.setText(
            f"Absorbed: <b>{p_abs:.2f} W</b> ({eta * 100:.1f} %), heat load {p_heat:.2f} W<br>"
            f"Pump Rayleigh range in crystal: {z_r / MM:.2f} mm "
            f"(crystal {spec.crystal_length / MM:.1f} mm)<br>"
            f"Absorption-weighted pump radius: <b>{w_eff / UM:.0f} µm</b><br>"
            f"Thermal focal length at full power: <b>{f_th / MM:.0f} mm</b>")
        z = np.linspace(0, spec.crystal_length, 200)
        self.plot.clear()
        a1, a2 = self.plot.axes
        w = laser.pump_beam.radius(z, n)
        a1.plot(z / MM, w / UM, color="C0")
        a1.plot(z / MM, -w / UM, color="C0")
        a1.axhline(w_eff / UM, ls="--", c="C1", lw=1, label="effective radius")
        a1.set(ylabel="pump radius [µm]", title="Pump beam in the crystal")
        a1.legend(fontsize=8)
        a2.plot(z / MM, alpha * np.exp(-alpha * z) * spec.pump_power / 100, color="C2")
        a2.set(xlabel="depth [mm]", ylabel="absorbed [W/cm]", title="Absorbed pump density")
        self.plot.draw_idle()

    def _refresh_side(self, spec: DesignSpec, laser: SidePumpedRodLaser) -> None:
        mat = laser.material
        p_abs = spec.pump_power * laser.absorbed_fraction
        p_heat = p_abs * mat.effective_heat_fraction
        f = laser.thermal_focal_lengths(p_abs)
        fracture = laser.stress_fracture_pump() / laser.absorbed_fraction
        d_t = thermal.side_pumped_center_temperature(p_heat, spec.crystal_length,
                                                     mat.thermal_conductivity)
        text = (f"Absorbed: <b>{p_abs:.3g} W</b>, heat load {p_heat:.3g} W "
                f"({p_heat / (spec.crystal_length / CM):.3g} W/cm)<br>"
                f"Centre-to-surface temperature rise {d_t:.3g} K<br>"
                f"Thermal focal length: radial <b>{f['radial'] / MM:.0f} mm</b>, tangential "
                f"<b>{f['tangential'] / MM:.0f} mm</b> (dn/dT only {f['dn_dT'] / MM:.0f} mm)")
        if np.isfinite(fracture):
            text += (f"<br>Fracture limit at about {fracture:.3g} W of pump "
                     f"({spec.pump_power / fracture * 100:.0f} % of it; keep below 25 to 50 %)")
        self.info.setText(text)
        powers = np.linspace(0.05, 1.25, 50) * spec.pump_power
        fl = [laser.thermal_focal_lengths(p * laser.absorbed_fraction) for p in powers]
        self.plot.clear()
        a1, a2 = self.plot.axes
        for key, ls in (("radial", "-"), ("tangential", "--"), ("average", ":")):
            a1.plot(powers, [x[key] / MM for x in fl], ls, label=key)
        a1.axvline(spec.pump_power, c="k", lw=0.8, ls=":")
        a1.set(yscale="log", ylabel="focal length [mm]", title="Rod thermal lens (bifocusing)")
        a1.legend(fontsize=8)
        r = np.linspace(0, spec.rod_radius, 100)
        a2.plot(r / MM, d_t * (1 - (r / spec.rod_radius) ** 2), color="C3")
        a2.set(xlabel="radius [mm]", ylabel="ΔT [K]", title="Temperature profile at full pump")
        self.plot.draw_idle()


# ====================================================================== #
# 3. Resonator
# ====================================================================== #
ELEMENT_LABELS = {"crystal": "Gain crystal", "space": "Air gap", "mirror": "Fold mirror",
                  "lens": "Thin lens", "medium": "Medium / Q-switch", "brewster": "Brewster plate"}
COLS = ["Element", "Name", "Length [mm]", "R or f [mm]", "Angle [°]", "Index n"]


class ResonatorPage(Page):
    title = "3. Resonator"
    icon_name = "step-resonator"
    help_text = ("For a standing-wave resonator, list the elements met going from end "
                 "mirror 1 (usually the pumped face) to end mirror 2. For a unidirectional "
                 "ring, list one full loop, with the curved mirrors as fold mirrors. Name "
                 "elements you want to refer to later (absorber, SESAM, aperture). The plots "
                 "show the TEM00 radius over one round trip at full pump power and how the "
                 "stability parameter "
                 "m = (A+D)/2 moves as the thermal lens changes; the resonator is stable "
                 "for −1 < m < 1.")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self._header(left)
        form = QFormLayout()
        self.cavity_type = QComboBox()
        self.cavity_type.addItem("Standing wave (two end mirrors)", "standing")
        self.cavity_type.addItem("Ring (unidirectional)", "ring")
        self.r1 = RadiusInput()
        self.r2 = RadiusInput()
        form.addRow("Resonator type", self.cavity_type)
        form.addRow("End mirror 1 radius", self.r1)
        form.addRow("End mirror 2 radius", self.r2)
        left.addLayout(form)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        left.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.add_buttons = {}
        for t in ("space", "mirror", "lens", "medium", "brewster"):
            b = QPushButton("+ " + ELEMENT_LABELS[t])
            b.clicked.connect(lambda _=False, t=t: self.add_element(t))
            buttons.addWidget(b)
            self.add_buttons[t] = b
        left.addLayout(buttons)
        edit = QHBoxLayout()
        self.remove = QPushButton("Remove")
        self.up = QPushButton("Move up")
        self.down = QPushButton("Move down")
        for b in (self.remove, self.up, self.down):
            edit.addWidget(b)
        edit.addStretch(1)
        left.addLayout(edit)
        self.info = info_label()
        left.addWidget(self.info)
        wrap = QWidget()
        wrap.setLayout(left)

        self.plot = PlotCanvas(2, 1, 5.5, 6)
        split = QSplitter()
        split.addWidget(wrap)
        split.addWidget(self.plot)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([560, 640])
        lay.addWidget(split)

        self.remove.clicked.connect(self._remove)
        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(1))
        self.r1.changed.connect(self._emit)
        self.r2.changed.connect(self._emit)
        self.table.itemChanged.connect(self._emit)
        self.cavity_type.currentIndexChanged.connect(self._type_changed)

    def _type_changed(self, _idx: int = 0) -> None:
        standing = self.cavity_type.currentData() == "standing"
        self.r1.setEnabled(standing)
        self.r2.setEnabled(standing)
        self._emit()

    # -- table helpers ------------------------------------------------- #
    def _set_row(self, row: int, e: dict) -> None:
        t = e["type"]
        cells = [ELEMENT_LABELS[t], e.get("name", ""), "", "", "", ""]
        editable = {1}
        if t in ("space", "medium"):
            cells[2] = f"{e['length'] / MM:.4g}"
            editable.add(2)
        if t == "brewster":
            cells[2] = f"{e['thickness'] / MM:.4g}"
            editable.add(2)
        if t == "mirror":
            r = float(e.get("R", math.inf))
            cells[3] = "inf" if math.isinf(r) else f"{r / MM:.4g}"
            cells[4] = f"{e.get('angle_deg', 0.0):.4g}"
            editable |= {3, 4}
        if t == "lens":
            cells[3] = f"{float(e['f']) / MM:.4g}"
            editable.add(3)
        if t in ("medium", "brewster"):
            cells[5] = f"{e.get('n', 1.5):.4g}"
            editable.add(5)
        if t == "crystal":
            cells[1] = "(from page 1)"
            editable = set()
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, t)
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            if col in editable:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            self.table.setItem(row, col, item)

    def _row_to_element(self, row: int) -> dict:
        t = self.table.item(row, 0).data(Qt.UserRole)

        def num(col, scale=1.0):
            text = self.table.item(row, col).text().strip().lower()
            if text in ("inf", "∞", "flat", ""):
                return math.inf
            return float(text) * scale

        e: dict = {"type": t}
        name = self.table.item(row, 1).text().strip()
        if name and t != "crystal":
            e["name"] = name
        if t in ("space", "medium"):
            e["length"] = num(2, MM)
        if t == "brewster":
            e["thickness"] = num(2, MM)
        if t == "mirror":
            e["R"] = num(3, MM)
            e["angle_deg"] = num(4)
        if t == "lens":
            e["f"] = num(3, MM)
        if t in ("medium", "brewster"):
            e["n"] = num(5)
        return e

    def elements(self) -> list[dict]:
        return [self._row_to_element(r) for r in range(self.table.rowCount())]

    def _set_elements(self, elements: list[dict]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(elements))
        for r, e in enumerate(elements):
            self._set_row(r, e)
        self.table.blockSignals(False)

    def add_element(self, t: str) -> None:
        defaults = {"space": {"type": "space", "length": 0.05},
                    "mirror": {"type": "mirror", "R": 0.2, "angle_deg": 5.0},
                    "lens": {"type": "lens", "f": 0.1},
                    "medium": {"type": "medium", "length": 0.02, "n": 1.45, "name": "Q-switch"},
                    "brewster": {"type": "brewster", "thickness": 0.005, "n": 1.45}}
        els = self.elements()
        row = self.table.currentRow()
        pos = len(els) if row < 0 else row + 1
        els.insert(pos, dict(defaults[t]))
        self._set_elements(els)
        self.table.selectRow(pos)
        self._emit()

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        els = self.elements()
        if els[row]["type"] == "crystal":
            self.info.setText("<span style='color:#b00'>The gain crystal cannot be removed; "
                              "move it instead.</span>")
            return
        del els[row]
        self._set_elements(els)
        self._emit()

    def _move(self, step: int) -> None:
        row = self.table.currentRow()
        new = row + step
        els = self.elements()
        if row < 0 or not 0 <= new < len(els):
            return
        els[row], els[new] = els[new], els[row]
        self._set_elements(els)
        self.table.selectRow(new)
        self._emit()

    # -- protocol ------------------------------------------------------ #
    def refresh_icons(self) -> None:
        super().refresh_icons()
        for i in range(self.cavity_type.count()):
            self.cavity_type.setItemIcon(i, icons.icon(f"cavity-{self.cavity_type.itemData(i)}"))

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.cavity_type.setCurrentIndex(self.cavity_type.findData(spec.cavity_type))
        self.r1.set_si(spec.R1)
        self.r2.set_si(spec.R2)
        self.r1.setEnabled(spec.cavity_type == "standing")
        self.r2.setEnabled(spec.cavity_type == "standing")
        self._set_elements(spec.elements)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.cavity_type = self.cavity_type.currentData()
        spec.R1 = self.r1.si()
        spec.R2 = self.r2.si()
        try:
            spec.elements = self.elements()
        except ValueError:
            self.info.setText("<span style='color:#b00'>Could not read a number in the "
                              "element table.</span>")

    def refresh(self, spec: DesignSpec) -> None:
        try:
            laser = build_laser(spec)
        except ValueError as exc:
            self.info.setText(f"<span style='color:#b00'>{exc}</span>")
            self.plot.message(str(exc))
            return
        powers = np.linspace(0.02, 1.25, 60) * spec.pump_power
        cavs = [laser.resonator(p) for p in powers]
        m_t = [c.stability_parameter("t") for c in cavs]
        m_s = [c.stability_parameter("s") for c in cavs]
        stable_p = [p for p, c in zip(powers, cavs) if c.is_stable()]
        cav = laser.resonator(spec.pump_power)
        self.plot.clear()
        a1, a2 = self.plot.axes
        if cav.is_stable():
            trip = round_trip_mode(cav)
            for plane, ls in (("t", "-"), ("s", "--")):
                prof = trip[plane]
                a1.plot(prof.z / MM, prof.w / UM, ls,
                        label="tangential" if plane == "t" else "sagittal")
            a1.set_ylim(bottom=0)
            for z, label in trip["landmarks"]:
                a1.axvline(z / MM, c="0.6", lw=0.7, ls=":")
                a1.text(z / MM, 0.98, label, rotation=90, ha="right", va="top", fontsize=7,
                        color="0.35", transform=a1.get_xaxis_transform())
            standing = isinstance(cav, StandingWaveCavity)
            a1.set(xlabel=trip["xlabel"], ylabel="w [µm]",
                   title=f"{trip['title']} at {spec.pump_power:.3g} W pump")
            a1.legend(fontsize=8, loc="lower right")
            w_l = cav.spot_size_at(CRYSTAL_LENS_NAME)
            pump_kind = "rod" if isinstance(laser, SidePumpedRodLaser) else "pump"
            text = (f"<b>Stable</b> at {spec.pump_power:.3g} W: m = "
                    f"{cav.stability_parameter('t'):.3f} (t), {cav.stability_parameter('s'):.3f} (s)<br>"
                    f"Mode radius in crystal {w_l / UM:.0f} µm vs {pump_kind} "
                    f"{laser.pump_radius / UM:.0f} µm (ratio {w_l / laser.pump_radius:.2f})<br>")
            if standing:
                text += (f"On mirror 1: {cav.spot_size_on_mirror(1) / UM:.0f} µm, mirror 2: "
                         f"{cav.spot_size_on_mirror(2) / UM:.0f} µm<br>")
            else:
                named = [e.name for e in cav.elements if e.name and "crystal" not in e.name]
                if named:
                    text += "Spot sizes: " + ", ".join(
                        f"{nm} {cav.spot_size_at(nm) / UM:.0f} µm" for nm in named[:6]) + "<br>"
                text += "Ring: one gain pass per round trip, repetition rate c/L.<br>"
        else:
            a1.text(0.5, 0.5, "Unstable at full pump power", ha="center", va="center",
                    transform=a1.transAxes, color="#b00")
            a1.set_axis_off()
            text = f"<span style='color:#b00'><b>Unstable</b> at {spec.pump_power:.3g} W.</span><br>"
        if stable_p:
            text += f"Stable pump range in the plot: {min(stable_p):.3g} to {max(stable_p):.3g} W<br>"
        text += (f"Optical length {cav.optical_length / MM:.1f} mm, FSR "
                 f"{cav.free_spectral_range / 1e9:.3g} GHz, round trip {cav.round_trip_time * 1e9:.3g} ns")
        self.info.setText(text)
        a2.plot(powers, m_t, label="tangential")
        a2.plot(powers, m_s, "--", label="sagittal")
        a2.axhspan(-1, 1, color="C2", alpha=0.08)
        a2.axvline(spec.pump_power, c="k", lw=0.8, ls=":")
        a2.set(xlabel="pump power [W]", ylabel="m = (A+D)/2", title="Stability vs pump power",
               ylim=(max(-3, min(min(m_t), min(m_s)) - 0.2), min(3, max(max(m_t), max(m_s)) + 0.2)))
        a2.legend(fontsize=8)
        self.plot.draw_idle()


# ====================================================================== #
# 4. Operation
# ====================================================================== #
MODES = (("cw", "Continuous wave"), ("qswitch", "Active Q-switch"),
         ("passive", "Passive Q-switch"), ("modelock", "SESAM mode-locked"),
         ("klm", "Kerr-lens mode-locked"))
MODE_KEYS = tuple(k for k, _ in MODES)


class LocationCombo(QComboBox):
    """Choose an end mirror or a named resonator element."""

    def __init__(self, allow_crystal: bool = False, parent=None):
        super().__init__(parent)
        self.allow_crystal = allow_crystal
        self._value = "mirror2"

    def populate(self, spec: DesignSpec) -> None:
        self.blockSignals(True)
        self.clear()
        if spec.cavity_type == "standing":
            self.addItem("End mirror 1", "mirror1")
            self.addItem("End mirror 2", "mirror2")
        if self.allow_crystal:
            self.addItem("Gain crystal (soft aperture)", "crystal")
        for e in spec.elements:
            if e.get("name"):
                self.addItem(f"Element: {e['name']}", e["name"])
        idx = self.findData(self._value)
        if idx < 0:
            self.addItem(f"{self._value} (not found)", self._value)
            idx = self.count() - 1
        self.setCurrentIndex(idx)
        self.blockSignals(False)

    def value(self) -> str:
        return self.currentData() or self._value

    def set_value(self, value: str) -> None:
        self._value = value
        idx = self.findData(value)
        if idx >= 0:
            self.blockSignals(True)
            self.setCurrentIndex(idx)
            self.blockSignals(False)


class OperationPage(Page):
    title = "4. Operation"
    icon_name = "step-operation"
    help_text = ("Choose the output coupling, the other losses and how the laser is run: "
                 "continuous wave, actively Q-switched with CW pumping, passively Q-switched "
                 "with a saturable absorber, SESAM mode-locked, or Kerr-lens mode-locked. "
                 "Absorbers, SESAMs and apertures sit at an end mirror or a named element.")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self._header(lay)
        form = QFormLayout()
        self.oc = UnitSpin(0.1, 0.01, "%", 0.01, 99, 2, 1)
        self.loss = UnitSpin(0.01, 0.01, "%", 0, 50, 2, 0.5)
        form.addRow("Output coupler transmission", self.oc)
        form.addRow("Other round-trip losses", self.loss)
        lay.addLayout(form)

        modes = QGroupBox("Operating mode")
        ml = QHBoxLayout(modes)
        self.group = QButtonGroup(self)
        self.radios = {}
        for i, (key, label) in enumerate(MODES):
            rb = QRadioButton(label)
            self.group.addButton(rb, i)
            self.radios[key] = rb
            ml.addWidget(rb)
        lay.addWidget(modes)

        self.stack = QStackedWidget()
        self.stack.addWidget(info_label("No further settings for CW operation."))
        qs = QWidget()
        qf = QFormLayout(qs)
        self.rep_rate = UnitSpin(20e3, 1e3, "kHz", 0.001, 1e4, 3, 1)
        qf.addRow("Repetition rate", self.rep_rate)
        self.stack.addWidget(qs)

        pw = QWidget()
        pf = QFormLayout(pw)
        self.absorber = QComboBox()
        for key, a in ABSORBERS.items():
            self.absorber.addItem(a.name, key)
        self.t0 = UnitSpin(0.85, 0.01, "%", 1, 99.9, 1, 1,
                           tooltip="Small-signal single-pass transmission T0")
        self.absorber_loc = LocationCombo()
        pf.addRow("Saturable absorber", self.absorber)
        pf.addRow("Initial transmission T0", self.t0)
        pf.addRow("Absorber location", self.absorber_loc)
        self.stack.addWidget(pw)

        mlw = QWidget()
        mf = QFormLayout(mlw)
        self.fsat = UnitSpin(0.6, 1e-2, "µJ/cm²", 0.1, 1e5, 1, 5)
        self.dr = UnitSpin(0.01, 0.01, "%", 0.01, 50, 2, 0.1)
        self.sesam_loc = LocationCombo()
        mf.addRow("SESAM saturation fluence", self.fsat)
        mf.addRow("SESAM modulation depth", self.dr)
        mf.addRow("SESAM location", self.sesam_loc)
        self.stack.addWidget(mlw)

        kw = QWidget()
        kf = QFormLayout(kw)
        self.klm_loc = LocationCombo(allow_crystal=True)
        self.slices = UnitSpin(6, 1.0, "", 2, 40, 0, 2)
        self.pulse = UnitSpin(20e-15, 1e-15, "fs", 3, 1e5, 1, 5)
        kf.addRow("Aperture (where the Kerr effect is read)", self.klm_loc)
        kf.addRow("Crystal slices", self.slices)
        kf.addRow("Target pulse width", self.pulse)
        self.stack.addWidget(kw)
        lay.addWidget(self.stack)
        self.info = info_label()
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.group.idClicked.connect(self._mode_changed)
        for w in (self.oc, self.loss, self.rep_rate, self.fsat, self.dr, self.t0, self.slices,
                  self.pulse):
            w.valueChanged.connect(self._emit)
        for w in (self.absorber, self.absorber_loc, self.sesam_loc, self.klm_loc):
            w.currentIndexChanged.connect(self._emit)

    def _mode_changed(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self._emit()

    def mode(self) -> str:
        return MODE_KEYS[max(self.group.checkedId(), 0)]

    def refresh_icons(self) -> None:
        super().refresh_icons()
        for key, radio in self.radios.items():
            radio.setIcon(icons.icon(f"mode-{key}"))

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.oc.set_si(spec.output_coupling)
        self.loss.set_si(spec.passive_loss)
        self.radios[spec.mode].setChecked(True)
        self.stack.setCurrentIndex(MODE_KEYS.index(spec.mode))
        self.rep_rate.set_si(spec.rep_rate)
        self.fsat.set_si(spec.sesam_saturation_fluence)
        self.dr.set_si(spec.sesam_modulation_depth)
        self.absorber.setCurrentIndex(max(self.absorber.findData(spec.absorber), 0))
        self.t0.set_si(spec.absorber_transmission)
        self.slices.set_si(spec.klm_slices)
        self.pulse.set_si(spec.klm_pulse_width)
        for combo, value in ((self.absorber_loc, spec.absorber_location),
                             (self.sesam_loc, spec.sesam_location),
                             (self.klm_loc, spec.klm_aperture)):
            combo.set_value(value)
            combo.populate(spec)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.output_coupling = self.oc.si()
        spec.passive_loss = self.loss.si()
        spec.mode = self.mode()
        spec.rep_rate = self.rep_rate.si()
        spec.sesam_saturation_fluence = self.fsat.si()
        spec.sesam_modulation_depth = self.dr.si()
        spec.absorber = self.absorber.currentData()
        spec.absorber_transmission = self.t0.si()
        spec.klm_slices = int(round(self.slices.si()))
        spec.klm_pulse_width = self.pulse.si()
        for combo in (self.absorber_loc, self.sesam_loc, self.klm_loc):
            combo.set_value(combo.value())
        spec.absorber_location = self.absorber_loc.value()
        spec.sesam_location = self.sesam_loc.value()
        spec.klm_aperture = self.klm_loc.value()

    def refresh(self, spec: DesignSpec) -> None:
        for combo in (self.absorber_loc, self.sesam_loc, self.klm_loc):
            combo.populate(spec)
        try:
            laser = build_laser(spec)
        except ValueError as exc:
            self.info.setText(f"<span style='color:#b00'>{exc}</span>")
            return
        delta = laser.delta
        text = (f"Logarithmic round-trip loss δ = {delta:.4f}; share leaving through the "
                f"output coupler {gain.output_fraction(spec.output_coupling, delta) * 100:.1f} %.")
        op = laser.analyze(spec.pump_power)
        if op.stable:
            text += f"<br>CW threshold {op.threshold:.3g} W, CW output {op.output_power:.3g} W."
            if op.gain_passes == 1:
                text += "<br>Ring resonator: one gain pass per round trip."
        if spec.mode == "passive":
            a = absorber(spec)
            l_gs, l_es = a.losses(spec.absorber_transmission, op.gain_passes)
            text += (f"<br>{a.name}: unbleached round-trip loss {l_gs:.3f}, bleached "
                     f"{l_es:.3f}; recovery time {a.recovery_time * 1e6:.2g} µs.")
        if spec.mode == "klm":
            km = kerr_model(spec)
            text += (f"<br>Kerr medium: n₂ = {km.n2 * 1e20:.3g}×10⁻²⁰ m²/W, critical power "
                     f"P<sub>cr</sub> = {km.critical_power / 1e6:.3g} MW.")
            if km.n2 == 0:
                text += (" <span style='color:#b00'>This material has no n₂ value; set one "
                         "to use KLM.</span>")
        self.info.setText(text)


# ====================================================================== #
# 5. Results
# ====================================================================== #
class ResultsPage(Page):
    title = "5. Results"
    icon_name = "step-results"
    help_text = "Performance of the design. Go back to any step to change it; results update."

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self._header(left)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Quantity", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        left.addWidget(self.table, 1)
        self.notes = info_label()
        left.addWidget(self.notes)
        wrap = QWidget()
        wrap.setLayout(left)
        self.plot = PlotCanvas(2, 1, 5.5, 6)
        split = QSplitter()
        split.addWidget(wrap)
        split.addWidget(self.plot)
        split.setStretchFactor(1, 1)
        lay.addWidget(split)
        split.setSizes([520, 680])
        self.rows: list[tuple[str, str]] = []
        self._twins: list = []

    def load(self, spec: DesignSpec) -> None:
        pass

    def store(self, spec: DesignSpec) -> None:
        pass

    def _set_rows(self, rows) -> None:
        self.rows = rows
        self.table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(k))
            item = QTableWidgetItem(v)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 1, item)

    def refresh(self, spec: DesignSpec) -> None:
        try:
            laser = build_laser(spec)
        except ValueError as exc:
            self._set_rows([("Error", str(exc))])
            self.plot.message(str(exc))
            return
        p = spec.pump_power
        op = laser.analyze(p)
        if not op.stable:
            self._set_rows([("Resonator", "unstable at this pump power")])
            self.plot.message("The resonator is unstable at the chosen pump power.\n"
                              "Go back to step 3 to change it.")
            self.notes.setText("")
            return
        rows = [
            ("Design", spec.name),
            ("Pump power", f"{p:.3g} W"),
            ("Absorbed power", f"{op.absorbed_power:.3g} W"),
            ("Heat load", f"{op.heat_power:.3g} W"),
            ("Thermal focal length", f"{op.thermal_focal_length / MM:.0f} mm"),
            ("Stability parameter m", f"{op.stability_parameter:.3f}"),
            ("Resonator type", "ring (1 gain pass)" if op.gain_passes == 1
             else "standing wave (2 gain passes)"),
            ("Laser / pump radius in crystal",
             f"{op.laser_radius / UM:.0f} / {op.pump_radius / UM:.0f} µm"
             + (" (multimode flat-top / rod)" if op.laser_profile == "tophat" else "")),
            ("CW threshold", f"{op.threshold:.3g} W"),
            ("CW output power", f"{op.output_power:.3g} W"),
            ("Optical efficiency", f"{op.output_power / p * 100:.1f} %"),
            ("M² estimate", f"{op.m2_estimate:.2f} (aberration {op.m2_aberration:.2f}, "
                            f"multimode {op.m2_multimode:.2f})"),
        ]
        if op.aperture_loss > 1e-4:
            rows.append(("Rod clipping loss (round trip)", f"{op.aperture_loss * 100:.2f} %"))
        stable_ops = [o for o in laser.scan(np.linspace(0.05, 1.0, 25) * p) if o.stable]
        for twin in self._twins:
            twin.remove()
        self._twins = []
        self.plot.clear()
        a1, a2 = self.plot.axes
        notes = ""

        if spec.mode == "cw":
            pp = [o.pump_power for o in stable_ops]
            a1.plot(pp, [o.output_power for o in stable_ops])
            a1.set(xlabel="pump power [W]", ylabel="output [W]", title="CW output")
            a2.plot(pp, [o.m2_estimate for o in stable_ops], label="combined")
            a2.plot(pp, [o.m2_aberration for o in stable_ops], ":", label="thermal aberration")
            a2.plot(pp, [o.m2_multimode for o in stable_ops], "--", label="pump/mode ratio")
            a2.set(xlabel="pump power [W]", ylabel="M²", title="Beam quality estimate")
            a2.legend(fontsize=8)

        elif spec.mode == "qswitch":
            qs = laser.q_switched(p, spec.rep_rate)
            rows += [
                ("Repetition rate", f"{spec.rep_rate / 1e3:.3g} kHz"),
                ("Initial inversion / threshold", f"{qs['initial_ratio']:.2f}"),
                ("Pulse energy", f"{qs['energy'] * 1e3:.3g} mJ"),
                ("Pulse width (E / P_peak)", f"{qs['pulse_width'] * 1e9:.3g} ns"),
                ("Peak power", f"{qs['peak_power'] / 1e3:.3g} kW"),
                ("Average power", f"{qs['average_power']:.3g} W"),
            ]
            rates = np.geomspace(spec.rep_rate / 30, spec.rep_rate * 30, 30)
            res = [laser.q_switched(p, f) for f in rates]
            a1.semilogx(rates / 1e3, [r["energy"] * 1e3 for r in res])
            a1.axvline(spec.rep_rate / 1e3, c="k", ls=":", lw=0.8)
            a1.set(xlabel="repetition rate [kHz]", ylabel="energy [mJ]", title="Pulse energy")
            a2.semilogx(rates / 1e3, [r["pulse_width"] * 1e9 for r in res], label="pulse width")
            a2.set(xlabel="repetition rate [kHz]", ylabel="pulse width [ns]",
                   title="Width and average power")
            a3 = a2.twinx()
            self._twins.append(a3)
            a3.semilogx(rates / 1e3, [r["average_power"] for r in res], "C1",
                        label="average power")
            a3.axhline(op.output_power, c="k", ls="--", lw=0.8, label="CW power")
            a3.set_ylabel("average power [W]")
            h1, l1 = a2.get_legend_handles_labels()
            h2, l2 = a3.get_legend_handles_labels()
            a2.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
            if qs["initial_ratio"] <= 1:
                notes = "The inversion does not reach threshold between pulses: no output."

        elif spec.mode == "passive":
            notes = self._passive(spec, laser, rows, stable_ops, a1, a2)

        elif spec.mode == "klm":
            notes = self._klm(spec, laser, op, rows, a1, a2)

        else:  # modelock
            loc = library_location(spec.sesam_location)
            res = laser.sesam_mode_locked(p, spec.sesam_saturation_fluence,
                                          spec.sesam_modulation_depth, loc)
            c = res["check"]
            rows += [
                ("Repetition rate", f"{c.repetition_rate / 1e6:.4g} MHz"),
                ("Intracavity pulse energy", f"{c.pulse_energy * 1e9:.3g} nJ"),
                ("QML threshold", f"{c.qml_threshold * 1e9:.3g} nJ"),
                ("QML margin", f"{c.qml_margin:.2f}"),
                ("SESAM spot radius", f"{res['absorber_radius'] / UM:.0f} µm"),
                ("SESAM saturation E_p / E_sat,A", f"{c.absorber_saturation:.1f}"),
                ("Pulse width estimate", f"{c.pulse_width_estimate * 1e12:.3g} ps"),
                ("Transform limit", f"{c.transform_limit * 1e12:.3g} ps"),
            ]
            pp, checks = [], []
            for o in stable_ops:
                pp.append(o.pump_power)
                checks.append(laser.sesam_mode_locked(o.pump_power, spec.sesam_saturation_fluence,
                                                      spec.sesam_modulation_depth, loc)["check"])
            a1.plot(pp, [k.qml_margin for k in checks], label="E_p / E_p,QML")
            a1.plot(pp, [k.absorber_saturation for k in checks], label="E_p / E_sat,A")
            a1.axhline(1, c="k", ls=":", lw=0.8)
            a1.set(xlabel="pump power [W]", ylabel="ratio", title="Mode-locking margins")
            a1.legend(fontsize=8)
            a2.plot(pp, [o.output_power for o in stable_ops])
            a2.set(xlabel="pump power [W]", ylabel="average output [W]", title="Average output")
            if c.qml_margin < 1:
                notes = ("<span style='color:#b00'>Below the QML threshold: the laser will "
                         "Q-switch mode lock. Lengthen the cavity, shrink the mode on the SESAM, "
                         "or use a SESAM with lower saturation fluence or modulation depth.</span>")
            elif c.absorber_saturation > 20:
                notes = ("<span style='color:#b00'>The SESAM is saturated more than 20×; risk of "
                         "damage or multiple pulsing. Enlarge the mode on the SESAM.</span>")
            elif c.absorber_saturation < 3:
                notes = "The SESAM is only weakly saturated; mode-locking may not self-start."
        self._set_rows(rows)
        self.notes.setText(notes + "<br><i>Results come from idealised models; see the theory "
                           "pages for their assumptions.</i>")
        self.plot.draw_idle()

    # ------------------------------------------------------------------ #
    def _passive(self, spec, laser, rows, stable_ops, a1, a2) -> str:
        p = spec.pump_power
        loc = library_location(spec.absorber_location)
        ab = absorber(spec)
        res = laser.passively_q_switched(p, spec.absorber_transmission, ab, loc)
        pulse = res["pulse"]
        rows += [
            ("Absorber", f"{ab.name}, T0 = {spec.absorber_transmission * 100:.1f} %"),
            ("Absorber spot radius", f"{res['absorber_radius'] / UM:.0f} µm"),
            ("Bleaching criterion (needs > 1)", f"{pulse.bleaching_criterion:.2f}"),
            ("Threshold with absorber", f"{res['threshold']:.3g} W"),
            ("Pulse energy", f"{res['energy'] * 1e3:.3g} mJ"),
            ("Pulse width (E / P_peak)", f"{res['pulse_width'] * 1e9:.3g} ns"),
            ("Peak power", f"{res['peak_power'] / 1e3:.3g} kW"),
            ("Repetition rate", f"{res['rep_rate'] / 1e3:.3g} kHz"),
            ("Average power", f"{res['average_power']:.3g} W"),
        ]
        pp = [o.pump_power for o in stable_ops]
        vs_p = [laser.passively_q_switched(x, spec.absorber_transmission, ab, loc) for x in pp]
        a1.plot(pp, [v["rep_rate"] / 1e3 for v in vs_p])
        a1.set(xlabel="pump power [W]", ylabel="repetition rate [kHz]",
               title="Pump sets the repetition rate")
        a3 = a1.twinx()
        self._twins.append(a3)
        a3.plot(pp, [v["average_power"] for v in vs_p], "C1--")
        a3.set_ylabel("average power [W]", color="C1")
        t0s = np.linspace(max(0.3, spec.absorber_transmission - 0.3),
                          min(0.98, spec.absorber_transmission + 0.1), 25)
        vs_t = [laser.passively_q_switched(p, t, ab, loc) for t in t0s]
        a2.plot(t0s * 100, [v["energy"] * 1e3 for v in vs_t])
        a2.axvline(spec.absorber_transmission * 100, c="k", ls=":", lw=0.8)
        a2.set(xlabel="absorber T0 [%]", ylabel="energy [mJ]", title="Energy vs absorber T0")
        a4 = a2.twinx()
        self._twins.append(a4)
        a4.plot(t0s * 100, [v["pulse_width"] * 1e9 for v in vs_t], "C1--")
        a4.set_ylabel("pulse width [ns]", color="C1")
        if not pulse.pulse_forms:
            return ("<span style='color:#b00'>The absorber does not bleach fast enough for a "
                    "giant pulse (criterion below 1). Focus harder into the absorber or use "
                    "a lower T0.</span>")
        if res["rep_rate"] == 0:
            return ("<span style='color:#b00'>The pump does not reach threshold with the "
                    "absorber.</span>")
        if not res["absorber_recovered"]:
            return ("The pulse period is shorter than three absorber recovery times; the "
                    "absorber will not recover fully and the pulses will be weaker.")
        return ""

    def _klm(self, spec, laser, op, rows, a1, a2) -> str:
        p = spec.pump_power
        f_th = laser.thermal_focal_length(p)
        km = kerr_model(spec, f_th)
        if km.n2 <= 0:
            a1.set_axis_off()
            a2.set_axis_off()
            return ("<span style='color:#b00'>The gain medium has no n₂: KLM cannot be "
                    "estimated.</span>")
        loc = library_location(spec.klm_aperture)
        p_cr = km.critical_power
        cav = laser.resonator(p)
        ring = op.gain_passes == 1
        f_rep = modelocking.repetition_rate(cav.optical_length, ring=ring)
        e_p = op.circulating_power / f_rep
        peak = 0.88 * e_p / spec.klm_pulse_width
        sol0 = km.solve(0.0)
        w_x = km.spot_size(sol0, "crystal", "t") * (km.n if km.brewster else 1.0)
        w_y = km.spot_size(sol0, "crystal", "s")
        spm = modelocking.spm_coefficient(km.n2, km.crystal_length, np.pi * w_x * w_y,
                                          km.wavelength, passes=op.gain_passes)
        strengths = {(lo, pl): km.klm_strength(lo, pl)
                     for lo in (loc, "crystal") for pl in ("t", "s")}
        rows += [
            ("Critical power P_cr", f"{p_cr / 1e6:.3g} MW"),
            ("KLM strength at aperture (t / s)",
             f"{strengths[(loc, 't')]:.2f} / {strengths[(loc, 's')]:.2f}"),
            ("KLM strength in crystal (t / s)",
             f"{strengths[('crystal', 't')]:.2f} / {strengths[('crystal', 's')]:.2f}"),
            ("Repetition rate", f"{f_rep / 1e6:.4g} MHz"),
            ("Intracavity pulse energy", f"{e_p * 1e9:.3g} nJ"),
            ("Peak power / P_cr", f"{peak / p_cr:.2f}"),
        ]
        if e_p > 0:
            gdd = modelocking.soliton_required_gdd(spec.klm_pulse_width, spm, e_p)
            rows.append(("Soliton net GDD per round trip", f"{gdd / 1e-30:.0f} fs²"))
            gvd = laser.material.gvd
            if gvd:
                mat_gdd = op.gain_passes * gvd * spec.crystal_length
                rows.append(("Crystal GDD per round trip", f"+{mat_gdd / 1e-30:.0f} fs²"))
                rows.append(("Compensation needed (prisms, mirrors)",
                             f"{(gdd - mat_gdd) / 1e-30:.0f} fs²"))
        p_axis = np.linspace(0, 0.3, 10)
        a1.plot(p_axis, km.spot_vs_power(p_axis, loc, "t") / km.spot_vs_power([0], loc, "t")[0],
                label="at aperture")
        a1.plot(p_axis, km.spot_vs_power(p_axis, "crystal", "t")
                / km.spot_vs_power([0], "crystal", "t")[0], "--", label="in crystal")
        a1.set(xlabel="P / P_cr", ylabel="w(P) / w(0)", title="Self-consistent Kerr lens (t)")
        a1.legend(fontsize=8)
        pumps = np.linspace(0.2, 1.2, 9) * p
        hard, soft = [], []
        for x in pumps:
            m = kerr_model(spec, laser.thermal_focal_length(x))
            hard.append(m.klm_strength(loc, "t"))
            soft.append(m.klm_strength("crystal", "t"))
        a2.plot(pumps, hard, "o-", ms=3, label="at aperture")
        a2.plot(pumps, soft, "s--", ms=3, label="in crystal")
        a2.axhline(0, c="k", lw=0.6)
        a2.axvline(p, c="k", ls=":", lw=0.8)
        a2.set(xlabel="pump power [W]", ylabel="δ = (1/w) dw/dp",
               title="KLM strength vs thermal lens")
        a2.legend(fontsize=8)
        d = strengths[(loc, "t")]
        if not np.isfinite(d):
            return "<span style='color:#b00'>The Kerr-lensed resonator is unstable.</span>"
        hint = ("A negative δ at a hard aperture favours pulses (the pulse shrinks there); "
                "a negative δ in the crystal helps soft-aperture KLM with a small pump. "
                "|δ| grows near the stability edges.")
        return hint


ALL_PAGES = (GainMediumPage, PumpPage, ResonatorPage, OperationPage, ResultsPage)
