"""Active Q-switching: analytic pulse estimates and rate-equation simulation.

Analytic theory
---------------
With the cavity switched instantly from high to low loss, and pumping and
spontaneous decay neglected during the pulse, the rate equations for the
inversion density ``N`` and the photon number give the classic results
(Siegman, *Lasers*, ch. 26; Milonni & Eberly, *Laser Physics*, sec. 6.7;
Degnan, IEEE JQE 25, 214 (1989)). With ``r = N_i / N_th`` the ratio of initial
to threshold inversion:

* the final inversion ``N_f`` satisfies
  :math:`N_i - N_f = N_{th} \\ln(N_i / N_f)`;
* the extraction efficiency is :math:`\\eta = 1 - N_f/N_i`;
* the output energy is

  .. math:: E = \\frac{A h\\nu}{2\\sigma\\gamma}\\,\\delta_{oc}\\,\\ln\\frac{N_i}{N_f};

* the peak output power is

  .. math:: P_{pk} = \\frac{A h\\nu\\,\\delta\\,\\delta_{oc}}{2\\sigma\\gamma\\,t_{rt}}
            \\left(r - 1 - \\ln r\\right);

* and the pulse width is estimated as ``E / P_pk``.

Here ``A`` is the effective mode area in the gain medium, ``delta`` the total
and ``delta_oc`` the output-coupling logarithmic round-trip loss, ``t_rt`` the
cavity round-trip time and ``gamma`` the inversion reduction factor (1 for a
four-level laser, ``1 + sigma_a/sigma_e`` style values up to 2 for
quasi-three-level media). The factor 2 is the number of gain passes per
round trip in a standing-wave resonator; every function takes
``gain_passes=1`` for a unidirectional ring, which doubles the energy for the
same inversion ratio because the same round-trip gain needs twice the
stored inversion.

Repetitive Q-switching with CW pumping
--------------------------------------
Between pulses the inversion recovers toward its CW-pumped asymptote
``N_inf`` with the upper-state lifetime, so at repetition rate ``f``

.. math:: N_i = N_\\infty - (N_\\infty - N_f) e^{-1/(f\\tau)}.

:func:`repetitive_q_switch` solves this together with the extraction
condition self-consistently. Writing ``N_inf / N_th`` as the ratio of
absorbed pump power to the CW threshold (absorbed) power of the same,
low-loss cavity keeps the spatial overlap consistent with
:mod:`laserdesign.gain`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize


def gaussian_mode_area(w: float) -> float:
    """Effective area ``pi w^2 / 2`` of a TEM00 mode with 1/e^2 radius ``w`` [m^2]."""
    return float(np.pi * w**2 / 2)


def final_inversion_fraction(r: float) -> float:
    """Ratio ``N_f / N_i`` after a Q-switched pulse.

    Solves ``r (1 - x) = -ln x`` for the non-trivial root ``x < 1``.

    Parameters
    ----------
    r : float
        Initial inversion over threshold inversion; must exceed 1.
    """
    if r <= 1:
        raise ValueError("No pulse forms unless the initial inversion exceeds threshold (r > 1)")

    def f(x):
        return r * (1 - x) + np.log(x)

    return float(optimize.brentq(f, 1e-300, 1 / r, xtol=1e-15, rtol=1e-14))


def extraction_efficiency(r: float) -> float:
    """Energy extraction efficiency ``1 - N_f / N_i``."""
    return 1.0 - final_inversion_fraction(r)


@dataclass
class QSwitchPulse:
    """Analytic Q-switched pulse parameters.

    Attributes
    ----------
    energy : float
        Output pulse energy [J].
    peak_power : float
        Output peak power [W].
    pulse_width : float
        ``energy / peak_power`` [s], close to the FWHM for typical pulses.
    extraction_efficiency : float
    initial_ratio : float
        ``N_i / N_th``.
    """

    energy: float
    peak_power: float
    pulse_width: float
    extraction_efficiency: float
    initial_ratio: float


def q_switch_pulse(initial_ratio: float, mode_area: float, emission_cross_section: float,
                   photon_energy: float, delta: float, delta_oc: float,
                   round_trip_time: float, gamma: float = 1.0,
                   gain_passes: int = 2) -> QSwitchPulse:
    """Analytic energy, peak power and width of a Q-switched pulse.

    Parameters
    ----------
    initial_ratio : float
        ``r = N_i / N_th`` (with ``N_th`` the threshold of the *open*
        Q-switch cavity).
    mode_area : float
        Effective mode area in the gain medium [m^2].
    emission_cross_section : float
        [m^2]; for quasi-three-level media use ``sigma_e + sigma_a``.
    photon_energy : float
        Laser photon energy [J].
    delta, delta_oc : float
        Total and output-coupler logarithmic round-trip losses.
    round_trip_time : float
        Cavity round-trip time [s].
    gamma : float
        Inversion reduction factor.
    gain_passes : int
        2 for a standing-wave, 1 for a ring resonator.
    """
    r = initial_ratio
    x = final_inversion_fraction(r)
    ln_ratio = -np.log(x)
    pref = mode_area * photon_energy / (gain_passes * emission_cross_section * gamma)
    energy = pref * delta_oc * ln_ratio
    peak = pref * delta * delta_oc * (r - 1 - np.log(r)) / round_trip_time
    return QSwitchPulse(float(energy), float(peak), float(energy / peak), 1 - x, r)


def repetitive_q_switch(pump_ratio: float, rep_rate: float, lifetime: float) -> tuple[float, float]:
    """Steady-state initial and final inversion ratios at a repetition rate.

    Parameters
    ----------
    pump_ratio : float
        ``N_inf / N_th``, the inversion the pump would build up with no
        lasing, relative to threshold. For end pumping use absorbed pump over
        absorbed CW threshold power of the same cavity.
    rep_rate : float
        Pulse repetition frequency [Hz].
    lifetime : float
        Upper-state lifetime [s].

    Returns
    -------
    r_i, r_f : float
        Initial and final inversion over threshold. ``r_i <= 1`` means the
        laser cannot reach threshold between pulses.
    """
    decay = np.exp(-1 / (rep_rate * lifetime))
    r_inf = pump_ratio

    def g(ri):
        return r_inf - (r_inf - ri * final_inversion_fraction(ri)) * decay - ri

    lo = 1 + 1e-9
    if g(lo) <= 0:
        return float(r_inf * (1 - decay)), 0.0
    ri = optimize.brentq(g, lo, r_inf, xtol=1e-12)
    return float(ri), float(ri * final_inversion_fraction(ri))


@dataclass
class QSwitchSimulation:
    """Result of :func:`simulate_q_switch`.

    Attributes
    ----------
    t : ndarray
        Time after opening the switch [s].
    output_power : ndarray
        Output power [W].
    inversion_ratio : ndarray
        ``N(t) / N_th``.
    energy, peak_power, fwhm, buildup_time : float
        Pulse energy [J], peak power [W], FWHM [s] and time from switching to
        the peak [s].
    """

    t: np.ndarray
    output_power: np.ndarray
    inversion_ratio: np.ndarray
    energy: float
    peak_power: float
    fwhm: float
    buildup_time: float


def simulate_q_switch(initial_ratio: float, mode_area: float, emission_cross_section: float,
                      photon_energy: float, delta: float, delta_oc: float,
                      round_trip_time: float, gamma: float = 1.0,
                      initial_photons: float = 1.0, n_points: int = 4000,
                      gain_passes: int = 2) -> QSwitchSimulation:
    """Integrate the Q-switch rate equations numerically.

    The equations, written for the inversion ratio ``n = N / N_th`` and the
    logarithm of the intracavity photon number ``Phi`` (the logarithm keeps the
    build-up from one photon well conditioned), are

    .. math::

        \\frac{d \\ln\\Phi}{dt} = \\frac{\\delta (n - 1)}{t_{rt}}, \\qquad
        \\frac{dn}{dt} = -\\frac{p\\gamma\\sigma}{A t_{rt}} n \\Phi,

    with ``p = gain_passes``.

    Pumping and spontaneous decay during the pulse are neglected, as in the
    analytic theory, so this is mostly useful for pulse shape and build-up
    time. The output power is ``P = Phi h nu delta_oc / t_rt``.
    """
    tau_c = round_trip_time / delta
    r = initial_ratio
    if r <= 1:
        raise ValueError("initial_ratio must exceed 1")
    k = gain_passes * gamma * emission_cross_section / (mode_area * round_trip_time)

    def rhs(_t, y):
        ln_phi, n = y
        return [delta * (n - 1) / round_trip_time, -k * n * np.exp(ln_phi)]

    # Rough build-up time to ~1e15 photons, plus a generous tail.
    t_build = tau_c * 40 / (r - 1)
    t_end = t_build + 60 * tau_c * max(1.0, 1 / (r - 1))
    sol = integrate.solve_ivp(rhs, (0, t_end), [np.log(initial_photons), r],
                              method="LSODA", rtol=1e-9, atol=[1e-9, 1e-12],
                              dense_output=True)
    t = np.linspace(0, t_end, n_points)
    ln_phi, n = sol.sol(t)
    power = np.exp(ln_phi) * photon_energy * delta_oc / round_trip_time

    # Refine around the pulse
    i_pk = int(np.argmax(power))
    above = np.where(power > power[i_pk] * 1e-4)[0]
    t0, t1 = t[max(above[0] - 1, 0)], t[min(above[-1] + 1, len(t) - 1)]
    t = np.linspace(t0, t1, n_points)
    ln_phi, n = sol.sol(t)
    power = np.exp(ln_phi) * photon_energy * delta_oc / round_trip_time
    i_pk = int(np.argmax(power))
    half = np.where(power >= power[i_pk] / 2)[0]
    fwhm = t[half[-1]] - t[half[0]]
    energy = float(integrate.trapezoid(power, t))
    return QSwitchSimulation(t, power, n, energy, float(power[i_pk]), float(fwhm),
                             float(t[i_pk]))
