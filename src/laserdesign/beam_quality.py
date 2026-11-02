"""Beam quality (M^2) estimates.

Three tools are provided:

1. :func:`m2_radial_field` computes the second-moment beam quality factor
   (ISO 11146; Siegman, "New developments in laser resonators", SPIE 1224
   (1990)) of any radially symmetric complex field. For one transverse
   coordinate,

   .. math::

       M^2 = 2 \\sqrt{\\langle x^2 \\rangle \\langle k_x^2 \\rangle
                  - \\langle x k_x \\rangle^2},

   which is 1 for a Gaussian and is unchanged by a pure lens.
2. :func:`m2_thermal_aberration` uses (1) to find the beam quality of a TEM00
   mode after one round trip through the non-parabolic thermal lens of an
   end-pumped crystal (:func:`laserdesign.thermal.end_pumped_opd`). This is
   the dominant source of M^2 degradation in high-power end-pumped lasers.
3. :func:`m2_from_mode_size_ratio` is the usual multimode rule of thumb: if
   the pumped region is larger than the TEM00 mode, higher-order modes reach
   threshold and the output fills the pumped region, so
   ``M^2 ~ (w_p / w_00)^2``.

:func:`fit_m2_caustic` fits measured beam radii versus position (the ISO
11146 hyperbola) so that measurements can be compared with predictions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate

from .thermal import end_pumped_opd


def m2_radial_field(r: np.ndarray, field: np.ndarray) -> float:
    """Second-moment M^2 (per Cartesian axis) of a radially symmetric field.

    Parameters
    ----------
    r : ndarray
        Radial grid from 0 out to where the field is negligible [m].
    field : ndarray of complex
        Complex field amplitude on ``r``.

    Notes
    -----
    For a radially symmetric field ``E(r) = A(r) exp(i phi(r))``:

    * ``<x^2> = <r^2> / 2``
    * ``<k_x^2> = (1/2) int |dE/dr|^2 dA / int |E|^2 dA``
    * ``<x k_x> = (1/2) int r A^2 phi'(r) dA / int |E|^2 dA``
    """
    r = np.asarray(r, dtype=float)
    e = np.asarray(field, dtype=complex)
    da = 2 * np.pi * r
    inten = np.abs(e) ** 2
    norm = integrate.trapezoid(inten * da, r)
    x2 = 0.5 * integrate.trapezoid(r**2 * inten * da, r) / norm
    de = np.gradient(e, r)
    k2 = 0.5 * integrate.trapezoid(np.abs(de) ** 2 * da, r) / norm
    # phase gradient times intensity: Im(conj(E) dE/dr) = A^2 phi'
    xk = 0.5 * integrate.trapezoid(r * np.imag(np.conj(e) * de) * da, r) / norm
    return float(2 * np.sqrt(max(x2 * k2 - xk**2, 0.0)))


def m2_thermal_aberration(laser_radius: float, pump_radius: float, heat_power: float,
                          thermal_conductivity: float, dn_dT: float, wavelength: float,
                          passes: int = 2, extra_coefficient: float = 0.0,
                          n_points: int = 6000) -> float:
    """M^2 of a TEM00 beam after passing an end-pumped thermal lens.

    Parameters
    ----------
    laser_radius : float
        TEM00 radius in the crystal [m].
    pump_radius : float
        Pump (heat source) radius [m].
    heat_power : float
        Heat load [W].
    thermal_conductivity, dn_dT : float
        Material constants.
    wavelength : float
        Vacuum laser wavelength [m].
    passes : int
        Number of passes through the crystal (2 for one round trip of a
        standing-wave cavity).

    Notes
    -----
    This is the single-round-trip degradation of an ideal Gaussian. In a
    resonator the cavity partly filters the aberration, so the measured M^2 of
    a TEM00 laser is usually lower; the value is a useful upper bound and a
    way to compare designs (Siegman, Appl. Opt. 32, 5893 (1993)).
    """
    r = np.linspace(0, 4 * laser_radius, n_points)
    opd = passes * end_pumped_opd(r, heat_power, pump_radius, thermal_conductivity,
                                  dn_dT, extra_coefficient)
    field = np.exp(-(r**2) / laser_radius**2) * np.exp(1j * 2 * np.pi / wavelength * opd)
    return m2_radial_field(r, field)


def m2_from_mode_size_ratio(pump_radius: float, tem00_radius: float) -> float:
    """Multimode rule of thumb ``M^2 ~ max(1, (w_p / w_00)^2)``."""
    return float(max(1.0, (pump_radius / tem00_radius) ** 2))


def combine_m2(*m2_values: float) -> float:
    """Combine independent contributions as ``M^4_tot - 1 = sum(M^4_i - 1)``.

    This quadrature rule is an engineering approximation for independent,
    uncorrelated degradations (for example a multimode beam passing a weak
    aberration). It reduces to the single value when the others are 1 and
    should be checked against measurement with :func:`fit_m2_caustic`.
    """
    total = 1 + sum(m**2 - 1 for m in m2_values)  # (M^2)^2 = M^4
    return float(np.sqrt(total))


@dataclass
class CausticFit:
    """Result of :func:`fit_m2_caustic`."""

    m2: float
    waist: float
    waist_position: float
    rayleigh_range: float


def fit_m2_caustic(z, w, wavelength: float) -> CausticFit:
    """Fit ``w(z)^2 = w0^2 + (M^2 lambda / (pi w0))^2 (z - z0)^2`` (ISO 11146).

    Parameters
    ----------
    z : array
        Positions along the beam [m].
    w : array
        Measured second-moment (or 1/e^2) radii [m].
    wavelength : float
        Vacuum wavelength [m].
    """
    z = np.asarray(z, dtype=float)
    w2 = np.asarray(w, dtype=float) ** 2
    c2, c1, c0 = np.polyfit(z, w2, 2)
    if c2 <= 0:
        raise ValueError("Data do not describe a beam caustic (curvature <= 0)")
    z0 = -c1 / (2 * c2)
    w0_sq = c0 - c1**2 / (4 * c2)
    if w0_sq <= 0:
        raise ValueError("Fit gives a non-physical waist; add points near the focus")
    w0 = np.sqrt(w0_sq)
    m2 = np.pi / wavelength * np.sqrt(c0 * c2 - c1**2 / 4)
    return CausticFit(float(m2), float(w0), float(z0), float(w0 / np.sqrt(c2)))
