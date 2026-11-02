"""Pump absorption, pump beam geometry and pump/laser mode overlap.

The models here describe longitudinal (end) pumping by a focused diode or
laser beam, which is the configuration used by all three example designs.
Pump light is absorbed following Beer-Lambert's law (Milonni & Eberly,
*Laser Physics*, sec. 7.2):

.. math::

    P(z) = P_0 e^{-\\alpha z}.

The pump beam is treated as an embedded Gaussian with beam quality
:math:`M^2_p`, which is how fibre-coupled diodes are usually specified.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate

from . import gaussian


def absorbed_fraction(alpha: float, length: float, passes: int = 1,
                      back_reflectance: float = 1.0) -> float:
    """Fraction of incident pump power absorbed in the crystal.

    Parameters
    ----------
    alpha : float
        Pump absorption coefficient [1/m].
    length : float
        Crystal length [m].
    passes : int
        1 for single pass, 2 if the unabsorbed pump is reflected back.
    back_reflectance : float
        Reflectance of the back mirror for the second pass.

    Returns
    -------
    float
        Absorbed fraction ``eta_abs`` between 0 and 1.
    """
    t = np.exp(-alpha * length)
    if passes == 1:
        return float(1 - t)
    if passes == 2:
        return float((1 - t) * (1 + back_reflectance * t))
    raise ValueError("passes must be 1 or 2")


def absorption_length_for(fraction: float, alpha: float) -> float:
    """Crystal length needed to absorb ``fraction`` of the pump in one pass [m]."""
    if not 0 < fraction < 1:
        raise ValueError("fraction must be between 0 and 1")
    return float(-np.log(1 - fraction) / alpha)


def heat_load(absorbed_power: float, heat_fraction: float) -> float:
    """Heat deposited in the crystal ``P_heat = xi P_abs`` [W]."""
    return absorbed_power * heat_fraction


@dataclass
class PumpBeam:
    """A focused pump beam inside the gain crystal.

    Parameters
    ----------
    power : float
        Incident pump power [W].
    waist : float
        Pump waist radius (1/e^2) inside the crystal [m].
    wavelength : float
        Vacuum pump wavelength [m].
    m2 : float
        Pump beam quality factor (fibre-coupled diodes are often 20 to 200).
    waist_position : float
        Distance of the waist from the pumped face, inside the crystal [m].
    """

    power: float
    waist: float
    wavelength: float
    m2: float = 1.0
    waist_position: float = 0.0

    def radius(self, z, n: float = 1.0):
        """Pump radius at depth ``z`` inside a crystal of index ``n`` [m]."""
        return gaussian.beam_radius(z, self.waist, self.wavelength,
                                    z0=self.waist_position, n=n, m2=self.m2)

    def effective_radius(self, alpha: float, length: float, n: float = 1.0) -> float:
        """Absorption-weighted RMS pump radius over the crystal [m].

        Defined as

        .. math:: w_{eff}^2 = \\frac{\\int_0^L w_p^2(z) \\alpha e^{-\\alpha z} dz}
                                     {\\int_0^L \\alpha e^{-\\alpha z} dz},

        which is the radius that enters threshold and thermal-lens formulas
        when the pump diverges noticeably in the crystal.
        """
        num, _ = integrate.quad(lambda z: self.radius(z, n) ** 2 * np.exp(-alpha * z), 0, length)
        den, _ = integrate.quad(lambda z: np.exp(-alpha * z), 0, length)
        return float(np.sqrt(num / den))
