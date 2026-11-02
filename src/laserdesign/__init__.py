"""laserdesign: a physics library for designing solid state lasers.

Modules
-------
units
    SI unit helpers and constants.
materials
    Gain media database (:class:`~laserdesign.materials.GainMedium`).
gaussian
    Gaussian beams and the complex beam parameter.
abcd
    ABCD matrices, standing-wave and ring resonators, eigenmodes, stability.
pump
    Pump absorption and pump beam geometry.
thermal
    Temperature profiles, thermal lensing and fracture limits.
gain
    Threshold, slope efficiency and CW output (spatially resolved).
qswitch
    Active Q-switching: analytic theory and rate-equation simulation.
passive_qswitch
    Passive Q-switching with a saturable absorber such as Cr:YAG.
modelocking
    Mode-locking estimates: AM, soliton and SESAM mode locking, QML limit.
kerr
    Kerr-lens mode locking: self-consistent Kerr lens and KLM strength.
beam_quality
    M^2 from fields, thermal aberration and caustic fits.
design
    :class:`~laserdesign.design.EndPumpedLaser` and
    :class:`~laserdesign.design.SidePumpedRodLaser`, which combine all of the
    above for standing-wave and ring resonators.

All quantities are in SI units; see :mod:`laserdesign.units`.
"""

from . import (abcd, beam_quality, design, gain, gaussian, kerr, materials, modelocking,
               passive_qswitch, pump, qswitch, thermal, units)
from .design import EndPumpedLaser, OperatingPoint, SidePumpedRodLaser
from .materials import MATERIALS, GainMedium, get_material

__version__ = "0.2.0"

__all__ = [
    "abcd", "beam_quality", "design", "gain", "gaussian", "kerr", "materials",
    "modelocking", "passive_qswitch", "pump", "qswitch", "thermal", "units",
    "EndPumpedLaser", "OperatingPoint", "SidePumpedRodLaser",
    "GainMedium", "MATERIALS", "get_material", "__version__",
]
