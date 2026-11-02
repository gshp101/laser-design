"""Thermal effects in the gain medium: temperature rise, thermal lens, fracture.

End pumping with a Gaussian pump
--------------------------------
For a heat source with a Gaussian transverse profile of radius ``w_p``
(1/e^2) deposited in a long rod of radius ``r_0`` with a cooled barrel, the
steady-state heat equation gives (Innocenzi et al., Appl. Phys. Lett. 56,
1831 (1990))

.. math::

    T(r) - T(r_0) = \\frac{P_h}{4 \\pi K L}
        \\left[F\\!\\left(\\frac{2 r_0^2}{w_p^2}\\right)
             - F\\!\\left(\\frac{2 r^2}{w_p^2}\\right)\\right],
    \\qquad F(x) = \\gamma + \\ln x + E_1(x),

where :math:`P_h` is the total heat load, :math:`K` the thermal
conductivity and :math:`\\gamma` Euler's constant. Near the axis
:math:`F(x) \\approx x`, so the temperature is parabolic and the crystal acts
as a thin lens of focal length

.. math::

    f_{th} = \\frac{\\pi K w_p^2}{P_h \\, \\chi},

with :math:`\\chi = dn/dT` (plus optional end-face bulging and photo-elastic
contributions supplied by the user). Away from the axis the profile is
logarithmic; this non-parabolic part is the spherical aberration that
degrades beam quality (see :mod:`laserdesign.beam_quality`).

Uniformly side-pumped rod
-------------------------
For uniform heating of a rod of radius ``r_0`` the temperature is exactly
parabolic and (Koechner, *Solid-State Laser Engineering*, eq. 7.41)

.. math::

    f = \\frac{K A}{P_h} \\left(\\frac{1}{2}\\frac{dn}{dT} + \\alpha_T C n_0^3
        + \\frac{\\alpha_T r_0 (n_0 - 1)}{L}\\right)^{-1}.
"""

from __future__ import annotations

import numpy as np
from scipy import special

from .materials import GainMedium


def _F(x):
    """``gamma + ln(x) + E1(x)``, with the correct limit ``F(0) = 0``."""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    small = x < 1e-8
    xs = x[~small]
    out[~small] = np.euler_gamma + np.log(xs) + special.exp1(xs)
    out[small] = x[small]  # series: F(x) = x - x^2/4 + ...
    return out if out.ndim else float(out)


def end_pumped_focal_length(heat_power: float, pump_radius: float,
                            thermal_conductivity: float, dn_dT: float,
                            extra_coefficient: float = 0.0) -> float:
    """Thermal focal length of an end-pumped crystal [m].

    Parameters
    ----------
    heat_power : float
        Total heat deposited in the crystal [W] (``xi * P_abs``).
    pump_radius : float
        Pump 1/e^2 radius [m]; use the absorption-weighted value from
        :meth:`laserdesign.pump.PumpBeam.effective_radius` for a diverging
        pump.
    thermal_conductivity : float
        [W/(m K)].
    dn_dT : float
        Thermo-optic coefficient [1/K].
    extra_coefficient : float
        Additional effective thermo-optic contribution [1/K], for example
        end-face bulging ``~2 (n-1) alpha_T w_p / L`` or a photo-elastic term.

    Returns
    -------
    float
        Focal length [m]; ``inf`` when there is no heat. Negative means a
        diverging lens (negative dn/dT).
    """
    chi = dn_dT + extra_coefficient
    if heat_power == 0 or chi == 0:
        return np.inf
    return float(np.pi * thermal_conductivity * pump_radius**2 / (heat_power * chi))


def thermal_lens(material: GainMedium, absorbed_power: float, pump_radius: float,
                 extra_coefficient: float = 0.0) -> float:
    """Convenience wrapper for :func:`end_pumped_focal_length` using a material.

    Uses the material's heat fraction, conductivity and dn/dT.
    """
    p_h = absorbed_power * material.effective_heat_fraction
    return end_pumped_focal_length(p_h, pump_radius, material.thermal_conductivity,
                                   material.dn_dT, extra_coefficient)


def end_pumped_temperature(r, heat_power: float, pump_radius: float,
                           thermal_conductivity: float, length: float,
                           rod_radius: float):
    """Temperature rise relative to the cooled rod surface [K].

    Implements the Innocenzi profile given in the module docstring, with the
    heat spread uniformly along ``length``. For strongly absorbing crystals the
    pumped face is hotter than this average; multiply ``heat_power / length``
    by ``alpha L / (1 - exp(-alpha L))`` for the peak at the face.

    Parameters
    ----------
    r : float or array
        Radial position(s) [m].
    """
    pref = heat_power / (4 * np.pi * thermal_conductivity * length)
    x0 = 2 * rod_radius**2 / pump_radius**2
    x = 2 * np.asarray(r, dtype=float) ** 2 / pump_radius**2
    return pref * (_F(x0) - _F(x))


def end_pumped_opd(r, heat_power: float, pump_radius: float,
                   thermal_conductivity: float, dn_dT: float,
                   extra_coefficient: float = 0.0):
    """Thermally induced optical path difference relative to the axis [m].

    ``OPD(r) - OPD(0) = -(chi P_h / (4 pi K)) F(2 r^2 / w_p^2)``. The result
    is independent of crystal length. A pure lens of focal length ``f`` would
    give ``-r^2 / (2 f)``.
    """
    chi = dn_dT + extra_coefficient
    x = 2 * np.asarray(r, dtype=float) ** 2 / pump_radius**2
    return -chi * heat_power / (4 * np.pi * thermal_conductivity) * _F(x)


def side_pumped_rod_focal_length(heat_power: float, rod_radius: float, length: float,
                                 thermal_conductivity: float, dn_dT: float,
                                 thermal_expansion: float = 0.0,
                                 refractive_index: float = 1.0,
                                 photoelastic_coefficient: float = 0.0) -> float:
    """Thermal focal length of a uniformly pumped, barrel-cooled rod [m].

    Koechner eq. 7.41. Set ``thermal_expansion`` and
    ``photoelastic_coefficient`` (``C_r`` or ``C_phi``) to include stress
    birefringence and end-face curvature; by default only the dn/dT term is
    used.
    """
    area = np.pi * rod_radius**2
    n0 = refractive_index
    term = (0.5 * dn_dT
            + thermal_expansion * photoelastic_coefficient * n0**3
            + thermal_expansion * rod_radius * (n0 - 1) / length)
    if heat_power == 0 or term == 0:
        return np.inf
    return float(thermal_conductivity * area / (heat_power * term))


def side_pumped_center_temperature(heat_power: float, length: float,
                                   thermal_conductivity: float) -> float:
    """Centre-to-surface temperature difference of a uniformly heated rod [K].

    ``Delta T = P_h / (4 pi K L)`` (Koechner eq. 7.7).
    """
    return float(heat_power / (4 * np.pi * thermal_conductivity * length))


def fracture_limit_per_length(thermal_shock_parameter: float) -> float:
    """Maximum heat load per unit length of a uniformly pumped rod [W/m].

    ``P_h / L = 8 pi R_T`` (Koechner eq. 7.25), where ``R_T`` is the thermal
    shock parameter. Apply a safety factor of 2 to 4 in practice.
    """
    return float(8 * np.pi * thermal_shock_parameter)
