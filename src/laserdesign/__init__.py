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
modelocking
    Mode-locking estimates: AM, soliton and SESAM mode locking, QML limit.
beam_quality
    M^2 from fields, thermal aberration and caustic fits.
design
    :class:`~laserdesign.design.EndPumpedLaser`, which combines all of the
    above.

All quantities are in SI units; see :mod:`laserdesign.units`.
"""

from . import (abcd, beam_quality, design, gain, gaussian, materials, modelocking, pump,
               qswitch, thermal, units)
from .design import EndPumpedLaser, OperatingPoint
from .materials import MATERIALS, GainMedium, get_material

__version__ = "0.1.0"

__all__ = [
    "abcd", "beam_quality", "design", "gain", "gaussian", "materials", "modelocking",
    "pump", "qswitch", "thermal", "units", "EndPumpedLaser", "OperatingPoint",
    "GainMedium", "MATERIALS", "get_material", "__version__",
]
