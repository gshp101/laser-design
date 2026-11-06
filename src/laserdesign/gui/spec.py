"""A serialisable description of a laser design, independent of Qt.

The GUI edits a :class:`DesignSpec`; :func:`build_laser` turns it into a
:class:`laserdesign.design.EndPumpedLaser` or
:class:`laserdesign.design.SidePumpedRodLaser`, and :func:`kerr_model` into a
:class:`laserdesign.kerr.KerrLensModel`. Keeping this layer free of Qt means
it can be tested, saved as JSON and reused from scripts.

All values are SI, as in the rest of the library. The resonator is a list of
element dictionaries describing one pass from end mirror 1 to end mirror 2
(``cavity_type = "standing"``) or one full loop (``cavity_type = "ring"``,
where ``R1`` and ``R2`` are ignored and curved mirrors are ``"mirror"``
elements):

``{"type": "crystal"}``
    Where the gain crystal (or rod) sits. Expanded with
    :func:`laserdesign.abcd.crystal_with_thermal_lens`, or with Brewster
    halves when ``crystal_brewster`` is set. Exactly one is required.
``{"type": "space", "length": L}``
    Air gap.
``{"type": "mirror", "R": R, "angle_deg": a}``
    Curved (or flat, ``R = inf``) fold mirror.
``{"type": "lens", "f": f}``
    Thin lens.
``{"type": "medium", "length": L, "n": n}``
    Dielectric block, e.g. a Q-switch or Pockels cell.
``{"type": "brewster", "thickness": t, "n": n}``
    Brewster-angled plate.

Every element may also carry a ``"name"``, which is how absorbers, SESAMs
and KLM apertures are located: those settings take ``"mirror1"``,
``"mirror2"`` (standing-wave only) or an element name.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import abcd, kerr, passive_qswitch, pump
from ..design import EndPumpedLaser, SidePumpedRodLaser
from ..materials import GainMedium, get_material

ELEMENT_TYPES = ("crystal", "space", "mirror", "lens", "medium", "brewster")
OPERATION_MODES = ("cw", "qswitch", "passive", "modelock", "klm")
CAVITY_TYPES = ("standing", "ring")
PUMP_GEOMETRIES = ("end", "side")
ROD_LENSES = ("average", "radial", "tangential", "dn_dT")
CRYSTAL_LENS_NAME = "crystal thermal lens"


def _inf_to_json(x: float):
    return "inf" if isinstance(x, float) and math.isinf(x) else x


def _json_to_float(x) -> float:
    if isinstance(x, str):
        return float(x)  # handles "inf" and "-inf"
    return float(x)


@dataclass
class DesignSpec:
    """Everything the wizard collects.

    Attributes are grouped by wizard page: gain medium, pump, resonator and
    operation.
    """

    name: str = "New design"
    # Gain medium
    material: str = "nd:yvo4"
    material_overrides: dict = field(default_factory=dict)
    doping: float = 0.3
    crystal_length: float = 6e-3
    effective_absorption: float | None = None
    crystal_brewster: bool = False
    # Pump
    pump_geometry: str = "end"
    pump_power: float = 20.0
    pump_waist: float = 200e-6
    pump_m2: float = 30.0
    pump_waist_position: float = 1e-3
    pump_passes: int = 1
    # Side pumping (pump_geometry == "side"; crystal_length is the rod length)
    rod_radius: float = 2e-3
    absorption_efficiency: float = 0.7
    rod_thermal_lens: str = "average"
    multimode_fill: float | None = None
    # Resonator
    cavity_type: str = "standing"
    R1: float = math.inf
    R2: float = 0.2
    elements: list = field(default_factory=lambda: [{"type": "crystal"},
                                                    {"type": "space", "length": 0.04}])
    # Operation
    output_coupling: float = 0.1
    passive_loss: float = 0.01
    mode: str = "cw"
    rep_rate: float = 20e3
    sesam_saturation_fluence: float = 0.6     # J/m^2 (60 uJ/cm^2)
    sesam_modulation_depth: float = 0.01
    sesam_location: str = "mirror2"
    absorber: str = "cr:yag"
    absorber_transmission: float = 0.85
    absorber_location: str = "mirror2"
    klm_aperture: str = "mirror1"
    klm_slices: int = 6
    klm_pulse_width: float = 20e-15

    # ------------------------------------------------------------------ #
    def gain_medium(self) -> GainMedium:
        """The material with any user overrides applied."""
        base = get_material(self.material)
        return base.replace(**self.material_overrides) if self.material_overrides else base

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty when valid)."""
        problems = []
        if self.mode not in OPERATION_MODES:
            problems.append(f"Unknown operating mode {self.mode!r}")
        if self.cavity_type not in CAVITY_TYPES:
            problems.append(f"Unknown cavity type {self.cavity_type!r}")
        if self.pump_geometry not in PUMP_GEOMETRIES:
            problems.append(f"Unknown pump geometry {self.pump_geometry!r}")
        if self.rod_thermal_lens not in ROD_LENSES:
            problems.append(f"Unknown rod thermal lens choice {self.rod_thermal_lens!r}")
        names = {e.get("name") for e in self.elements if e.get("name")}
        for label, loc in (("SESAM", self.sesam_location),
                           ("Saturable absorber", self.absorber_location),
                           ("KLM aperture", self.klm_aperture)):
            used = {"modelock": "SESAM", "passive": "Saturable absorber",
                    "klm": "KLM aperture"}.get(self.mode)
            if used != label:
                continue
            if loc in ("mirror1", "mirror2"):
                if self.cavity_type == "ring":
                    problems.append(f"{label}: a ring has no end mirrors; name an element "
                                    "and choose it as the location")
            elif loc != "crystal" and loc not in names:
                problems.append(f"{label} location {loc!r} is not an element name")
        if self.pump_geometry == "side":
            if not self.rod_radius > 0:
                problems.append("Rod radius must be positive")
            if not 0 < self.absorption_efficiency <= 1:
                problems.append("Absorption efficiency must be between 0 and 1")
            if self.multimode_fill is not None and not 0 < self.multimode_fill <= 1:
                problems.append("Multimode fill factor must be between 0 and 1")
        if self.mode == "passive" and not 0 < self.absorber_transmission < 1:
            problems.append("Absorber initial transmission must be between 0 and 1")
        crystals = [e for e in self.elements if e.get("type") == "crystal"]
        if len(crystals) != 1:
            problems.append("The resonator must contain exactly one gain crystal")
        for e in self.elements:
            if e.get("type") not in ELEMENT_TYPES:
                problems.append(f"Unknown element type {e.get('type')!r}")
            if e.get("type") in ("space", "medium") and e.get("length", 0) < 0:
                problems.append("Lengths must be positive")
        if not 0 < self.output_coupling < 1:
            problems.append("Output coupling must be between 0 and 1")
        if not 0 <= self.passive_loss < 1:
            problems.append("Passive loss must be between 0 and 1")
        for label, v in (("doping", self.doping), ("crystal length", self.crystal_length),
                         ("pump power", self.pump_power), ("pump waist", self.pump_waist),
                         ("pump M^2", self.pump_m2)):
            if not v > 0:
                problems.append(f"{label.capitalize()} must be positive")
        return problems

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        d = asdict(self)
        d["R1"] = _inf_to_json(self.R1)
        d["R2"] = _inf_to_json(self.R2)
        d["elements"] = [{k: _inf_to_json(v) for k, v in e.items()} for e in self.elements]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DesignSpec":
        d = dict(d)
        for key in ("R1", "R2"):
            if key in d:
                d[key] = _json_to_float(d[key])
        if "elements" in d:
            d["elements"] = [
                {k: (_json_to_float(v) if k in ("R", "f") else v) for k, v in e.items()}
                for e in d["elements"]
            ]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "DesignSpec":
        return cls.from_dict(json.loads(Path(path).read_text()))


def _crystal(material: GainMedium, length: float, f_thermal: float, brewster: bool) -> list:
    n = material.refractive_index
    if not brewster:
        return abcd.crystal_with_thermal_lens(length, n, f_thermal, name="crystal")
    thickness = length * n / np.sqrt(n**2 + 1)
    return [abcd.BrewsterPlate(thickness=thickness / 2, n=n, name="crystal (first half)"),
            abcd.ThinLens(f=f_thermal, name=CRYSTAL_LENS_NAME),
            abcd.BrewsterPlate(thickness=thickness / 2, n=n, name="crystal (second half)")]


def _element(e: dict, material: GainMedium, length: float, f_thermal: float,
             brewster: bool = False, crystal_elements: list | None = None) -> list:
    t = e["type"]
    name = e.get("name", "")
    if t == "crystal":
        if crystal_elements is not None:
            return list(crystal_elements)
        return _crystal(material, length, f_thermal, brewster)
    if t == "space":
        return [abcd.FreeSpace(e["length"], name=name)]
    if t == "mirror":
        return [abcd.CurvedMirror(_json_to_float(e.get("R", math.inf)),
                                  angle=np.deg2rad(e.get("angle_deg", 0.0)), name=name)]
    if t == "lens":
        return [abcd.ThinLens(_json_to_float(e["f"]), name=name)]
    if t == "medium":
        return [abcd.Medium(e["length"], n=e.get("n", 1.0), name=name)]
    if t == "brewster":
        return [abcd.BrewsterPlate(thickness=e["thickness"], n=e.get("n", 1.5), name=name)]
    raise ValueError(f"Unknown element type {t!r}")


def _resonator(spec: DesignSpec, material: GainMedium, f_thermal: float,
               crystal_elements: list | None = None):
    els = []
    for e in spec.elements:
        els.extend(_element(e, material, spec.crystal_length, f_thermal,
                            spec.crystal_brewster, crystal_elements))
    if spec.cavity_type == "ring":
        return abcd.RingCavity(els, wavelength=material.laser_wavelength)
    return abcd.StandingWaveCavity(els, R1=spec.R1, R2=spec.R2,
                                   wavelength=material.laser_wavelength)


def cavity_factory(spec: DesignSpec):
    """Return ``f_thermal -> StandingWaveCavity or RingCavity`` for the spec's resonator."""
    material = spec.gain_medium()

    def cavity(f_thermal: float):
        return _resonator(spec, material, f_thermal)

    return cavity


def library_location(location: str) -> int | str:
    """Translate a spec location (``"mirror1"``, ``"mirror2"``, name) for the library."""
    return {"mirror1": 1, "mirror2": 2}.get(location, location)


def kerr_model(spec: DesignSpec, f_thermal: float = math.inf) -> kerr.KerrLensModel:
    """The spec's resonator with its crystal sliced into Kerr lenses.

    The thermal lens ``f_thermal`` sits at the crystal centre under the usual
    name, so mode sizes can be read at :data:`CRYSTAL_LENS_NAME`.
    """
    material = spec.gain_medium()

    def cavity(crystal_elements):
        return _resonator(spec, material, f_thermal, crystal_elements)

    return kerr.KerrLensModel(cavity, spec.crystal_length, material.refractive_index,
                              material.nonlinear_index, material.laser_wavelength,
                              brewster=spec.crystal_brewster, slices=spec.klm_slices,
                              name="crystal", thermal_focal_length=f_thermal)


def absorber(spec: DesignSpec) -> passive_qswitch.SaturableAbsorber:
    """The spec's passive Q-switch absorber."""
    return passive_qswitch.get_absorber(spec.absorber)


def build_laser(spec: DesignSpec) -> EndPumpedLaser | SidePumpedRodLaser:
    """Build the laser model described by ``spec``.

    Raises
    ------
    ValueError
        If :meth:`DesignSpec.validate` reports problems.
    """
    problems = spec.validate()
    if problems:
        raise ValueError("; ".join(problems))
    material = spec.gain_medium()
    if spec.pump_geometry == "side":
        return SidePumpedRodLaser(
            material=material, doping=spec.doping, rod_radius=spec.rod_radius,
            rod_length=spec.crystal_length, cavity=cavity_factory(spec),
            crystal_element=CRYSTAL_LENS_NAME, output_coupling=spec.output_coupling,
            passive_loss=spec.passive_loss, absorption_efficiency=spec.absorption_efficiency,
            thermal_lens=spec.rod_thermal_lens, multimode_fill=spec.multimode_fill)
    beam = pump.PumpBeam(spec.pump_power, spec.pump_waist, material.pump_wavelength,
                         m2=spec.pump_m2, waist_position=spec.pump_waist_position)
    return EndPumpedLaser(material=material, doping=spec.doping,
                          crystal_length=spec.crystal_length, pump_beam=beam,
                          cavity=cavity_factory(spec), crystal_element=CRYSTAL_LENS_NAME,
                          output_coupling=spec.output_coupling,
                          passive_loss=spec.passive_loss, pump_passes=spec.pump_passes,
                          effective_absorption=spec.effective_absorption)


def round_trip_mode(cavity) -> dict:
    """What the resonator step plots: the TEM00 radius over one round trip.

    Shared by the Qt wizard and the browser version. A standing-wave cavity
    is traced from end mirror 1 to end mirror 2 and back to mirror 1; a ring
    once around the loop (see :meth:`laserdesign.abcd._Resonator.round_trip_profile`).

    Returns
    -------
    dict
        ``"t"`` and ``"s"``: :class:`laserdesign.abcd.ModeProfile` for each
        plane; ``"landmarks"``: ``[(z, label), ...]`` with the crystal shown as
        ``"crystal"`` and labels closer than 3 % of the path merged; ``"xlabel"`` and ``"title"`` for the axis and plot.
    """
    profiles = {plane: cavity.round_trip_profile(plane) for plane in ("t", "s")}
    # Landmarks closer than 3 % of the path share one label (e.g. M1 and a
    # crystal bonded to it), so the text does not overprint.
    span = float(profiles["t"].z[-1]) or 1.0
    landmarks: list[tuple[float, str]] = []
    for z, name in profiles["t"].landmarks:
        name = "crystal" if name == CRYSTAL_LENS_NAME else name
        if landmarks and z - landmarks[-1][0] < 0.03 * span:
            landmarks[-1] = (landmarks[-1][0], f"{landmarks[-1][1]}, {name}")
        else:
            landmarks.append((z, name))
    standing = isinstance(cavity, abcd.StandingWaveCavity)
    return {**profiles, "landmarks": landmarks,
            "xlabel": ("path from mirror 1 to mirror 2 and back [mm]" if standing
                       else "position around the ring [mm]"),
            "title": "TEM00 mode over one round trip" if standing
            else "TEM00 mode around the ring"}
