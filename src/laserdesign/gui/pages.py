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
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QRadioButton, QSplitter, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import gain, pump
from ..materials import MATERIALS, get_material
from .spec import DesignSpec, build_laser
from .widgets import PlotCanvas, RadiusInput, UnitSpin, info_label

UM, MM, CM = 1e-6, 1e-3, 1e-2


def _fmt(x: float, digits: int = 3) -> str:
    if x is None or not np.isfinite(x):
        return "∞" if x is not None and np.isinf(x) else "–"
    return f"{x:.{digits}g}"


class Page(QWidget):
    """Base class for wizard pages."""

    title = ""
    help_text = ""
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
        h = QLabel(f"<h2>{self.title}</h2><p>{self.help_text}</p>")
        h.setWordWrap(True)
        layout.addWidget(h)


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
        self.length = UnitSpin(6e-3, MM, "mm", 0.05, 500, 2, 0.5)
        form.addRow("Material", self.material)
        form.addRow("Doping", self.doping)
        form.addRow("Crystal length", self.length)
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
        self._show_material(spec.material, spec.material_overrides)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.material = self.material.currentData()
        spec.doping = self.doping.si()
        spec.crystal_length = self.length.si()
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
    help_text = ("Describe the focused pump beam inside the crystal. Fibre-coupled diodes are "
                 "best described by their M² (fibre radius × NA × π / λ).")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self._header(left)
        form = QFormLayout()
        self.power = UnitSpin(20, 1.0, "W", 0.01, 1e5, 2, 1)
        self.waist = UnitSpin(200e-6, UM, "µm", 1, 1e5, 1, 10)
        self.m2 = UnitSpin(30, 1.0, "", 1, 1e4, 1, 5)
        self.position = UnitSpin(1e-3, MM, "mm", -100, 100, 2, 0.5)
        self.passes = QComboBox()
        self.passes.addItems(["Single pass", "Double pass"])
        self.alpha_override = UnitSpin(0, CM ** -1, "/cm", 0, 1e4, 2, 0.5)
        self.alpha_override.setSpecialValueText("from material")
        form.addRow("Pump power", self.power)
        form.addRow("Waist radius", self.waist)
        form.addRow("Beam quality M²", self.m2)
        form.addRow("Waist depth in crystal", self.position)
        form.addRow("Pumping", self.passes)
        form.addRow("Effective absorption", self.alpha_override)
        left.addLayout(form)
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
        for w in (self.power, self.waist, self.m2, self.position, self.alpha_override):
            w.valueChanged.connect(self._emit)
        self.passes.currentIndexChanged.connect(self._emit)

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.power.set_si(spec.pump_power)
        self.waist.set_si(spec.pump_waist)
        self.m2.set_si(spec.pump_m2)
        self.position.set_si(spec.pump_waist_position)
        self.passes.setCurrentIndex(spec.pump_passes - 1)
        self.alpha_override.set_si(spec.effective_absorption or 0.0)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.pump_power = self.power.si()
        spec.pump_waist = self.waist.si()
        spec.pump_m2 = self.m2.si()
        spec.pump_waist_position = self.position.si()
        spec.pump_passes = self.passes.currentIndex() + 1
        a = self.alpha_override.si()
        spec.effective_absorption = a if a > 0 else None

    def refresh(self, spec: DesignSpec) -> None:
        try:
            laser = build_laser(spec)
        except ValueError as exc:
            self.info.setText(f"<span style='color:#b00'>{exc}</span>")
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


# ====================================================================== #
# 3. Resonator
# ====================================================================== #
ELEMENT_LABELS = {"crystal": "Gain crystal", "space": "Air gap", "mirror": "Fold mirror",
                  "lens": "Thin lens", "medium": "Medium / Q-switch", "brewster": "Brewster plate"}
COLS = ["Element", "Name", "Length [mm]", "R or f [mm]", "Angle [°]", "Index n"]


class ResonatorPage(Page):
    title = "3. Resonator"
    help_text = ("List the elements met going from end mirror 1 (usually the pumped face) to "
                 "end mirror 2. The plots show the TEM00 mode at full pump power and how the "
                 "stability parameter m = (A+D)/2 moves as the thermal lens changes; the "
                 "resonator is stable for −1 < m < 1.")

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self._header(left)
        form = QFormLayout()
        self.r1 = RadiusInput()
        self.r2 = RadiusInput()
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
    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.r1.set_si(spec.R1)
        self.r2.set_si(spec.R2)
        self._set_elements(spec.elements)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
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
            for plane, ls in (("t", "-"), ("s", "--")):
                prof = cav.mode_profile(plane)
                a1.plot(prof.z / MM, prof.w / UM, ls,
                        label="tangential" if plane == "t" else "sagittal")
            a1.axvspan(0, 0, alpha=0)
            a1.set(xlabel="distance from mirror 1 [mm]", ylabel="w [µm]",
                   title=f"TEM00 mode at {spec.pump_power:.3g} W pump")
            a1.legend(fontsize=8)
            w_l = cav.spot_size_at("crystal thermal lens")
            text = (f"<b>Stable</b> at {spec.pump_power:.3g} W: m = "
                    f"{cav.stability_parameter('t'):.3f} (t), {cav.stability_parameter('s'):.3f} (s)<br>"
                    f"Mode radius in crystal {w_l / UM:.0f} µm vs pump {laser.pump_radius / UM:.0f} µm "
                    f"(ratio {w_l / laser.pump_radius:.2f})<br>"
                    f"On mirror 1: {cav.spot_size_on_mirror(1) / UM:.0f} µm, mirror 2: "
                    f"{cav.spot_size_on_mirror(2) / UM:.0f} µm<br>")
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
class OperationPage(Page):
    title = "4. Operation"
    help_text = ("Choose the output coupling, the other losses and how the laser is run: "
                 "continuous wave, actively Q-switched with CW pumping, or SESAM mode-locked "
                 "(SESAM as end mirror 2).")

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
        for i, (key, label) in enumerate((("cw", "Continuous wave"),
                                          ("qswitch", "Q-switched"),
                                          ("modelock", "SESAM mode-locked"))):
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
        mlw = QWidget()
        mf = QFormLayout(mlw)
        self.fsat = UnitSpin(0.6, 1e-2, "µJ/cm²", 0.1, 1e5, 1, 5)
        self.dr = UnitSpin(0.01, 0.01, "%", 0.01, 50, 2, 0.1)
        mf.addRow("SESAM saturation fluence", self.fsat)
        mf.addRow("SESAM modulation depth", self.dr)
        self.stack.addWidget(mlw)
        lay.addWidget(self.stack)
        self.info = info_label()
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.group.idClicked.connect(self._mode_changed)
        for w in (self.oc, self.loss, self.rep_rate, self.fsat, self.dr):
            w.valueChanged.connect(self._emit)

    def _mode_changed(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self._emit()

    def mode(self) -> str:
        return ("cw", "qswitch", "modelock")[max(self.group.checkedId(), 0)]

    def load(self, spec: DesignSpec) -> None:
        self._loading = True
        self.oc.set_si(spec.output_coupling)
        self.loss.set_si(spec.passive_loss)
        self.radios[spec.mode].setChecked(True)
        self.stack.setCurrentIndex(("cw", "qswitch", "modelock").index(spec.mode))
        self.rep_rate.set_si(spec.rep_rate)
        self.fsat.set_si(spec.sesam_saturation_fluence)
        self.dr.set_si(spec.sesam_modulation_depth)
        self._loading = False

    def store(self, spec: DesignSpec) -> None:
        spec.output_coupling = self.oc.si()
        spec.passive_loss = self.loss.si()
        spec.mode = self.mode()
        spec.rep_rate = self.rep_rate.si()
        spec.sesam_saturation_fluence = self.fsat.si()
        spec.sesam_modulation_depth = self.dr.si()

    def refresh(self, spec: DesignSpec) -> None:
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
        self.info.setText(text)


# ====================================================================== #
# 5. Results
# ====================================================================== #
class ResultsPage(Page):
    title = "5. Results"
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
            ("Laser / pump radius in crystal",
             f"{op.laser_radius / UM:.0f} / {op.pump_radius / UM:.0f} µm"),
            ("CW threshold", f"{op.threshold:.3g} W"),
            ("CW output power", f"{op.output_power:.3g} W"),
            ("Optical efficiency", f"{op.output_power / p * 100:.1f} %"),
            ("M² estimate", f"{op.m2_estimate:.2f} (aberration {op.m2_aberration:.2f}, "
                            f"multimode {op.m2_multimode:.2f})"),
        ]
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

        else:  # modelock
            res = laser.sesam_mode_locked(p, spec.sesam_saturation_fluence,
                                          spec.sesam_modulation_depth)
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
                                                      spec.sesam_modulation_depth)["check"])
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


ALL_PAGES = (GainMediumPage, PumpPage, ResonatorPage, OperationPage, ResultsPage)
