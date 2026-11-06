"""Which inputs set each quantity on the Results step.

The Results table of both front ends (the Qt wizard and the browser app)
shows, when the pointer rests on a row, a short note on how the quantity is
found and the principal design inputs that set it, with their current
values. This module is the single place where those dependencies are
written down; :func:`influences` returns them as plain data and
:func:`tooltip_html` formats them for Qt.

The lists name the inputs that matter most, not every input that enters the
calculation: almost everything depends a little on everything else through
the thermal lens and the mode size. Inputs are grouped by the wizard step
where they are set. Some entries depend on the design, for example end
versus side pumping, or the operating mode (the repetition rate is an input
for active Q-switching but a result for passive Q-switching).
"""

from __future__ import annotations

import html
import math

from .spec import DesignSpec

STEP_NAMES = {"gain_medium": "1. Gain medium", "pump": "2. Pump",
              "resonator": "3. Resonator", "operation": "4. Operation"}


# ---------------------------------------------------------------------- #
# Formatting the current value of an input
# ---------------------------------------------------------------------- #
def _g(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}g}"


def _radius(r: float) -> str:
    if math.isinf(r):
        return "flat"
    return f"{r * 1e3:.4g} mm"


def _location(loc: str) -> str:
    return {"mirror1": "end mirror 1", "mirror2": "end mirror 2"}.get(loc, f"element “{loc}”")


def _elements(spec: DesignSpec) -> str:
    spaces = sum(float(e.get("length", 0.0)) for e in spec.elements if e.get("type") == "space")
    n = len(spec.elements)
    return f"{n} element{'s' if n != 1 else ''}, {spaces * 1e3:.4g} mm of air"


def _absorption(spec: DesignSpec) -> str:
    if spec.effective_absorption is not None:
        return f"{spec.effective_absorption / 100:.3g} /cm (set directly)"
    mat = spec.gain_medium()
    return (f"{mat.pump_absorption_coefficient(spec.doping) / 100:.3g} /cm "
            f"({spec.doping:.3g} {mat.doping_unit} doping)")


def _mat(attr: str, scale: float, unit: str, digits: int = 3):
    def get(spec: DesignSpec) -> str:
        value = getattr(spec.gain_medium(), attr)
        if value is None:
            return "not tabulated"
        return f"{value / scale:.{digits}g}{(' ' + unit) if unit else ''}"
    return get


def _absorber_recovery(spec: DesignSpec) -> str:
    from .spec import absorber
    return f"{absorber(spec).recovery_time * 1e6:.2g} µs"


def _absorber_name(spec: DesignSpec) -> str:
    from .spec import absorber
    return absorber(spec).name


#: Every input the notes can name: key -> (wizard step, label, current value).
PARAMETERS = {
    # 1. Gain medium
    "material": ("gain_medium", "Material", lambda s: s.gain_medium().name),
    "doping": ("gain_medium", "Doping",
               lambda s: f"{_g(s.doping)} {s.gain_medium().doping_unit}"),
    "crystal_length": ("gain_medium", "Crystal / rod length",
                       lambda s: f"{s.crystal_length * 1e3:.4g} mm"),
    "crystal_brewster": ("gain_medium", "Brewster-cut crystal",
                         lambda s: "yes" if s.crystal_brewster else "no"),
    "emission_cross_section": ("gain_medium", "Emission cross section",
                               _mat("emission_cross_section", 1e-23, "×10⁻¹⁹ cm²")),
    "upper_state_lifetime": ("gain_medium", "Upper-state lifetime",
                             _mat("upper_state_lifetime", 1e-6, "µs")),
    "refractive_index": ("gain_medium", "Refractive index", _mat("refractive_index", 1, "", 4)),
    "dn_dT": ("gain_medium", "dn/dT", _mat("dn_dT", 1e-6, "×10⁻⁶ /K")),
    "thermal_conductivity": ("gain_medium", "Thermal conductivity",
                             _mat("thermal_conductivity", 1, "W/(m·K)")),
    "pump_absorption_cross_section": ("gain_medium", "Pump absorption cross section",
                                      _mat("pump_absorption_cross_section", 1e-24,
                                           "×10⁻²⁰ cm²")),
    "gain_bandwidth": ("gain_medium", "Gain bandwidth", _mat("gain_bandwidth", 1e9, "GHz")),
    "heat_fraction": ("gain_medium", "Heat fraction (quantum defect)",
                      lambda s: f"{s.gain_medium().effective_heat_fraction:.3f}"),
    "wavelengths": ("gain_medium", "Laser / pump wavelength",
                    lambda s: f"{s.gain_medium().laser_wavelength * 1e9:.1f} / "
                              f"{s.gain_medium().pump_wavelength * 1e9:.1f} nm"),
    "n2": ("gain_medium", "Nonlinear index n₂", _mat("nonlinear_index", 1e-20, "×10⁻²⁰ m²/W")),
    "gvd": ("gain_medium", "Group velocity dispersion", _mat("gvd", 1e-27, "fs²/mm")),
    # 2. Pump
    "pump_power": ("pump", "Pump power", lambda s: f"{_g(s.pump_power)} W"),
    "pump_waist": ("pump", "Pump waist radius", lambda s: f"{s.pump_waist * 1e6:.4g} µm"),
    "pump_m2": ("pump", "Pump beam quality M²", lambda s: _g(s.pump_m2)),
    "pump_waist_position": ("pump", "Pump waist depth in crystal",
                            lambda s: f"{s.pump_waist_position * 1e3:.4g} mm"),
    "pump_passes": ("pump", "Pump passes", lambda s: str(s.pump_passes)),
    "effective_absorption": ("pump", "Pump absorption coefficient", _absorption),
    "rod_radius": ("pump", "Rod radius", lambda s: f"{s.rod_radius * 1e3:.4g} mm"),
    "absorption_efficiency": ("pump", "Absorption efficiency",
                              lambda s: f"{s.absorption_efficiency * 100:.3g} %"),
    "rod_thermal_lens": ("pump", "Thermal lens in resonator",
                         lambda s: s.rod_thermal_lens.replace("_", "/")),
    "multimode_fill": ("pump", "Multimode fill",
                       lambda s: "TEM00 only" if s.multimode_fill is None
                       else f"{s.multimode_fill:.3g} of the rod radius"),
    # 3. Resonator
    "cavity_type": ("resonator", "Resonator type",
                    lambda s: "ring" if s.cavity_type == "ring" else "standing wave"),
    "R1": ("resonator", "End mirror 1 radius", lambda s: _radius(s.R1)),
    "R2": ("resonator", "End mirror 2 radius", lambda s: _radius(s.R2)),
    "elements": ("resonator", "Resonator elements and spacings", _elements),
    # 4. Operation
    "output_coupling": ("operation", "Output coupler transmission",
                        lambda s: f"{s.output_coupling * 100:.3g} %"),
    "passive_loss": ("operation", "Other round-trip losses",
                     lambda s: f"{s.passive_loss * 100:.3g} %"),
    "rep_rate": ("operation", "Repetition rate", lambda s: f"{s.rep_rate / 1e3:.3g} kHz"),
    "absorber": ("operation", "Saturable absorber", _absorber_name),
    "absorber_recovery": ("operation", "Absorber recovery time", _absorber_recovery),
    "absorber_transmission": ("operation", "Initial transmission T0",
                              lambda s: f"{s.absorber_transmission * 100:.3g} %"),
    "absorber_location": ("operation", "Absorber location",
                          lambda s: _location(s.absorber_location)),
    "sesam_saturation_fluence": ("operation", "SESAM saturation fluence",
                                 lambda s: f"{s.sesam_saturation_fluence * 1e2:.3g} µJ/cm²"),
    "sesam_modulation_depth": ("operation", "SESAM modulation depth",
                               lambda s: f"{s.sesam_modulation_depth * 100:.3g} %"),
    "sesam_location": ("operation", "SESAM location", lambda s: _location(s.sesam_location)),
    "klm_aperture": ("operation", "KLM aperture", lambda s: _location(s.klm_aperture)),
    "klm_pulse_width": ("operation", "Target pulse width",
                        lambda s: f"{s.klm_pulse_width * 1e15:.3g} fs"),
}


# ---------------------------------------------------------------------- #
# Groups of inputs that recur, expanded for the design at hand
# ---------------------------------------------------------------------- #
def _side(spec: DesignSpec) -> bool:
    return spec.pump_geometry == "side"


def _group(name: str, spec: DesignSpec) -> list[str]:
    side = _side(spec)
    if name == "absorbed":  # absorbed pump power
        if side:
            return ["pump_power", "absorption_efficiency"]
        out = ["pump_power", "effective_absorption", "crystal_length"]
        return out + ["pump_passes"] if spec.pump_passes > 1 else out
    if name == "pump_size":  # pump (or rod) radius in the crystal
        if side:
            return ["rod_radius"]
        return ["pump_waist", "pump_m2"]
    if name == "thermal":  # thermal lens
        out = _group("absorbed", spec) + ["heat_fraction", "thermal_conductivity", "dn_dT"]
        if side:
            return out + ["crystal_length", "rod_thermal_lens"]
        return out + _group("pump_size", spec)
    if name == "cavity":  # resonator geometry
        return ["elements"] if spec.cavity_type == "ring" else ["R1", "R2", "elements"]
    if name == "mode":  # laser mode size: resonator geometry plus the thermal lens
        out = _group("cavity", spec) + ["pump_power"]
        if side:
            out += ["rod_thermal_lens", "multimode_fill"]
        return out
    if name == "losses":
        return ["output_coupling", "passive_loss"]
    if name == "gain":  # small-signal gain per unit pump
        return ["emission_cross_section", "upper_state_lifetime", "wavelengths"]
    return [name]


# One entry per Results row: (summary, [input keys or group names]).
# Keys are "label" or "mode:label" (the second wins for that mode).
_RULES: dict[str, tuple[str, list[str]]] = {
    "Pump power": ("An input, set in step 2.", ["pump_power"]),
    "Absorbed power": ("Incident pump times the absorbed fraction.", ["absorbed"]),
    "Heat load": ("Absorbed pump times the heat fraction.", ["absorbed", "heat_fraction"]),
    "Thermal focal length": ("Set by the heat load, the pumped radius and the crystal's "
                             "thermal and thermo-optic properties.", ["thermal"]),
    "Paraxial stability (A+D)/2": ("m = (A+D)/2 of the round-trip ABCD matrix in each "
                                   "plane, with the crystal and its thermal lens at this "
                                   "pump power; stable for −1 < m < 1. Every resonator "
                                   "element enters; fold angles split t from s.",
                                   ["cavity_type", "cavity", "crystal_length",
                                    "refractive_index", "crystal_brewster", "thermal"]),
    "Resonator type": ("An input, set in step 3.", ["cavity_type"]),
    "Laser / pump radius in crystal": ("The TEM00 mode follows from the resonator and the "
                                       "thermal lens; the pump radius from the pump optics.",
                                       ["mode", "pump_size"]),
    "CW threshold": ("Rises with the round-trip loss and with the gain volume; falls with σ·τ "
                     "and better pump/mode overlap.",
                     ["losses", "gain", "pump_size", "mode", "absorbed"]),
    "CW output power": ("Slope efficiency (output-coupling share of the loss, quantum defect, "
                        "absorption, overlap) times the pump above threshold.",
                        ["pump_power", "losses", "absorbed", "gain", "pump_size", "mode"]),
    "Optical efficiency": ("CW output over incident pump.",
                           ["pump_power", "losses", "absorbed", "pump_size", "mode"]),
    "M² estimate": ("Thermal aberration grows with the heat load and the mode size; the "
                    "multimode part with the pump-to-mode radius ratio.",
                    ["thermal", "mode", "pump_size"]),
    "Rod clipping loss (round trip)": ("Gaussian mode clipped by the rod aperture.",
                                       ["rod_radius", "mode"]),
    # Active Q-switching
    "qswitch:Repetition rate": ("An input, set in step 4.", ["rep_rate"]),
    "Initial inversion / threshold": ("Inversion built up between pulses relative to "
                                      "threshold: pump above threshold, period and lifetime.",
                                      ["pump_power", "rep_rate", "upper_state_lifetime",
                                       "losses", "absorbed", "pump_size", "mode"]),
    "qswitch:Pulse energy": ("Stored energy extracted by the pulse: inversion ratio, mode "
                             "area, saturation fluence and output-coupling share.",
                             ["pump_power", "rep_rate", "upper_state_lifetime",
                              "emission_cross_section", "losses", "mode", "pump_size"]),
    "qswitch:Pulse width (E / P_peak)": ("Shorter for a short cavity, high inversion ratio "
                                         "and high loss.",
                                         ["elements", "rep_rate", "pump_power", "losses",
                                          "upper_state_lifetime"]),
    "qswitch:Peak power": ("Pulse energy over pulse width.",
                           ["pump_power", "rep_rate", "losses", "elements", "mode",
                            "emission_cross_section"]),
    "qswitch:Average power": ("Pulse energy times repetition rate; approaches the CW power at "
                              "high rates.", ["pump_power", "rep_rate", "upper_state_lifetime",
                                              "losses", "mode"]),
    # Passive Q-switching
    "Absorber": ("Inputs, set in step 4.", ["absorber", "absorber_transmission"]),
    "Absorber spot radius": ("Mode radius at the absorber location.",
                             ["absorber_location", "cavity", "thermal"]),
    "Bleaching criterion (needs > 1)": ("Ratio of absorber to gain saturation: grows with the "
                                        "absorber cross sections and the gain-to-absorber "
                                        "mode area ratio.",
                                        ["absorber", "emission_cross_section", "absorber_location",
                                         "mode", "pump_size"]),
    "Threshold with absorber": ("CW threshold with the unbleached absorber loss added.",
                                ["absorber_transmission", "losses", "gain", "pump_size", "mode",
                                 "absorbed"]),
    "passive:Pulse energy": ("Set by the absorber's initial transmission and the mode areas, "
                             "not by the pump.",
                             ["absorber", "absorber_transmission", "output_coupling",
                              "passive_loss", "mode", "absorber_location",
                              "emission_cross_section"]),
    "passive:Pulse width (E / P_peak)": ("Shorter for a short cavity and a low T0.",
                                         ["elements", "absorber_transmission", "losses"]),
    "passive:Peak power": ("Pulse energy over pulse width.",
                           ["absorber_transmission", "losses", "elements", "mode",
                            "absorber_location"]),
    "passive:Repetition rate": ("The pump sets how often the inversion reaches threshold.",
                                ["pump_power", "absorber_transmission", "upper_state_lifetime",
                                 "losses", "absorbed", "pump_size", "mode"]),
    "passive:Average power": ("Pulse energy times repetition rate.",
                              ["pump_power", "absorber_transmission", "losses", "mode"]),
    # SESAM mode locking
    "modelock:Repetition rate": ("c over the round-trip optical path.",
                                 ["cavity_type", "elements", "crystal_length",
                                  "refractive_index"]),
    "modelock:Intracavity pulse energy": ("Circulating power over repetition rate.",
                                          ["pump_power", "losses", "absorbed", "mode",
                                           "elements"]),
    "QML threshold": ("E² > E_sat,L · E_sat,A · ΔR: shrink the modes in the gain and on the "
                      "SESAM, or use a lower F_sat,A or ΔR.",
                      ["sesam_saturation_fluence", "sesam_modulation_depth", "sesam_location",
                       "emission_cross_section", "wavelengths", "mode"]),
    "QML margin": ("Intracavity pulse energy over the QML threshold.",
                   ["pump_power", "elements", "output_coupling", "sesam_saturation_fluence",
                    "sesam_modulation_depth", "sesam_location", "mode"]),
    "SESAM spot radius": ("Mode radius at the SESAM location.",
                          ["sesam_location", "cavity", "thermal"]),
    "SESAM saturation E_p / E_sat,A": ("Pulse energy over the SESAM saturation energy "
                                       "(F_sat,A times the spot area).",
                                       ["pump_power", "elements", "output_coupling",
                                        "sesam_saturation_fluence", "sesam_location"]),
    "Pulse width estimate": ("τ ≈ (1.07/Δν_g)·√(g/ΔR): the gain bandwidth, the round-trip "
                             "loss and the modulation depth.",
                             ["gain_bandwidth", "losses", "sesam_modulation_depth"]),
    "Transform limit": ("Shortest sech² pulse the gain bandwidth supports.", ["gain_bandwidth"]),
    # Kerr-lens mode locking
    "Critical power P_cr": ("P_cr = λ²/(2π n n₂).", ["wavelengths", "refractive_index", "n2"]),
    "KLM strength at aperture (t / s)": ("How fast the mode at the aperture changes with "
                                         "intracavity power; largest near a stability edge.",
                                         ["klm_aperture", "cavity", "thermal", "crystal_length",
                                          "crystal_brewster", "n2"]),
    "KLM strength in crystal (t / s)": ("How fast the mode in the crystal changes with "
                                        "intracavity power.",
                                        ["cavity", "thermal", "crystal_length",
                                         "crystal_brewster", "n2"]),
    "klm:Repetition rate": ("c over the round-trip optical path.",
                            ["cavity_type", "elements", "crystal_length", "refractive_index"]),
    "klm:Intracavity pulse energy": ("Circulating power over repetition rate.",
                                     ["pump_power", "losses", "absorbed", "mode", "elements"]),
    "Peak power / P_cr": ("Pulse peak power (pulse energy over the target width) relative to "
                          "the critical power.",
                          ["pump_power", "losses", "elements", "klm_pulse_width", "n2"]),
    "Soliton net GDD per round trip": ("Negative dispersion that balances self-phase "
                                       "modulation for the target width.",
                                       ["klm_pulse_width", "n2", "crystal_length", "mode",
                                        "pump_power", "losses", "elements"]),
    "Crystal GDD per round trip": ("Crystal GVD times the length passed per round trip.",
                                   ["gvd", "crystal_length", "cavity_type"]),
    "Compensation needed (prisms, mirrors)": ("Soliton GDD minus the crystal's own GDD.",
                                              ["klm_pulse_width", "gvd", "crystal_length", "n2",
                                               "pump_power", "losses"]),
}


def _expand(keys: list[str], spec: DesignSpec) -> list[str]:
    out: list[str] = []
    todo = list(keys)
    while todo:
        key = todo.pop(0)
        if key in PARAMETERS:
            if key not in out:
                out.append(key)
            continue
        expanded = _group(key, spec)
        if expanded == [key]:
            raise KeyError(f"Unknown input {key!r}")
        todo[:0] = expanded
    return out


def influences(label: str, spec: DesignSpec) -> dict | None:
    """The principal inputs behind the Results row ``label``.

    Returns ``None`` for rows without a note (the design name, errors), or::

        {"summary": "how the quantity is found",
         "inputs": [{"key": "pump_power", "step": "2. Pump",
                     "name": "Pump power", "value": "20 W"}, ...]}

    with the inputs ordered by wizard step.
    """
    rule = _RULES.get(f"{spec.mode}:{label}") or _RULES.get(label)
    if rule is None:
        return None
    summary, keys = rule
    order = list(STEP_NAMES)
    inputs = []
    for key in _expand(keys, spec):
        step, name, get = PARAMETERS[key]
        try:
            value = get(spec)
        except (KeyError, ValueError, TypeError, AttributeError):
            value = "?"
        inputs.append({"key": key, "step": STEP_NAMES[step], "name": name, "value": value})
    keys_order = list(PARAMETERS)
    inputs.sort(key=lambda d: (order.index(PARAMETERS[d["key"]][0]), keys_order.index(d["key"])))
    return {"summary": summary, "inputs": inputs}


def tooltip_html(label: str, spec: DesignSpec) -> str:
    """:func:`influences` as rich text for a Qt tooltip ("" when there is none)."""
    info = influences(label, spec)
    if info is None:
        return ""
    parts = ["<table cellspacing='0' cellpadding='1' width='380'>",
             f"<tr><td colspan='2'><b>{html.escape(label)}</b><br>"
             f"{html.escape(info['summary'])}</td></tr>"]
    step = None
    for d in info["inputs"]:
        if d["step"] != step:
            step = d["step"]
            parts.append(f"<tr><td colspan='2'><i>{html.escape(step)}</i></td></tr>")
        parts.append(f"<tr><td>&nbsp;&nbsp;{html.escape(d['name'])}&nbsp;&nbsp;</td>"
                     f"<td>{html.escape(d['value'])}</td></tr>")
    parts.append("</table>")
    return "".join(parts)
