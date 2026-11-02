"""Gaussian beams and the complex beam parameter.

This module uses the *reduced* complex beam parameter of Siegman, *Lasers*,
chapter 20: ``q_hat = q / n``, so that

.. math::

    \\frac{1}{\\hat q} = \\frac{n}{R} - i \\frac{\\lambda_0}{\\pi w^2},

where :math:`\\lambda_0` is the **vacuum** wavelength. With this
convention the spot size can be read off ``q_hat`` without knowing the local
refractive index, and ABCD matrices for dielectric media are written in
reduced form (see :mod:`laserdesign.abcd`).

A real beam with beam quality factor :math:`M^2` propagates like a Gaussian
beam with wavelength :math:`M^2 \\lambda_0` ("embedded Gaussian"), which is
how the ``m2`` arguments below are used.
"""

from __future__ import annotations

import numpy as np


def q_from_waist(w0: float, wavelength: float, z: float = 0.0, n: float = 1.0,
                 m2: float = 1.0) -> complex:
    """Reduced q parameter a distance ``z`` after a waist of radius ``w0``.

    Parameters
    ----------
    w0 : float
        1/e^2 intensity waist radius [m].
    wavelength : float
        Vacuum wavelength [m].
    z : float
        Physical distance from the waist [m] (positive = after the waist).
    n : float
        Refractive index of the medium the beam is in.
    m2 : float
        Beam quality factor.

    Returns
    -------
    complex
        Reduced complex beam parameter ``q / n`` [m].
    """
    z_r = rayleigh_range(w0, wavelength, n=n, m2=m2)
    return (z + 1j * z_r) / n


def q_from_w_R(w: float, R: float, wavelength: float, n: float = 1.0,
               m2: float = 1.0) -> complex:
    """Reduced q parameter from spot size and wavefront radius of curvature.

    Parameters
    ----------
    w : float
        1/e^2 intensity radius [m].
    R : float
        Wavefront radius of curvature [m]; use ``numpy.inf`` for a flat
        wavefront.
    wavelength : float
        Vacuum wavelength [m].
    n : float
        Refractive index of the local medium.
    m2 : float
        Beam quality factor.
    """
    inv = (n / R if np.isfinite(R) else 0.0) - 1j * m2 * wavelength / (np.pi * w**2)
    return 1.0 / inv


def spot_size(q: complex, wavelength: float, m2: float = 1.0) -> float:
    """1/e^2 intensity radius from the reduced q parameter [m]."""
    im = np.imag(1.0 / q)
    if im >= 0:
        raise ValueError("q does not describe a confined beam (Im(1/q) >= 0)")
    return float(np.sqrt(-m2 * wavelength / (np.pi * im)))


def radius_of_curvature(q: complex, n: float = 1.0) -> float:
    """Wavefront radius of curvature [m] from the reduced q parameter.

    Returns ``inf`` at a waist.
    """
    re = np.real(1.0 / q)
    if re == 0:
        return np.inf
    return float(n / re)


def rayleigh_range(w0: float, wavelength: float, n: float = 1.0,
                   m2: float = 1.0) -> float:
    """Rayleigh range ``pi n w0^2 / (M^2 lambda_0)`` [m] (physical length)."""
    return np.pi * n * w0**2 / (m2 * wavelength)


def waist_from_q(q: complex, wavelength: float, n: float = 1.0,
                 m2: float = 1.0) -> tuple[float, float]:
    """Waist radius and the physical distance from the current plane to it.

    Parameters
    ----------
    q : complex
        Reduced q parameter at the current plane.

    Returns
    -------
    w0 : float
        Waist radius [m].
    z_to_waist : float
        Distance to the waist [m]; positive means the waist lies ahead.
    """
    qq = q * n  # physical q = z + i zR
    z_r = np.imag(qq)
    w0 = np.sqrt(z_r * m2 * wavelength / (np.pi * n))
    return float(w0), float(-np.real(qq))


def beam_radius(z: np.ndarray | float, w0: float, wavelength: float,
                z0: float = 0.0, n: float = 1.0, m2: float = 1.0):
    """Beam radius ``w(z) = w0 sqrt(1 + ((z - z0)/z_R)^2)`` [m]."""
    z_r = rayleigh_range(w0, wavelength, n=n, m2=m2)
    return w0 * np.sqrt(1.0 + ((np.asarray(z) - z0) / z_r) ** 2)


def divergence_half_angle(w0: float, wavelength: float, m2: float = 1.0) -> float:
    """Far-field half-angle divergence ``M^2 lambda / (pi w0)`` in air [rad]."""
    return m2 * wavelength / (np.pi * w0)


def gouy_phase(z: float, z_r: float) -> float:
    """Gouy phase ``arctan(z / z_R)`` [rad]."""
    return float(np.arctan2(z, z_r))
