"""A serialisable description of a laser design, independent of Qt.

The GUI edits a :class:`DesignSpec`; :func:`build_laser` turns it into a
:class:`laserdesign.design.EndPumpedLaser`. Keeping this layer free of Qt
means it can be tested, saved as JSON and reused from scripts.

All values are SI, as in the rest of the library. The resonator is a list of
element dictionaries describing one pass from end mirror 1 to end mirror 2:

``{"type": "crystal"}``
    Where the gain crystal sits. Expanded with
    :func:`laserdesign.abcd.crystal_with_thermal_lens`. Exactly one is required.
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

Every element may also carry a ``"name"``.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import abcd, pump
from ..design import EndPumpedLaser
from ..materials import GainMedium, get_material

ELEMENT_TYPES = ("crystal", "space", "mirror", "lens", "medium", "brewster")
OPERATION_MODES = ("cw", "qswitch", "modelock")
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
    # Pump
    pump_power: float = 20.0
    pump_waist: float = 200e-6
    pump_m2: float = 30.0
    pump_waist_position: float = 1e-3
    pump_passes: int = 1
    # Resonator
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


def _element(e: dict, material: GainMedium, length: float, f_thermal: float) -> list:
    t = e["type"]
    name = e.get("name", "")
    if t == "crystal":
        els = abcd.crystal_with_thermal_lens(length, material.refractive_index, f_thermal,
                                             name="crystal")
        return els
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


def cavity_factory(spec: DesignSpec):
    """Return ``f_thermal -> StandingWaveCavity`` for the spec's resonator."""
    material = spec.gain_medium()

    def cavity(f_thermal: float) -> abcd.StandingWaveCavity:
        els = []
        for e in spec.elements:
            els.extend(_element(e, material, spec.crystal_length, f_thermal))
        return abcd.StandingWaveCavity(els, R1=spec.R1, R2=spec.R2,
                                       wavelength=material.laser_wavelength)

    return cavity


def build_laser(spec: DesignSpec) -> EndPumpedLaser:
    """Build the :class:`EndPumpedLaser` described by ``spec``.

    Raises
    ------
    ValueError
        If :meth:`DesignSpec.validate` reports problems.
    """
    problems = spec.validate()
    if problems:
        raise ValueError("; ".join(problems))
    material = spec.gain_medium()
    beam = pump.PumpBeam(spec.pump_power, spec.pump_waist, material.pump_wavelength,
                         m2=spec.pump_m2, waist_position=spec.pump_waist_position)
    return EndPumpedLaser(material=material, doping=spec.doping,
                          crystal_length=spec.crystal_length, pump_beam=beam,
                          cavity=cavity_factory(spec), crystal_element=CRYSTAL_LENS_NAME,
                          output_coupling=spec.output_coupling,
                          passive_loss=spec.passive_loss, pump_passes=spec.pump_passes,
                          effective_absorption=spec.effective_absorption)
