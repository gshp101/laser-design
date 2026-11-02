"""Gain, threshold and CW output of end-pumped solid state lasers.

Loss bookkeeping
----------------
All losses are expressed as *logarithmic round-trip* losses, so that the
round-trip power factor is ``exp(-delta)``. An output coupler of
transmission ``T`` contributes ``-ln(1 - T)`` and a passive single-pass
transmission ``1 - L_i`` contributes ``-2 ln(1 - L_i)``. For small values
these reduce to the familiar ``T + L``. :func:`round_trip_loss` builds the
total.

Threshold
---------
For a Gaussian pump of radius ``w_p`` and TEM00 laser mode of radius ``w_l``,
both constant along the crystal, the incident pump power at threshold is
(Moulton, IEEE JQE 21, 1582 (1985); Risk, JOSA B 5, 1412 (1988))

.. math::

    P_{th} = \\frac{\\pi h\\nu_p (w_l^2 + w_p^2)}
                  {4 (\\sigma_e + \\sigma_a) \\tau \\eta_q \\eta_{abs}}
             \\left(\\delta + 2 \\sigma_a N_0 l\\right),

where the last term is the ground-state reabsorption of quasi-three-level
media (zero for four-level media).

Above threshold
---------------
:func:`end_pumped_cw` solves the spatially resolved steady-state rate
equations, integrated over the crystal length, for the circulating power
``P`` at which saturated round-trip gain equals loss:

.. math::

    2\\int \\left[(\\sigma_e+\\sigma_a)\\bar N_2(r) - \\sigma_a N_0 l\\right]
       s_0(r)\\, 2\\pi r\\,dr = \\delta,

with :math:`s_0 = (2/\\pi w_l^2) e^{-2r^2/w_l^2}` and :math:`\\bar N_2` the
length-integrated upper-state density saturated by the standing-wave
intensity :math:`2 P s_0(r)`. The power extracted from the gain is then
``delta * P`` and the output coupler receives the share
``T / (1 - exp(-delta))`` of it, which keeps the energy balance exact for
lumped losses of any size. Spatial hole burning and pump bleaching are
neglected. This reproduces the threshold formula above and automatically
includes the pump-to-mode overlap in the slope efficiency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize

from .materials import GainMedium


def round_trip_loss(output_coupling: float, passive_loss: float = 0.0,
                    passive_loss_is_round_trip: bool = True) -> float:
    """Logarithmic round-trip loss ``delta``.

    Parameters
    ----------
    output_coupling : float
        Output coupler transmission ``T`` (0 to 1).
    passive_loss : float
        Other losses as a fractional power loss (0 to 1).
    passive_loss_is_round_trip : bool
        If False, ``passive_loss`` is a single-pass value and is counted twice.
    """
    n = 1 if passive_loss_is_round_trip else 2
    return float(-np.log(1 - output_coupling) - n * np.log(1 - passive_loss))


def output_coupling_loss(output_coupling: float) -> float:
    """Logarithmic loss of the output coupler, ``-ln(1 - T)``."""
    return float(-np.log(1 - output_coupling))


def threshold_inversion(delta: float, sigma: float, length: float) -> float:
    """Inversion density needed for threshold, ``delta / (2 sigma l)`` [1/m^3]."""
    return delta / (2 * sigma * length)


def threshold_pump_power(material: GainMedium, laser_radius: float, pump_radius: float,
                         delta: float, absorbed_fraction: float,
                         crystal_length: float = 0.0, doping: float = 0.0) -> float:
    """Incident pump power at threshold for an end-pumped laser [W].

    Parameters
    ----------
    material : GainMedium
    laser_radius, pump_radius : float
        1/e^2 radii in the crystal [m].
    delta : float
        Logarithmic round-trip loss (see :func:`round_trip_loss`).
    absorbed_fraction : float
        Fraction of incident pump absorbed, ``eta_abs``.
    crystal_length, doping : float
        Needed only for quasi-three-level media, to compute reabsorption.
    """
    sig = material.emission_cross_section + material.laser_absorption_cross_section
    reabs = 2 * material.laser_absorption_cross_section * material.ion_density(doping) * crystal_length
    return float(
        np.pi * material.pump_photon_energy * (laser_radius**2 + pump_radius**2)
        * (delta + reabs)
        / (4 * sig * material.upper_state_lifetime * material.quantum_efficiency
           * absorbed_fraction)
    )


def slope_efficiency(material: GainMedium, output_coupling: float, delta: float,
                     absorbed_fraction: float, overlap: float = 1.0) -> float:
    """Ideal slope efficiency with respect to incident pump power.

    ``eta_s = eta_abs eta_q (lambda_p / lambda_l) eta_out eta_ov`` with the
    output fraction ``eta_out = T / (1 - exp(-delta))``: the share of the
    power lost per round trip that leaves through the output coupler.
    ``overlap`` is the mode-overlap factor (1 for a pump much smaller than the
    laser mode). For low-loss cavities ``eta_out`` reduces to ``T / (T + L)``.
    """
    return float(absorbed_fraction * material.quantum_efficiency * material.quantum_defect
                 * output_fraction(output_coupling, delta) * overlap)


def output_fraction(output_coupling: float, delta: float) -> float:
    """Share of the round-trip loss that leaves through the output coupler.

    ``T / (1 - exp(-delta))``, which is exact for lumped losses whatever their
    size.
    """
    return float(output_coupling / (1 - np.exp(-delta)))


@dataclass
class CWResult:
    """Output of :func:`end_pumped_cw`.

    Attributes
    ----------
    output_power : float
        Power transmitted by the output coupler [W].
    circulating_power : float
        Mean one-way intracavity power [W].
    threshold : float
        Incident pump threshold [W].
    above_threshold : bool
    small_signal_gain : float
        Logarithmic round-trip small-signal gain at this pump power.
    """

    output_power: float
    circulating_power: float
    threshold: float
    above_threshold: bool
    small_signal_gain: float


def _length_integrated_gain(material: GainMedium, absorbed_power: float,
                            w_l: float, w_p: float, circulating: float,
                            reabsorption: float) -> float:
    """Saturated logarithmic round-trip gain (see module docstring)."""
    sig_e = material.emission_cross_section
    sig_a = material.laser_absorption_cross_section
    tau = material.upper_state_lifetime
    hnu_l = material.laser_photon_energy
    rate = material.quantum_efficiency * absorbed_power / material.pump_photon_energy

    def integrand(r):
        s0 = 2 / (np.pi * w_l**2) * np.exp(-2 * r**2 / w_l**2)
        rp = 2 / (np.pi * w_p**2) * np.exp(-2 * r**2 / w_p**2)
        intensity = 2 * circulating * s0
        # length-integrated N2 per unit area; reabsorption = sig_a * N0 * l
        sat = 1 + (sig_e + sig_a) * tau * intensity / hnu_l
        n2l = (rate * rp * tau + reabsorption * tau * intensity / hnu_l) / sat
        local = 2 * ((sig_e + sig_a) * n2l - reabsorption)
        return local * s0 * 2 * np.pi * r

    r_max = 4 * max(w_l, w_p)
    val, _ = integrate.quad(integrand, 0, r_max, limit=200)
    return float(val)


def end_pumped_cw(material: GainMedium, pump_power: float, laser_radius: float,
                  pump_radius: float, output_coupling: float, passive_loss: float,
                  absorbed_fraction: float, crystal_length: float = 0.0,
                  doping: float = 0.0) -> CWResult:
    """CW output of an end-pumped laser from the spatially resolved model.

    Parameters
    ----------
    material : GainMedium
    pump_power : float
        Incident pump power [W].
    laser_radius, pump_radius : float
        TEM00 mode and pump 1/e^2 radii in the crystal [m].
    output_coupling : float
        Output coupler transmission ``T``.
    passive_loss : float
        Other round-trip fractional losses.
    absorbed_fraction : float
        Fraction of incident pump absorbed.
    crystal_length, doping : float
        Only needed for quasi-three-level media.

    Returns
    -------
    CWResult
    """
    delta = round_trip_loss(output_coupling, passive_loss)
    p_abs = pump_power * absorbed_fraction
    reabs = material.laser_absorption_cross_section * material.ion_density(doping) * crystal_length
    p_th = threshold_pump_power(material, laser_radius, pump_radius, delta,
                                absorbed_fraction, crystal_length, doping)

    def excess(p):
        return _length_integrated_gain(material, p_abs, laser_radius, pump_radius, p, reabs) - delta

    g0 = excess(0.0) + delta
    if g0 <= delta:
        return CWResult(0.0, 0.0, p_th, False, g0)
    hi = 1.0
    while excess(hi) > 0:
        hi *= 10
        if hi > 1e12:  # pragma: no cover
            raise RuntimeError("Could not bracket circulating power")
    p_circ = optimize.brentq(excess, 0.0, hi, xtol=1e-9 * hi, rtol=1e-10)
    # The model's extracted power is delta * P (log gain times mean circulating
    # power); the output coupler takes its share of it.
    p_out = p_circ * delta * output_fraction(output_coupling, delta)
    return CWResult(p_out, p_circ, p_th, True, g0)


# ---------------------------------------------------------------------- #
# Plane-wave (Rigrod) results, Siegman ch. 12
# ---------------------------------------------------------------------- #
def rigrod_output_intensity(small_signal_gain: float, output_coupling: float,
                            passive_loss: float, saturation_intensity: float) -> float:
    """Low-gain plane-wave output intensity of a standing-wave laser [W/m^2].

    ``I_out = (T I_sat / 2) (G0 / (T + L) - 1)``, where ``G0 = 2 g0 l`` is
    the round-trip small-signal gain (Siegman sec. 12.2, low-loss limit).
    """
    total = output_coupling + passive_loss
    if small_signal_gain <= total:
        return 0.0
    return float(output_coupling * saturation_intensity / 2 * (small_signal_gain / total - 1))


def optimum_output_coupling(small_signal_gain: float, passive_loss: float) -> float:
    """Output coupling maximising the Rigrod output, ``sqrt(G0 L) - L``."""
    if small_signal_gain <= passive_loss:
        return 0.0
    return float(np.sqrt(small_signal_gain * passive_loss) - passive_loss)
