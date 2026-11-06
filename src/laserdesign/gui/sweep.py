"""Plot a Results quantity against one of the inputs that set it.

The Results step of both front ends (the Qt wizard and the browser app) lets
the user pick a reported quantity, pick one of its principal inputs (the
ones :mod:`laserdesign.gui.influences` lists for that row) and see how the
quantity changes as that input is swept, with everything else held at the
current design.

Two tables drive this, both keyed like the influence rules ("label" or
"mode:label"):

* :data:`QUANTITIES` says how to compute each Results quantity as numbers
  (in display units) for a :class:`~laserdesign.gui.spec.DesignSpec`;
* :func:`sweep_inputs` turns the influence keys of a row into
  :class:`SweepInput` objects that can read and set the input on a copy of
  the spec. Inputs that are not continuous numbers (material choice, element
  locations, Brewster cut, ...) are left out; the ``"elements"`` entry is
  expanded into the individual air gaps, curved mirrors and lenses.

:func:`sweep` returns plain data, so the Qt page draws it with matplotlib
and the web app with its SVG plotter.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .. import modelocking
from .influences import influences
from .spec import DesignSpec, absorber, build_laser, kerr_model, library_location

UM, MM = 1e-6, 1e-3
DEFAULT_POINTS = 25


# ---------------------------------------------------------------------- #
# Inputs
# ---------------------------------------------------------------------- #
@dataclass
class SweepInput:
    """A continuous design input that can be swept.

    ``scale`` is one display unit in SI (``1e-3`` for mm). ``bounds`` are
    the allowed SI values (``None`` for open), ``lo``/``hi`` the default
    sweep range in SI.
    """

    key: str
    name: str
    unit: str
    scale: float
    get: Callable[[DesignSpec], float]
    set: Callable[[DesignSpec, float], None]
    lo: float
    hi: float
    bounds: tuple[float | None, float | None] = (None, None)
    log: bool = False
    step: str = ""  #: wizard step, e.g. "2. Pump" (set by :func:`sweep_inputs`)

    @property
    def label(self) -> str:
        """Axis label, e.g. ``"Pump power [W]"``."""
        return f"{self.name} [{self.unit}]" if self.unit else self.name

    def clip(self, value: float) -> float:
        lo, hi = self.bounds
        if lo is not None:
            value = max(value, lo)
        if hi is not None:
            value = min(value, hi)
        return value

    def to_dict(self, spec: DesignSpec) -> dict:
        """JSON-friendly description in display units (for the web app)."""
        lo, hi = self.bounds
        return {"key": self.key, "name": self.name, "unit": self.unit, "label": self.label,
                "step": self.step,
                "value": self.get(spec) / self.scale, "lo": self.lo / self.scale,
                "hi": self.hi / self.scale, "log": self.log,
                "min": None if lo is None else lo / self.scale,
                "max": None if hi is None else hi / self.scale}


def _range(x: float, down: float, up: float) -> tuple[float, float]:
    a, b = x * down, x * up
    return (a, b) if a <= b else (b, a)


def _attr(key, name, unit, scale, down=0.25, up=2.0, bounds=(None, None), log=False,
          span: Callable[[DesignSpec, float], tuple[float, float]] | None = None):
    """An input stored as a plain :class:`DesignSpec` attribute."""

    def make(spec: DesignSpec) -> SweepInput | None:
        x = getattr(spec, key)
        if x is None or not math.isfinite(x) or (x == 0 and span is None):
            return None
        lo, hi = span(spec, x) if span else _range(x, down, up)

        def set_(s, v):
            setattr(s, key, v)
        inp = SweepInput(key, name, unit, scale, lambda s: getattr(s, key), set_, lo, hi,
                         bounds, log)
        inp.lo, inp.hi = inp.clip(lo), inp.clip(hi)
        return inp
    return make


def _material(key, attr, name, unit, scale, bounds=(None, None), down=0.5, up=2.0):
    """A gain-medium property, swept through ``material_overrides``."""

    def make(spec: DesignSpec) -> SweepInput | None:
        x = getattr(spec.gain_medium(), attr)
        if not x:
            return None

        def set_(s, v):
            s.material_overrides = {**s.material_overrides, attr: v}
        lo, hi = _range(x, down, up)
        inp = SweepInput(key, name, unit, scale, lambda s: getattr(s.gain_medium(), attr),
                         set_, lo, hi, bounds)
        inp.lo, inp.hi = inp.clip(lo), inp.clip(hi)
        return inp
    return make


def _absorption(spec: DesignSpec) -> SweepInput:
    def get(s):
        if s.effective_absorption is not None:
            return s.effective_absorption
        return s.gain_medium().pump_absorption_coefficient(s.doping)

    def set_(s, v):
        s.effective_absorption = v
    lo, hi = _range(get(spec), 0.25, 2.0)
    return SweepInput("effective_absorption", "Pump absorption coefficient", "/cm", 100.0,
                      get, set_, lo, hi, (1e-6, None))


def _heat_fraction(spec: DesignSpec) -> SweepInput:
    def get(s):
        return s.gain_medium().effective_heat_fraction

    def set_(s, v):
        s.material_overrides = {**s.material_overrides, "heat_fraction": v}
    x = get(spec)
    return SweepInput("heat_fraction", "Heat fraction", "", 1.0, get, set_,
                      max(0.01, x * 0.5), min(1.0, x * 2), (1e-3, 1.0))


def _element_name(spec: DesignSpec, i: int, kind: str) -> str:
    e = spec.elements[i]
    if e.get("name"):
        return f"{kind} “{e['name']}”"
    same = [j for j, o in enumerate(spec.elements) if o.get("type") == e.get("type")]
    return f"{kind} {same.index(i) + 1}" if len(same) > 1 else kind


def _elements(spec: DesignSpec) -> list[SweepInput]:
    """Air gaps, fold-mirror radii and lens focal lengths in the resonator."""
    out = []
    for i, e in enumerate(spec.elements):
        t = e.get("type")
        field_, kind = {"space": ("length", "Air gap"), "mirror": ("R", "Fold mirror radius"),
                        "lens": ("f", "Lens focal length"),
                        "medium": ("length", "Medium length")}.get(t, (None, None))
        if field_ is None:
            continue
        x = float(e.get(field_, math.inf))
        if not math.isfinite(x) or x == 0:
            continue

        def get(s, i=i, f=field_):
            return float(s.elements[i][f])

        def set_(s, v, i=i, f=field_):
            s.elements[i] = {**s.elements[i], f: v}
        lo, hi = _range(x, 0.8, 1.25) if field_ != "length" else (x * 0.25, x * 2.0)
        bounds = (0.0, None) if field_ == "length" else (None, None)
        out.append(SweepInput(f"elements:{i}", _element_name(spec, i, kind), "mm", MM,
                              get, set_, lo, hi, bounds))
    return out


def _mirror(key: str, name: str):
    def make(spec: DesignSpec) -> SweepInput | None:
        if spec.cavity_type == "ring":
            return None
        return _attr(key, name, "mm", MM, 0.5, 2.0)(spec)
    return make


def _optional(key, name, unit, scale, bounds):
    def make(spec: DesignSpec) -> SweepInput | None:
        if getattr(spec, key) is None:
            return None
        return _attr(key, name, unit, scale, 0.5, 2.0, bounds)(spec)
    return make


def _pump_depth(spec, x):
    return 0.0, spec.crystal_length


def _fraction_span(down, up, cap):
    def span(spec, x):
        return x * down, min(cap, x * up)
    return span


def _loss_span(spec, x):
    return 0.0, max(0.05, 3 * x)


def _t0_span(spec, x):
    return max(0.3, x - 0.3), min(0.98, x + 0.1)


_FACTORIES = {
    # 1. Gain medium
    "doping": lambda s: _attr("doping", "Doping", s.gain_medium().doping_unit, 1.0,
                              bounds=(1e-9, None))(s),
    "crystal_length": _attr("crystal_length", "Crystal / rod length", "mm", MM,
                            bounds=(1e-6, None)),
    "emission_cross_section": _material("emission_cross_section", "emission_cross_section",
                                        "Emission cross section", "×10⁻¹⁹ cm²", 1e-23),
    "upper_state_lifetime": _material("upper_state_lifetime", "upper_state_lifetime",
                                      "Upper-state lifetime", "µs", 1e-6),
    "refractive_index": _material("refractive_index", "refractive_index", "Refractive index",
                                  "", 1.0, (1.0, None), 0.85, 1.15),
    "dn_dT": _material("dn_dT", "dn_dT", "dn/dT", "×10⁻⁶ /K", 1e-6),
    "thermal_conductivity": _material("thermal_conductivity", "thermal_conductivity",
                                      "Thermal conductivity", "W/(m·K)", 1.0),
    "pump_absorption_cross_section": _material("pump_absorption_cross_section",
                                               "pump_absorption_cross_section",
                                               "Pump absorption cross section", "×10⁻²⁰ cm²",
                                               1e-24),
    "gain_bandwidth": _material("gain_bandwidth", "gain_bandwidth", "Gain bandwidth", "GHz",
                                1e9),
    "heat_fraction": _heat_fraction,
    "n2": _material("n2", "nonlinear_index", "Nonlinear index n₂", "×10⁻²⁰ m²/W", 1e-20),
    "gvd": _material("gvd", "gvd", "Group velocity dispersion", "fs²/mm", 1e-27),
    # 2. Pump
    "pump_power": _attr("pump_power", "Pump power", "W", 1.0, 0.1, 2.0, (1e-6, None)),
    "pump_waist": _attr("pump_waist", "Pump waist radius", "µm", UM, bounds=(1e-7, None)),
    "pump_m2": _attr("pump_m2", "Pump beam quality M²", "", 1.0, bounds=(1.0, None),
                     span=lambda s, x: (1.0, max(2.0, 2 * x))),
    "pump_waist_position": _attr("pump_waist_position", "Pump waist depth in crystal", "mm",
                                 MM, span=_pump_depth),
    "effective_absorption": _absorption,
    "rod_radius": _attr("rod_radius", "Rod radius", "mm", MM, 0.5, 2.0, (1e-5, None)),
    "absorption_efficiency": _attr("absorption_efficiency", "Absorption efficiency", "%", 0.01,
                                   bounds=(1e-3, 1.0), span=_fraction_span(0.25, 2.0, 1.0)),
    "multimode_fill": _optional("multimode_fill", "Multimode fill", "", 1.0, (1e-3, 1.0)),
    # 3. Resonator
    "R1": _mirror("R1", "End mirror 1 radius"),
    "R2": _mirror("R2", "End mirror 2 radius"),
    # 4. Operation
    "output_coupling": _attr("output_coupling", "Output coupler transmission", "%", 0.01,
                             bounds=(1e-4, 0.99), span=_fraction_span(0.2, 3.0, 0.95)),
    "passive_loss": _attr("passive_loss", "Other round-trip losses", "%", 0.01,
                          bounds=(0.0, 0.99), span=_loss_span),
    "rep_rate": _attr("rep_rate", "Repetition rate", "kHz", 1e3, 0.1, 10.0, (1.0, None),
                      log=True),
    "absorber_transmission": _attr("absorber_transmission", "Initial transmission T0", "%",
                                   0.01, bounds=(0.01, 0.995), span=_t0_span),
    "sesam_saturation_fluence": _attr("sesam_saturation_fluence", "SESAM saturation fluence",
                                      "µJ/cm²", 1e-2, bounds=(1e-6, None)),
    "sesam_modulation_depth": _attr("sesam_modulation_depth", "SESAM modulation depth", "%",
                                    0.01, bounds=(1e-5, 0.9)),
    "klm_pulse_width": _attr("klm_pulse_width", "Target pulse width", "fs", 1e-15,
                             bounds=(1e-16, None)),
}


def sweep_inputs(label: str, spec: DesignSpec) -> list[SweepInput]:
    """The inputs of Results row ``label`` that can be swept, in wizard order.

    Empty when the row has no numeric quantity (see :func:`can_plot`).
    """
    if quantity(label, spec) is None:
        return []
    info = influences(label, spec)
    if info is None:
        return []
    out = []
    for d in info["inputs"]:
        key = d["key"]
        if key == "elements":
            for inp in _elements(spec):
                inp.step = d["step"]
                out.append(inp)
            continue
        make = _FACTORIES.get(key)
        if make is None:
            continue
        try:
            inp = make(spec)
        except (KeyError, ValueError, TypeError, AttributeError):
            inp = None
        if inp is not None:
            inp.step = d["step"]
            out.append(inp)
    return out


def find_input(label: str, key: str, spec: DesignSpec) -> SweepInput:
    for inp in sweep_inputs(label, spec):
        if inp.key == key:
            return inp
    raise KeyError(f"{key!r} is not a sweepable input of {label!r}")


# ---------------------------------------------------------------------- #
# Quantities
# ---------------------------------------------------------------------- #
class _Point:
    """One design, with the expensive pieces computed on first use."""

    def __init__(self, spec: DesignSpec):
        self.spec = spec
        self.laser = build_laser(spec)
        self.op = self.laser.analyze(spec.pump_power)
        if not self.op.stable:
            raise ValueError("unstable")
        self._cache: dict = {}

    def _get(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    @property
    def qs(self):
        s = self.spec
        return self._get("qs", lambda: self.laser.q_switched(s.pump_power, s.rep_rate))

    @property
    def passive(self):
        s = self.spec
        return self._get("passive", lambda: self.laser.passively_q_switched(
            s.pump_power, s.absorber_transmission, absorber(s),
            library_location(s.absorber_location)))

    @property
    def sesam(self):
        s = self.spec
        return self._get("sesam", lambda: self.laser.sesam_mode_locked(
            s.pump_power, s.sesam_saturation_fluence, s.sesam_modulation_depth,
            library_location(s.sesam_location)))

    @property
    def km(self):
        return self._get("km", lambda: kerr_model(
            self.spec, self.laser.thermal_focal_length(self.spec.pump_power)))

    def strength(self, where: str, plane: str) -> float:
        loc = library_location(self.spec.klm_aperture) if where == "aperture" else "crystal"
        return self._get(("klm", where, plane), lambda: self.km.klm_strength(loc, plane))

    @property
    def f_rep(self) -> float:
        def make():
            cav = self.laser.resonator(self.spec.pump_power)
            return modelocking.repetition_rate(cav.optical_length, ring=self.op.gain_passes == 1)
        return self._get("f_rep", make)

    @property
    def pulse_energy(self) -> float:
        return self.op.circulating_power / self.f_rep

    @property
    def soliton_gdd(self) -> float:
        def make():
            km = self.km
            sol0 = km.solve(0.0)
            w_x = km.spot_size(sol0, "crystal", "t") * (km.n if km.brewster else 1.0)
            w_y = km.spot_size(sol0, "crystal", "s")
            spm = modelocking.spm_coefficient(km.n2, km.crystal_length, np.pi * w_x * w_y,
                                              km.wavelength, passes=self.op.gain_passes)
            return modelocking.soliton_required_gdd(self.spec.klm_pulse_width, spm,
                                                    self.pulse_energy)
        return self._get("gdd", make)

    @property
    def crystal_gdd(self) -> float:
        return self.op.gain_passes * (self.laser.material.gvd or 0.0) * self.spec.crystal_length


@dataclass
class Quantity:
    """How to compute a Results row as numbers: axis label and named series."""

    ylabel: str
    series: list[tuple[str, Callable[[_Point], float]]]


def _q(ylabel, fn, name=""):
    return Quantity(ylabel, [(name, fn)])


FS2 = 1e-30

#: Results rows that can be plotted, keyed like the influence rules.
QUANTITIES: dict[str, Quantity] = {
    "Absorbed power": _q("absorbed power [W]", lambda p: p.op.absorbed_power),
    "Heat load": _q("heat load [W]", lambda p: p.op.heat_power),
    "Thermal focal length": _q("thermal focal length [mm]",
                               lambda p: p.op.thermal_focal_length / MM),
    "Stability parameter m": _q("m = (A+D)/2", lambda p: p.op.stability_parameter),
    "Laser / pump radius in crystal": Quantity("radius in crystal [µm]", [
        ("laser", lambda p: p.op.laser_radius / UM),
        ("pump", lambda p: p.op.pump_radius / UM)]),
    "CW threshold": _q("CW threshold [W]", lambda p: p.op.threshold),
    "CW output power": _q("CW output [W]", lambda p: p.op.output_power),
    "Optical efficiency": _q("optical efficiency [%]",
                             lambda p: p.op.output_power / p.spec.pump_power * 100),
    "M² estimate": Quantity("M²", [("combined", lambda p: p.op.m2_estimate),
                                   ("thermal aberration", lambda p: p.op.m2_aberration),
                                   ("pump/mode ratio", lambda p: p.op.m2_multimode)]),
    "Rod clipping loss (round trip)": _q("clipping loss [%]",
                                         lambda p: p.op.aperture_loss * 100),
    # Active Q-switching
    "Initial inversion / threshold": _q("initial inversion / threshold",
                                        lambda p: p.qs["initial_ratio"]),
    "qswitch:Pulse energy": _q("pulse energy [mJ]", lambda p: p.qs["energy"] * 1e3),
    "qswitch:Pulse width (E / P_peak)": _q("pulse width [ns]",
                                           lambda p: p.qs["pulse_width"] * 1e9),
    "qswitch:Peak power": _q("peak power [kW]", lambda p: p.qs["peak_power"] / 1e3),
    "qswitch:Average power": _q("average power [W]", lambda p: p.qs["average_power"]),
    # Passive Q-switching
    "Absorber spot radius": _q("absorber spot radius [µm]",
                               lambda p: p.passive["absorber_radius"] / UM),
    "Bleaching criterion (needs > 1)": _q("bleaching criterion",
                                          lambda p: p.passive["pulse"].bleaching_criterion),
    "Threshold with absorber": _q("threshold with absorber [W]",
                                  lambda p: p.passive["threshold"]),
    "passive:Pulse energy": _q("pulse energy [mJ]", lambda p: p.passive["energy"] * 1e3),
    "passive:Pulse width (E / P_peak)": _q("pulse width [ns]",
                                           lambda p: p.passive["pulse_width"] * 1e9),
    "passive:Peak power": _q("peak power [kW]", lambda p: p.passive["peak_power"] / 1e3),
    "passive:Repetition rate": _q("repetition rate [kHz]",
                                  lambda p: p.passive["rep_rate"] / 1e3),
    "passive:Average power": _q("average power [W]", lambda p: p.passive["average_power"]),
    # SESAM mode locking
    "modelock:Repetition rate": _q("repetition rate [MHz]",
                                   lambda p: p.sesam["check"].repetition_rate / 1e6),
    "modelock:Intracavity pulse energy": _q("intracavity pulse energy [nJ]",
                                            lambda p: p.sesam["check"].pulse_energy * 1e9),
    "QML threshold": _q("QML threshold [nJ]", lambda p: p.sesam["check"].qml_threshold * 1e9),
    "QML margin": _q("QML margin", lambda p: p.sesam["check"].qml_margin),
    "SESAM spot radius": _q("SESAM spot radius [µm]",
                            lambda p: p.sesam["absorber_radius"] / UM),
    "SESAM saturation E_p / E_sat,A": _q("E_p / E_sat,A",
                                         lambda p: p.sesam["check"].absorber_saturation),
    "Pulse width estimate": _q("pulse width [ps]",
                               lambda p: p.sesam["check"].pulse_width_estimate * 1e12),
    "Transform limit": _q("transform limit [ps]",
                          lambda p: p.sesam["check"].transform_limit * 1e12),
    # Kerr-lens mode locking
    "Critical power P_cr": _q("P_cr [MW]", lambda p: p.km.critical_power / 1e6),
    "KLM strength at aperture (t / s)": Quantity("δ = (1/w) dw/dp at aperture", [
        ("t", lambda p: p.strength("aperture", "t")),
        ("s", lambda p: p.strength("aperture", "s"))]),
    "KLM strength in crystal (t / s)": Quantity("δ = (1/w) dw/dp in crystal", [
        ("t", lambda p: p.strength("crystal", "t")),
        ("s", lambda p: p.strength("crystal", "s"))]),
    "klm:Repetition rate": _q("repetition rate [MHz]", lambda p: p.f_rep / 1e6),
    "klm:Intracavity pulse energy": _q("intracavity pulse energy [nJ]",
                                       lambda p: p.pulse_energy * 1e9),
    "Peak power / P_cr": _q("peak power / P_cr",
                            lambda p: 0.88 * p.pulse_energy / p.spec.klm_pulse_width
                            / p.km.critical_power),
    "Soliton net GDD per round trip": _q("soliton net GDD [fs²]",
                                         lambda p: p.soliton_gdd / FS2),
    "Crystal GDD per round trip": _q("crystal GDD [fs²]", lambda p: p.crystal_gdd / FS2),
    "Compensation needed (prisms, mirrors)": _q("compensation needed [fs²]",
                                                lambda p: (p.soliton_gdd - p.crystal_gdd)
                                                / FS2),
}


def quantity(label: str, spec: DesignSpec) -> Quantity | None:
    """How to compute Results row ``label`` for this design (None: not numeric)."""
    return QUANTITIES.get(f"{spec.mode}:{label}") or QUANTITIES.get(label)


def can_plot(label: str, spec: DesignSpec) -> bool:
    """True when ``label`` is a numeric quantity with at least one sweepable input."""
    return bool(sweep_inputs(label, spec))


def evaluate(label: str, spec: DesignSpec) -> list[float]:
    """The numbers behind Results row ``label`` (NaN where they can't be found)."""
    q = quantity(label, spec)
    if q is None:
        raise KeyError(f"{label!r} has no numeric quantity")
    try:
        point = _Point(spec)
    except Exception:  # invalid or unstable design at this input value
        return [math.nan] * len(q.series)
    out = []
    for _, fn in q.series:
        try:
            v = float(fn(point))
        except Exception:
            v = math.nan
        out.append(v if math.isfinite(v) else math.nan)
    return out


def sweep(label: str, key: str, spec: DesignSpec, lo: float | None = None,
          hi: float | None = None, points: int = DEFAULT_POINTS,
          log: bool | None = None, refine: bool = True) -> dict:
    """Sweep input ``key`` of Results row ``label`` and evaluate the row.

    ``lo`` and ``hi`` are in the input's display units (defaults: the
    input's default range). Points where the design fails (for example an
    unstable resonator) are NaN. With ``refine``, when fewer than half the
    points have a result, another ``points`` are spent on the part of the
    range that has one (a resonator's stable window can be narrow).

    Returns
    -------
    dict
        ``{"title", "xlabel", "ylabel", "x": [...], "series": [{"label", "y"}],
        "current": x of the current design, "current_y": [...], "xlog": bool,
        "lo", "hi": the range swept, "unstable": number of points with no
        result, "refined": [lo, hi] of the second pass or None}``, x in
        display units.
    """
    inp = find_input(label, key, spec)
    q = quantity(label, spec)
    lo_si = inp.lo if lo is None else lo * inp.scale
    hi_si = inp.hi if hi is None else hi * inp.scale
    lo_si, hi_si = sorted((inp.clip(lo_si), inp.clip(hi_si)))
    if hi_si == lo_si:
        raise ValueError("The sweep range is empty")
    log = inp.log if log is None else log
    points = max(2, min(int(points), 200))
    if log and lo_si > 0:
        xs = np.geomspace(lo_si, hi_si, points)
    else:
        log = False
        xs = np.linspace(lo_si, hi_si, points)
    def run(values):
        out = []
        for x in values:
            s = copy.deepcopy(spec)
            inp.set(s, float(x))
            out.append(evaluate(label, s))
        return np.array(out, dtype=float).reshape(len(values), len(q.series))

    ys = run(xs)
    ok = ~np.all(np.isnan(ys), axis=1)
    refined = None
    if refine and 0 < ok.sum() < len(xs) / 2:
        # Most of the range has no result (typically an unstable resonator):
        # sweep again across the part that has one, so its curve is resolved.
        i0, i1 = np.flatnonzero(ok)[[0, -1]]
        a, b = xs[max(i0 - 1, 0)], xs[min(i1 + 1, len(xs) - 1)]
        extra = np.geomspace(a, b, points) if log else np.linspace(a, b, points)
        extra = extra[~np.isin(extra, xs)]
        xs = np.concatenate([xs, extra])
        ys = np.concatenate([ys, run(extra)])
        order = np.argsort(xs)
        xs, ys = xs[order], ys[order]
        refined = [float(a) / inp.scale, float(b) / inp.scale]
    bad = int(np.sum(np.all(np.isnan(ys), axis=1)))
    what = inp.name if inp.name[1:2].isupper() else inp.name[:1].lower() + inp.name[1:]
    return {"title": f"{label} vs {what}",
            "xlabel": inp.label, "ylabel": q.ylabel,
            "x": [float(x) / inp.scale for x in xs],
            "series": [{"label": name, "y": [float(v) for v in ys[:, i]]}
                       for i, (name, _) in enumerate(q.series)],
            "current": inp.get(spec) / inp.scale, "current_y": evaluate(label, spec),
            "xlog": bool(log), "lo": lo_si / inp.scale, "hi": hi_si / inp.scale,
            "unstable": bad, "refined": refined}
