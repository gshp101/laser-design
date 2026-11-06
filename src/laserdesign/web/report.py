"""Step-by-step reports for a :class:`~laserdesign.gui.spec.DesignSpec`.

These functions compute what each wizard step shows (summary text, a table
of results and the data for the plots) and return plain dictionaries of
numbers and strings, so any front end can draw them. The browser version
(:mod:`laserdesign.web.api`, run under Pyodide) uses them; nothing here
needs Qt or matplotlib.

Every report has the same shape::

    {"info": [html line, ...],      # short summary lines (trusted HTML)
     "rows": [[label, value], ...], # result table (plain text)
     "plots": [plot, ...],          # see below
     "notes": [{"level": "warn" | "info", "text": html}, ...],
     "error": str | None}

and a plot is::

    {"title": str, "xlabel": str, "ylabel": str, "y2label": str | None,
     "xlog": bool, "ylog": bool, "ylim": [lo, hi] | None,
     "series": [{"x": [...], "y": [...], "label": str, "dash": "solid" | "dash" | "dot",
                 "axis": "y" | "y2", "markers": bool, "color": int | None}],
     "hlines": [{"y": float, "axis": "y" | "y2", "dash": str, "label": str}],
     "vlines": [{"x": float, "label": str}], "hspan": [lo, hi] | None, "message": str | None}

The physics and wording follow the Qt wizard in :mod:`laserdesign.gui.pages`.
"""

from __future__ import annotations

import html
import math

import numpy as np

from .. import gain, modelocking, pump, thermal
from ..abcd import StandingWaveCavity
from ..design import SidePumpedRodLaser
from ..gui.spec import (
    CRYSTAL_LENS_NAME,
    DesignSpec,
    absorber,
    build_laser,
    kerr_model,
    library_location,
    round_trip_mode,
)

UM, MM, CM = 1e-6, 1e-3, 1e-2

STEPS = ("gain_medium", "pump", "resonator", "operation", "results")

#: Editable material properties: (attribute, label, display scale, unit, decimals).
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

DISCLAIMER = "<i>Results come from idealised models; see the theory pages for their assumptions.</i>"


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _report(**kw) -> dict:
    out = {"info": [], "rows": [], "plots": [], "notes": [], "error": None}
    out.update(kw)
    return out


def _err(text: str) -> str:
    return f"<span class='bad'>{text}</span>"


def _list(values) -> list:
    return [float(v) for v in np.asarray(values, dtype=float).ravel()]


def series(x, y, label: str = "", dash: str = "solid", axis: str = "y",
           markers: bool = False, color: int | None = None) -> dict:
    return {"x": _list(x), "y": _list(y), "label": label, "dash": dash, "axis": axis,
            "markers": markers, "color": color}


def plot(title: str, xlabel: str, ylabel: str, *series_, y2label: str | None = None,
         xlog: bool = False, ylog: bool = False, ylim=None, hlines=(), vlines=(),
         hspan=None, message: str | None = None) -> dict:
    return {"title": title, "xlabel": xlabel, "ylabel": ylabel, "y2label": y2label,
            "xlog": xlog, "ylog": ylog, "ylim": list(ylim) if ylim is not None else None,
            "series": list(series_), "hlines": list(hlines),
            "vlines": [_vline(v) for v in vlines],
            "hspan": list(hspan) if hspan is not None else None, "message": message}


def _vline(v) -> dict:
    """``x`` or ``(x, label)`` -> ``{"x": x, "label": label}``."""
    x, label = v if isinstance(v, (tuple, list)) else (v, "")
    return {"x": float(x), "label": str(label)}


def hline(y: float, axis: str = "y", dash: str = "dot", label: str = "") -> dict:
    return {"y": float(y), "axis": axis, "dash": dash, "label": label}


def message_plot(text: str) -> dict:
    return plot("", "", "", message=text)


def _build(spec: DesignSpec):
    """Build the laser, or return an error report."""
    try:
        return build_laser(spec), None
    except (ValueError, KeyError) as exc:
        text = str(exc)
        return None, _report(error=text, info=[_err(html.escape(text))],
                             plots=[message_plot(text)])


# ---------------------------------------------------------------------- #
# 1. Gain medium
# ---------------------------------------------------------------------- #
def gain_medium(spec: DesignSpec) -> dict:
    try:
        mat = spec.gain_medium()
    except (KeyError, TypeError) as exc:
        return _report(error=str(exc), info=[_err(html.escape(str(exc)))])
    alpha = mat.pump_absorption_coefficient(spec.doping)
    absorbed = pump.absorbed_fraction(alpha, spec.crystal_length)
    kind = "quasi-three-level" if mat.is_quasi_three_level else "four-level"
    info = [
        f"<b>{html.escape(mat.name)}</b> ({kind}), λ<sub>laser</sub> = "
        f"{mat.laser_wavelength / 1e-9:.1f} nm, λ<sub>pump</sub> = "
        f"{mat.pump_wavelength / 1e-9:.1f} nm",
        f"Pump absorption coefficient α = {alpha / 100:.2f} /cm; single-pass absorption "
        f"{absorbed * 100:.1f} %",
        f"Saturation fluence {mat.saturation_fluence / 1e4:.3g} J/cm², saturation "
        f"intensity {mat.saturation_intensity / 1e7:.3g} kW/cm²",
        f"Heat fraction {mat.effective_heat_fraction:.2f}; σ·τ = "
        f"{mat.emission_cross_section * mat.upper_state_lifetime * 1e4 * 1e23:.3g}×10⁻²³ cm²·s "
        "(higher means lower threshold)",
    ]
    z = np.linspace(0, max(spec.crystal_length, 1e-6), 120)
    p = plot("Pump absorbed along the crystal (single pass)", "depth [mm]",
             "absorbed fraction [%]",
             series(z / MM, (1 - np.exp(-alpha * z)) * 100, "cumulative absorption"))
    return _report(info=info, plots=[p])


# ---------------------------------------------------------------------- #
# 2. Pump
# ---------------------------------------------------------------------- #
def pump_step(spec: DesignSpec) -> dict:
    laser, error = _build(spec)
    if error:
        return error
    if isinstance(laser, SidePumpedRodLaser):
        return _pump_side(spec, laser)
    mat = laser.material
    alpha = laser.absorption_coefficient
    eta = laser.absorbed_fraction
    w_eff = laser.pump_radius
    p_abs = spec.pump_power * eta
    p_heat = p_abs * mat.effective_heat_fraction
    f_th = laser.thermal_focal_length(spec.pump_power)
    n = mat.refractive_index
    z_r = np.pi * n * spec.pump_waist**2 / (spec.pump_m2 * mat.pump_wavelength)
    info = [
        f"Absorbed: <b>{p_abs:.2f} W</b> ({eta * 100:.1f} %), heat load {p_heat:.2f} W",
        f"Pump Rayleigh range in crystal: {z_r / MM:.2f} mm "
        f"(crystal {spec.crystal_length / MM:.1f} mm)",
        f"Absorption-weighted pump radius: <b>{w_eff / UM:.0f} µm</b>",
        f"Thermal focal length at full power: <b>{f_th / MM:.0f} mm</b>",
    ]
    z = np.linspace(0, spec.crystal_length, 200)
    w = laser.pump_beam.radius(z, n)
    p1 = plot("Pump beam in the crystal", "depth [mm]", "pump radius [µm]",
              series(z / MM, w / UM, "pump radius", color=0),
              series(z / MM, -w / UM, "", color=0),
              hlines=[hline(w_eff / UM, dash="dash", label="effective radius")])
    p2 = plot("Absorbed pump density", "depth [mm]", "absorbed [W/cm]",
              series(z / MM, alpha * np.exp(-alpha * z) * spec.pump_power / 100, color=2))
    return _report(info=info, plots=[p1, p2])


def _pump_side(spec: DesignSpec, laser: SidePumpedRodLaser) -> dict:
    mat = laser.material
    p_abs = spec.pump_power * laser.absorbed_fraction
    p_heat = p_abs * mat.effective_heat_fraction
    f = laser.thermal_focal_lengths(p_abs)
    fracture = laser.stress_fracture_pump() / laser.absorbed_fraction
    d_t = thermal.side_pumped_center_temperature(p_heat, spec.crystal_length,
                                                 mat.thermal_conductivity)
    info = [
        f"Absorbed: <b>{p_abs:.3g} W</b>, heat load {p_heat:.3g} W "
        f"({p_heat / (spec.crystal_length / CM):.3g} W/cm)",
        f"Centre-to-surface temperature rise {d_t:.3g} K",
        f"Thermal focal length: radial <b>{f['radial'] / MM:.0f} mm</b>, tangential "
        f"<b>{f['tangential'] / MM:.0f} mm</b> (dn/dT only {f['dn_dT'] / MM:.0f} mm)",
    ]
    if np.isfinite(fracture):
        info.append(f"Fracture limit at about {fracture:.3g} W of pump "
                    f"({spec.pump_power / fracture * 100:.0f} % of it; keep below 25 to 50 %)")
    powers = np.linspace(0.05, 1.25, 50) * spec.pump_power
    fl = [laser.thermal_focal_lengths(x * laser.absorbed_fraction) for x in powers]
    p1 = plot("Rod thermal lens (bifocusing)", "pump power [W]", "focal length [mm]",
              *[series(powers, [x[key] / MM for x in fl], key, dash)
                for key, dash in (("radial", "solid"), ("tangential", "dash"),
                                  ("average", "dot"))],
              ylog=True, vlines=[spec.pump_power])
    r = np.linspace(0, spec.rod_radius, 100)
    p2 = plot("Temperature profile at full pump", "radius [mm]", "ΔT [K]",
              series(r / MM, d_t * (1 - (r / spec.rod_radius) ** 2), color=3))
    return _report(info=info, plots=[p1, p2])


# ---------------------------------------------------------------------- #
# 3. Resonator
# ---------------------------------------------------------------------- #
def resonator(spec: DesignSpec) -> dict:
    laser, error = _build(spec)
    if error:
        return error
    powers = np.linspace(0.02, 1.25, 60) * spec.pump_power
    cavs = [laser.resonator(x) for x in powers]
    m_t = [c.stability_parameter("t") for c in cavs]
    m_s = [c.stability_parameter("s") for c in cavs]
    stable_p = [x for x, c in zip(powers, cavs) if c.is_stable()]
    cav = laser.resonator(spec.pump_power)
    info, plots = [], []
    standing = isinstance(cav, StandingWaveCavity)
    if cav.is_stable():
        trip = round_trip_mode(cav)
        mode = [series(trip[plane].z / MM, trip[plane].w / UM,
                       "tangential" if plane == "t" else "sagittal",
                       "solid" if plane == "t" else "dash")
                for plane in ("t", "s")]
        top = max(float(trip[p].w.max()) for p in ("t", "s")) / UM
        plots.append(plot(f"{trip['title']} at {spec.pump_power:.3g} W pump",
                          trip["xlabel"], "w [µm]", *mode, ylim=(0, 1.08 * top),
                          vlines=[(z / MM, label) for z, label in trip["landmarks"]]))
        w_l = cav.spot_size_at(CRYSTAL_LENS_NAME)
        pump_kind = "rod" if isinstance(laser, SidePumpedRodLaser) else "pump"
        info.append(f"<b>Stable</b> at {spec.pump_power:.3g} W: m = "
                    f"{cav.stability_parameter('t'):.3f} (t), "
                    f"{cav.stability_parameter('s'):.3f} (s)")
        info.append(f"Mode radius in crystal {w_l / UM:.0f} µm vs {pump_kind} "
                    f"{laser.pump_radius / UM:.0f} µm (ratio {w_l / laser.pump_radius:.2f})")
        if standing:
            info.append(f"On mirror 1: {cav.spot_size_on_mirror(1) / UM:.0f} µm, mirror 2: "
                        f"{cav.spot_size_on_mirror(2) / UM:.0f} µm")
        else:
            named = [e.name for e in cav.elements if e.name and "crystal" not in e.name]
            if named:
                info.append("Spot sizes: " + ", ".join(
                    f"{html.escape(nm)} {cav.spot_size_at(nm) / UM:.0f} µm" for nm in named[:6]))
            info.append("Ring: one gain pass per round trip, repetition rate c/L.")
    else:
        plots.append(message_plot("Unstable at full pump power"))
        info.append(_err(f"<b>Unstable</b> at {spec.pump_power:.3g} W."))
    if stable_p:
        info.append(f"Stable pump range in the plot: {min(stable_p):.3g} to "
                    f"{max(stable_p):.3g} W")
    info.append(f"Optical length {cav.optical_length / MM:.1f} mm, FSR "
                f"{cav.free_spectral_range / 1e9:.3g} GHz, round trip "
                f"{cav.round_trip_time * 1e9:.3g} ns")
    lo = max(-3, min(min(m_t), min(m_s)) - 0.2)
    hi = min(3, max(max(m_t), max(m_s)) + 0.2)
    plots.append(plot("Stability vs pump power", "pump power [W]", "m = (A+D)/2",
                      series(powers, m_t, "tangential"),
                      series(powers, m_s, "sagittal", "dash"),
                      ylim=(lo, hi), hspan=(-1, 1), vlines=[spec.pump_power]))
    return _report(info=info, plots=plots)


# ---------------------------------------------------------------------- #
# 4. Operation
# ---------------------------------------------------------------------- #
def operation(spec: DesignSpec) -> dict:
    laser, error = _build(spec)
    if error:
        return error
    delta = laser.delta
    info = [f"Logarithmic round-trip loss δ = {delta:.4f}; share leaving through the "
            f"output coupler {gain.output_fraction(spec.output_coupling, delta) * 100:.1f} %."]
    op = laser.analyze(spec.pump_power)
    if op.stable:
        info.append(f"CW threshold {op.threshold:.3g} W, CW output {op.output_power:.3g} W.")
        if op.gain_passes == 1:
            info.append("Ring resonator: one gain pass per round trip.")
    if spec.mode == "passive":
        a = absorber(spec)
        l_gs, l_es = a.losses(spec.absorber_transmission, op.gain_passes)
        info.append(f"{html.escape(a.name)}: unbleached round-trip loss {l_gs:.3f}, bleached "
                    f"{l_es:.3f}; recovery time {a.recovery_time * 1e6:.2g} µs.")
    if spec.mode == "klm":
        km = kerr_model(spec)
        line = (f"Kerr medium: n₂ = {km.n2 * 1e20:.3g}×10⁻²⁰ m²/W, critical power "
                f"P<sub>cr</sub> = {km.critical_power / 1e6:.3g} MW.")
        if km.n2 == 0:
            line += " " + _err("This material has no n₂ value; set one to use KLM.")
        info.append(line)
    return _report(info=info)


# ---------------------------------------------------------------------- #
# 5. Results
# ---------------------------------------------------------------------- #
def results(spec: DesignSpec) -> dict:
    laser, error = _build(spec)
    if error:
        error["rows"] = [["Error", error["error"]]]
        return error
    p = spec.pump_power
    op = laser.analyze(p)
    if not op.stable:
        return _report(rows=[["Resonator", "unstable at this pump power"]],
                       plots=[message_plot("The resonator is unstable at the chosen pump "
                                           "power. Go back to step 3 to change it.")])
    rows = [
        ["Design", spec.name],
        ["Pump power", f"{p:.3g} W"],
        ["Absorbed power", f"{op.absorbed_power:.3g} W"],
        ["Heat load", f"{op.heat_power:.3g} W"],
        ["Thermal focal length", f"{op.thermal_focal_length / MM:.0f} mm"],
        ["Stability parameter m", f"{op.stability_parameter:.3f}"],
        ["Resonator type", "ring (1 gain pass)" if op.gain_passes == 1
         else "standing wave (2 gain passes)"],
        ["Laser / pump radius in crystal",
         f"{op.laser_radius / UM:.0f} / {op.pump_radius / UM:.0f} µm"
         + (" (multimode flat-top / rod)" if op.laser_profile == "tophat" else "")],
        ["CW threshold", f"{op.threshold:.3g} W"],
        ["CW output power", f"{op.output_power:.3g} W"],
        ["Optical efficiency", f"{op.output_power / p * 100:.1f} %"],
        ["M² estimate", f"{op.m2_estimate:.2f} (aberration {op.m2_aberration:.2f}, "
                        f"multimode {op.m2_multimode:.2f})"],
    ]
    if op.aperture_loss > 1e-4:
        rows.append(["Rod clipping loss (round trip)", f"{op.aperture_loss * 100:.2f} %"])
    stable_ops = [o for o in laser.scan(np.linspace(0.05, 1.0, 25) * p) if o.stable]
    notes: list[dict] = []
    plots: list[dict] = []

    if spec.mode == "cw":
        pp = [o.pump_power for o in stable_ops]
        plots.append(plot("CW output", "pump power [W]", "output [W]",
                          series(pp, [o.output_power for o in stable_ops], "output")))
        plots.append(plot("Beam quality estimate", "pump power [W]", "M²",
                          series(pp, [o.m2_estimate for o in stable_ops], "combined"),
                          series(pp, [o.m2_aberration for o in stable_ops],
                                 "thermal aberration", "dot"),
                          series(pp, [o.m2_multimode for o in stable_ops],
                                 "pump/mode ratio", "dash")))
    elif spec.mode == "qswitch":
        _qswitch(spec, laser, op, rows, plots, notes)
    elif spec.mode == "passive":
        _passive(spec, laser, rows, stable_ops, plots, notes)
    elif spec.mode == "klm":
        _klm(spec, laser, op, rows, plots, notes)
    else:
        _sesam(spec, laser, rows, stable_ops, plots, notes)
    notes.append({"level": "info", "text": DISCLAIMER})
    return _report(rows=rows, plots=plots, notes=notes)


def _qswitch(spec, laser, op, rows, plots, notes) -> None:
    p = spec.pump_power
    qs = laser.q_switched(p, spec.rep_rate)
    rows += [
        ["Repetition rate", f"{spec.rep_rate / 1e3:.3g} kHz"],
        ["Initial inversion / threshold", f"{qs['initial_ratio']:.2f}"],
        ["Pulse energy", f"{qs['energy'] * 1e3:.3g} mJ"],
        ["Pulse width (E / P_peak)", f"{qs['pulse_width'] * 1e9:.3g} ns"],
        ["Peak power", f"{qs['peak_power'] / 1e3:.3g} kW"],
        ["Average power", f"{qs['average_power']:.3g} W"],
    ]
    rates = np.geomspace(spec.rep_rate / 30, spec.rep_rate * 30, 30)
    res = [laser.q_switched(p, f) for f in rates]
    plots.append(plot("Pulse energy", "repetition rate [kHz]", "energy [mJ]",
                      series(rates / 1e3, [r["energy"] * 1e3 for r in res], "energy"),
                      xlog=True, vlines=[spec.rep_rate / 1e3]))
    plots.append(plot("Width and average power", "repetition rate [kHz]", "pulse width [ns]",
                      series(rates / 1e3, [r["pulse_width"] * 1e9 for r in res], "pulse width"),
                      series(rates / 1e3, [r["average_power"] for r in res], "average power",
                             axis="y2", color=1),
                      y2label="average power [W]", xlog=True,
                      hlines=[hline(op.output_power, "y2", "dash", "CW power")]))
    if qs["initial_ratio"] <= 1:
        notes.append({"level": "warn", "text": "The inversion does not reach threshold "
                                               "between pulses: no output."})


def _passive(spec, laser, rows, stable_ops, plots, notes) -> None:
    p = spec.pump_power
    loc = library_location(spec.absorber_location)
    ab = absorber(spec)
    res = laser.passively_q_switched(p, spec.absorber_transmission, ab, loc)
    pulse = res["pulse"]
    rows += [
        ["Absorber", f"{ab.name}, T0 = {spec.absorber_transmission * 100:.1f} %"],
        ["Absorber spot radius", f"{res['absorber_radius'] / UM:.0f} µm"],
        ["Bleaching criterion (needs > 1)", f"{pulse.bleaching_criterion:.2f}"],
        ["Threshold with absorber", f"{res['threshold']:.3g} W"],
        ["Pulse energy", f"{res['energy'] * 1e3:.3g} mJ"],
        ["Pulse width (E / P_peak)", f"{res['pulse_width'] * 1e9:.3g} ns"],
        ["Peak power", f"{res['peak_power'] / 1e3:.3g} kW"],
        ["Repetition rate", f"{res['rep_rate'] / 1e3:.3g} kHz"],
        ["Average power", f"{res['average_power']:.3g} W"],
    ]
    pp = [o.pump_power for o in stable_ops]
    vs_p = [laser.passively_q_switched(x, spec.absorber_transmission, ab, loc) for x in pp]
    plots.append(plot("Pump sets the repetition rate", "pump power [W]",
                      "repetition rate [kHz]",
                      series(pp, [v["rep_rate"] / 1e3 for v in vs_p], "repetition rate"),
                      series(pp, [v["average_power"] for v in vs_p], "average power", "dash",
                             axis="y2", color=1),
                      y2label="average power [W]"))
    t0s = np.linspace(max(0.3, spec.absorber_transmission - 0.3),
                      min(0.98, spec.absorber_transmission + 0.1), 25)
    vs_t = [laser.passively_q_switched(p, t, ab, loc) for t in t0s]
    plots.append(plot("Energy vs absorber T0", "absorber T0 [%]", "energy [mJ]",
                      series(t0s * 100, [v["energy"] * 1e3 for v in vs_t], "energy"),
                      series(t0s * 100, [v["pulse_width"] * 1e9 for v in vs_t], "pulse width",
                             "dash", axis="y2", color=1),
                      y2label="pulse width [ns]", vlines=[spec.absorber_transmission * 100]))
    if not pulse.pulse_forms:
        notes.append({"level": "warn", "text": "The absorber does not bleach fast enough for a "
                      "giant pulse (criterion below 1). Focus harder into the absorber or use "
                      "a lower T0."})
    elif res["rep_rate"] == 0:
        notes.append({"level": "warn", "text": "The pump does not reach threshold with the "
                                               "absorber."})
    elif not res["absorber_recovered"]:
        notes.append({"level": "info", "text": "The pulse period is shorter than three absorber "
                      "recovery times; the absorber will not recover fully and the pulses will "
                      "be weaker."})


def _sesam(spec, laser, rows, stable_ops, plots, notes) -> None:
    p = spec.pump_power
    loc = library_location(spec.sesam_location)
    res = laser.sesam_mode_locked(p, spec.sesam_saturation_fluence,
                                  spec.sesam_modulation_depth, loc)
    c = res["check"]
    rows += [
        ["Repetition rate", f"{c.repetition_rate / 1e6:.4g} MHz"],
        ["Intracavity pulse energy", f"{c.pulse_energy * 1e9:.3g} nJ"],
        ["QML threshold", f"{c.qml_threshold * 1e9:.3g} nJ"],
        ["QML margin", f"{c.qml_margin:.2f}"],
        ["SESAM spot radius", f"{res['absorber_radius'] / UM:.0f} µm"],
        ["SESAM saturation E_p / E_sat,A", f"{c.absorber_saturation:.1f}"],
        ["Pulse width estimate", f"{c.pulse_width_estimate * 1e12:.3g} ps"],
        ["Transform limit", f"{c.transform_limit * 1e12:.3g} ps"],
    ]
    pp, checks = [], []
    for o in stable_ops:
        pp.append(o.pump_power)
        checks.append(laser.sesam_mode_locked(o.pump_power, spec.sesam_saturation_fluence,
                                              spec.sesam_modulation_depth, loc)["check"])
    plots.append(plot("Mode-locking margins", "pump power [W]", "ratio",
                      series(pp, [k.qml_margin for k in checks], "E_p / E_p,QML"),
                      series(pp, [k.absorber_saturation for k in checks], "E_p / E_sat,A"),
                      hlines=[hline(1)]))
    plots.append(plot("Average output", "pump power [W]", "average output [W]",
                      series(pp, [o.output_power for o in stable_ops], "output")))
    if c.qml_margin < 1:
        notes.append({"level": "warn", "text": "Below the QML threshold: the laser will "
                      "Q-switch mode lock. Lengthen the cavity, shrink the mode on the SESAM, "
                      "or use a SESAM with lower saturation fluence or modulation depth."})
    elif c.absorber_saturation > 20:
        notes.append({"level": "warn", "text": "The SESAM is saturated more than 20×; risk of "
                      "damage or multiple pulsing. Enlarge the mode on the SESAM."})
    elif c.absorber_saturation < 3:
        notes.append({"level": "info", "text": "The SESAM is only weakly saturated; "
                                               "mode-locking may not self-start."})


def _klm(spec, laser, op, rows, plots, notes) -> None:
    p = spec.pump_power
    f_th = laser.thermal_focal_length(p)
    km = kerr_model(spec, f_th)
    if km.n2 <= 0:
        notes.append({"level": "warn", "text": "The gain medium has no n₂: KLM cannot be "
                                               "estimated."})
        return
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
        ["Critical power P_cr", f"{p_cr / 1e6:.3g} MW"],
        ["KLM strength at aperture (t / s)",
         f"{strengths[(loc, 't')]:.2f} / {strengths[(loc, 's')]:.2f}"],
        ["KLM strength in crystal (t / s)",
         f"{strengths[('crystal', 't')]:.2f} / {strengths[('crystal', 's')]:.2f}"],
        ["Repetition rate", f"{f_rep / 1e6:.4g} MHz"],
        ["Intracavity pulse energy", f"{e_p * 1e9:.3g} nJ"],
        ["Peak power / P_cr", f"{peak / p_cr:.2f}"],
    ]
    if e_p > 0:
        gdd = modelocking.soliton_required_gdd(spec.klm_pulse_width, spm, e_p)
        rows.append(["Soliton net GDD per round trip", f"{gdd / 1e-30:.0f} fs²"])
        gvd = laser.material.gvd
        if gvd:
            mat_gdd = op.gain_passes * gvd * spec.crystal_length
            rows.append(["Crystal GDD per round trip", f"+{mat_gdd / 1e-30:.0f} fs²"])
            rows.append(["Compensation needed (prisms, mirrors)",
                         f"{(gdd - mat_gdd) / 1e-30:.0f} fs²"])
    p_axis = np.linspace(0, 0.3, 10)
    w_ap = km.spot_vs_power(p_axis, loc, "t") / km.spot_vs_power([0], loc, "t")[0]
    w_cr = km.spot_vs_power(p_axis, "crystal", "t") / km.spot_vs_power([0], "crystal", "t")[0]
    plots.append(plot("Self-consistent Kerr lens (t)", "P / P_cr", "w(P) / w(0)",
                      series(p_axis, w_ap, "at aperture"),
                      series(p_axis, w_cr, "in crystal", "dash")))
    pumps = np.linspace(0.2, 1.2, 9) * p
    hard, soft = [], []
    for x in pumps:
        m = kerr_model(spec, laser.thermal_focal_length(x))
        hard.append(m.klm_strength(loc, "t"))
        soft.append(m.klm_strength("crystal", "t"))
    plots.append(plot("KLM strength vs thermal lens", "pump power [W]", "δ = (1/w) dw/dp",
                      series(pumps, hard, "at aperture", markers=True),
                      series(pumps, soft, "in crystal", "dash", markers=True),
                      hlines=[hline(0, dash="solid")], vlines=[p]))
    d = strengths[(loc, "t")]
    if not np.isfinite(d):
        notes.append({"level": "warn", "text": "The Kerr-lensed resonator is unstable."})
    else:
        notes.append({"level": "info", "text": "A negative δ at a hard aperture favours pulses "
                      "(the pulse shrinks there); a negative δ in the crystal helps soft-aperture "
                      "KLM with a small pump. |δ| grows near the stability edges."})


REPORTS = {"gain_medium": gain_medium, "pump": pump_step, "resonator": resonator,
           "operation": operation, "results": results}


def report(spec: DesignSpec, step: str) -> dict:
    """The report for wizard step ``step`` (one of :data:`STEPS`)."""
    if step not in REPORTS:
        raise ValueError(f"Unknown step {step!r}; expected one of {STEPS}")
    out = REPORTS[step](spec)
    problems = spec.validate()
    out["problems"] = problems
    return out


def finite_or_none(x):
    """JSON cannot carry nan or inf: map them to ``None`` (recursively)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: finite_or_none(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite_or_none(v) for v in x]
    if isinstance(x, np.generic):
        return finite_or_none(x.item())
    return x
