"""Mode-locking estimates: pulse duration limits, AM and SESAM mode locking.

The functions here are design-level estimates, not full pulse simulations.
They answer the questions you need early in a design: how short can the
pulses be, what pulse energy is needed to avoid Q-switched mode locking, and
how the pulse width scales with modulation depth, gain and dispersion.

Pulse shapes and time-bandwidth products
----------------------------------------
Transform-limited pulses satisfy ``tau * delta_nu = K`` with ``K = 0.441``
for Gaussian and ``K = 0.315`` for sech^2 intensity profiles.

Active amplitude-modulation (AM) mode locking
---------------------------------------------
Haus's master equation (Haus, IEEE JSTQE 6, 1173 (2000)) gives a Gaussian
pulse with field width

.. math:: \\tau_a^4 = \\frac{D_g}{M_s}, \\quad D_g = \\frac{g}{\\Omega_g^2},
          \\quad M_s = \\frac{M \\omega_m^2}{2},

where ``g`` is the saturated round-trip *amplitude* gain (half of the
logarithmic round-trip power loss), :math:`\\Omega_g = \\pi \\Delta\\nu_g` the
gain half-width in rad/s, ``M`` the modulation depth and
:math:`\\omega_m = 2\\pi f_m`. The intensity FWHM is :math:`1.665\\,\\tau_a`.
This is identical to the Kuizenga-Siegman result quoted in Siegman, *Lasers*,
sec. 27.5.

Soliton mode locking
--------------------
With negative round-trip group delay dispersion ``GDD`` and self-phase
modulation coefficient :math:`\\delta_{SPM}` [rad/W], a sech^2 soliton of
energy ``E`` has (Haus 2000; Kärtner et al., IEEE JSTQE 2, 540 (1996))

.. math:: \\tau_{FWHM} = 1.763 \\, \\frac{2 |GDD|}{\\delta_{SPM} E}.

SESAM mode locking and Q-switched mode locking
----------------------------------------------
Continuous-wave mode locking with a slow saturable absorber is stable against
Q-switched mode locking when the intracavity pulse energy exceeds
(Hönninger et al., JOSA B 16, 46 (1999))

.. math:: E_p > E_{p,c} = \\sqrt{E_{sat,L} E_{sat,A} \\Delta R}.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .units import c as _c

#: Time-bandwidth products of transform-limited pulses.
TIME_BANDWIDTH = {"gaussian": 0.441, "sech2": 0.315}

#: Intensity FWHM over the field parameter, for each shape.
_FWHM_FACTOR = {"gaussian": 2 * np.sqrt(np.log(2)), "sech2": 2 * np.arccosh(np.sqrt(2))}


def transform_limited_duration(bandwidth: float, shape: str = "sech2") -> float:
    """Shortest pulse FWHM supported by a spectral FWHM ``bandwidth`` [s].

    Parameters
    ----------
    bandwidth : float
        Spectral FWHM [Hz].
    shape : {"sech2", "gaussian"}
    """
    return TIME_BANDWIDTH[shape] / bandwidth


def repetition_rate(optical_length: float, ring: bool = False) -> float:
    """Pulse repetition rate of a mode-locked laser [Hz].

    ``c / (2 L_opt)`` for a standing-wave cavity, ``c / L_opt`` for a ring.
    """
    return _c / (optical_length if ring else 2 * optical_length)


def active_am_pulse_width(round_trip_loss: float, modulation_depth: float,
                          modulation_frequency: float, gain_bandwidth: float) -> float:
    """Steady-state FWHM of an actively AM mode-locked laser [s].

    Parameters
    ----------
    round_trip_loss : float
        Logarithmic round-trip power loss ``delta``; the saturated amplitude
        gain is ``g = delta / 2``.
    modulation_depth : float
        Single-pass amplitude modulation depth ``M`` of the modulator
        (loss ``M (1 - cos(omega_m t))``, doubled for a standing-wave
        double pass if appropriate).
    modulation_frequency : float
        Modulation frequency ``f_m`` [Hz]; equal to the cavity FSR for
        fundamental mode locking with an AM modulator near an end mirror.
    gain_bandwidth : float
        Gain FWHM ``delta_nu_g`` [Hz] (Lorentzian approximated as parabolic).
    """
    g = round_trip_loss / 2
    omega_g = np.pi * gain_bandwidth
    omega_m = 2 * np.pi * modulation_frequency
    tau_a = (g / omega_g**2 / (modulation_depth * omega_m**2 / 2)) ** 0.25
    return float(_FWHM_FACTOR["gaussian"] * tau_a)


def spm_coefficient(n2: float, length: float, mode_area: float, wavelength: float,
                    passes: int = 2) -> float:
    """Round-trip self-phase-modulation coefficient ``delta_SPM`` [rad/W].

    ``delta_SPM = passes * (2 pi / lambda) n2 L / A_eff`` with
    ``A_eff = pi w^2`` for a Gaussian mode of radius ``w`` (peak-intensity
    convention).
    """
    return float(passes * 2 * np.pi / wavelength * n2 * length / mode_area)


def soliton_pulse_width(gdd_round_trip: float, spm: float, pulse_energy: float) -> float:
    """Soliton FWHM for given dispersion, SPM and intracavity pulse energy [s].

    Parameters
    ----------
    gdd_round_trip : float
        Net round-trip group delay dispersion [s^2]; must be negative.
    spm : float
        Round-trip SPM coefficient [rad/W], see :func:`spm_coefficient`.
    pulse_energy : float
        Intracavity pulse energy [J].
    """
    if gdd_round_trip >= 0:
        raise ValueError("Soliton mode locking needs negative net GDD")
    tau = 2 * abs(gdd_round_trip) / (spm * pulse_energy)
    return float(_FWHM_FACTOR["sech2"] * tau)


def soliton_required_gdd(pulse_width: float, spm: float, pulse_energy: float) -> float:
    """Net round-trip GDD needed for a soliton of the given FWHM [s^2] (negative)."""
    tau = pulse_width / _FWHM_FACTOR["sech2"]
    return float(-tau * spm * pulse_energy / 2)


def qml_threshold_energy(laser_saturation_fluence: float, laser_mode_area: float,
                         absorber_saturation_fluence: float, absorber_mode_area: float,
                         modulation_depth: float, gain_passes: int = 2) -> float:
    """Minimum intracavity pulse energy for CW mode locking (no QML) [J].

    Parameters
    ----------
    laser_saturation_fluence : float
        ``h nu / sigma`` of the gain medium [J/m^2]
        (:attr:`laserdesign.materials.GainMedium.saturation_fluence`).
    laser_mode_area : float
        ``pi w_L^2`` in the gain medium [m^2].
    absorber_saturation_fluence : float
        SESAM saturation fluence [J/m^2] (typically 10 to 100 uJ/cm^2).
    absorber_mode_area : float
        ``pi w_A^2`` on the SESAM [m^2].
    modulation_depth : float
        SESAM modulation depth ``delta R``.
    gain_passes : int
        Passes through the gain per round trip (2 in a standing-wave cavity),
        which divides the effective gain saturation energy.
    """
    e_sat_l = laser_saturation_fluence / gain_passes * laser_mode_area
    e_sat_a = absorber_saturation_fluence * absorber_mode_area
    return float(np.sqrt(e_sat_l * e_sat_a * modulation_depth))


def sesam_pulse_width_estimate(gain_bandwidth: float, round_trip_gain: float,
                               modulation_depth: float) -> float:
    """Rough FWHM of a SESAM mode-locked laser without soliton shaping [s].

    ``tau ~ (1.07 / delta_nu_g) sqrt(g / delta R)`` (Paschotta & Keller,
    Appl. Phys. B 73, 653 (2001)), assuming the absorber is saturated a few
    times over. ``round_trip_gain`` is the saturated power gain per round trip
    (equal to the round-trip loss). Treat this as an order-of-magnitude design
    guide.
    """
    return float(1.07 / gain_bandwidth * np.sqrt(round_trip_gain / modulation_depth))


@dataclass
class SesamCheck:
    """Summary returned by :func:`sesam_design_check`."""

    repetition_rate: float
    pulse_energy: float
    qml_threshold: float
    qml_margin: float
    absorber_saturation: float
    pulse_width_estimate: float
    transform_limit: float

    @property
    def cw_mode_locked(self) -> bool:
        """True when the pulse energy exceeds the QML threshold."""
        return self.qml_margin > 1


def sesam_design_check(average_intracavity_power: float, optical_length: float,
                       laser_saturation_fluence: float, laser_mode_radius: float,
                       absorber_saturation_fluence: float, absorber_mode_radius: float,
                       modulation_depth: float, gain_bandwidth: float,
                       round_trip_loss: float, ring: bool = False) -> SesamCheck:
    """Evaluate a SESAM mode-locked design in one call.

    Returns repetition rate, intracavity pulse energy, QML threshold and margin
    (pulse energy / threshold), absorber saturation parameter
    ``E_p / E_sat,A`` (aim for 3 to 5) and the pulse width estimates.

    ``optical_length`` is the one-way optical length of a standing-wave
    cavity, or the full loop for a ring (``ring=True``). In a ring the pulse
    passes the gain once per round trip, so the QML threshold uses
    ``gain_passes=1``; the SESAM is hit once per round trip in both cases.
    """
    f_rep = repetition_rate(optical_length, ring=ring)
    e_p = average_intracavity_power / f_rep
    a_l = np.pi * laser_mode_radius**2
    a_a = np.pi * absorber_mode_radius**2
    e_c = qml_threshold_energy(laser_saturation_fluence, a_l, absorber_saturation_fluence,
                               a_a, modulation_depth, gain_passes=1 if ring else 2)
    return SesamCheck(
        repetition_rate=f_rep,
        pulse_energy=e_p,
        qml_threshold=e_c,
        qml_margin=e_p / e_c,
        absorber_saturation=e_p / (absorber_saturation_fluence * a_a),
        pulse_width_estimate=sesam_pulse_width_estimate(gain_bandwidth, round_trip_loss,
                                                        modulation_depth),
        transform_limit=transform_limited_duration(gain_bandwidth),
    )
