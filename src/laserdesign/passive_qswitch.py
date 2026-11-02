"""Passive Q-switching with a saturable absorber (e.g. Cr:YAG).

Rate equations
--------------
With ``Phi`` the intracavity photon number, ``N`` the gain inversion density
and ``g`` the fraction of absorber ions in the ground state, a cavity of
round-trip time ``t_rt`` obeys (Degnan, IEEE JQE 31, 1890 (1995); Siegman,
*Lasers*, sec. 26.4)

.. math::

    \\frac{d\\Phi}{dt} = \\frac{\\Phi}{t_{rt}}\\left[p\\sigma N l - \\delta
        - L_{es} - (L_{gs} - L_{es})\\,g\\right], \\qquad
    \\frac{dN}{dt} = -\\frac{\\gamma p \\sigma}{A t_{rt}} N \\Phi, \\qquad
    \\frac{dg}{dt} = -\\frac{p_s \\sigma_{gs}}{A_s t_{rt}} g \\Phi,

where ``p`` and ``p_s`` are the passes per round trip through gain and
absorber (2 in a standing-wave cavity, 1 in a ring), ``A`` and ``A_s`` the
effective mode areas in gain and absorber, ``delta`` all other logarithmic
round-trip losses and

.. math::

    L_{gs} = p_s \\ln\\frac{1}{T_0}, \\qquad
    L_{es} = \\frac{\\sigma_{es}}{\\sigma_{gs}} L_{gs}

the unbleached and fully bleached absorber losses for a small-signal
single-pass transmission ``T_0``. Pumping, spontaneous decay and absorber
recovery are neglected during the pulse.

Dividing the third equation by the second gives ``g = x^alpha`` with
``x = N / N_i`` and

.. math:: \\alpha = \\frac{p_s \\sigma_{gs} A}{\\gamma p \\sigma A_s},

the ratio of absorber to gain saturation. Lasing starts when the gain reaches
the unbleached loss, ``p sigma N_i l = delta + L_gs``. Integrating
``dPhi/dx`` then gives

.. math::

    \\Phi(x) = \\frac{A}{\\gamma p \\sigma}\\left[(\\delta + L_{gs})(1 - x)
        - (\\delta + L_{es}) \\ln\\frac{1}{x}
        - (L_{gs} - L_{es})\\frac{1 - x^{\\alpha}}{\\alpha}\\right].

The final inversion ``x_f`` solves ``Phi(x_f) = 0``, the photon number peaks
at ``x_p`` where ``(delta + L_gs) x_p = delta + L_es + (L_gs - L_es) x_p^alpha``,
and

.. math::

    E = \\frac{h\\nu A}{\\gamma p \\sigma}\\,\\delta_{oc}\\ln\\frac{1}{x_f},
    \\qquad P_{pk} = \\frac{h\\nu\\,\\delta_{oc}}{t_{rt}}\\,\\Phi(x_p).

A clean giant pulse needs the absorber to bleach faster than the gain
saturates. Expanding ``Phi`` about ``x = 1`` gives the condition

.. math:: \\alpha\\,(L_{gs} - L_{es}) > \\delta + L_{gs},

reported as :attr:`PassiveQSwitchPulse.bleaching_criterion` (must exceed 1;
Degnan recommends a comfortable margin). Below it the absorber only adds
loss and the laser tends to run CW or in weak, irregular spikes.

Repetition rate
---------------
With CW pumping the inversion recovers from ``N_f`` towards its unsaturated
value ``N_inf`` with the upper-state lifetime and the next pulse fires when it
reaches ``N_i`` again. Writing ``r = N_inf / N_i`` as the pump power over the
CW threshold of the cavity *with the unbleached absorber*,

.. math:: T_{rep} = \\tau \\ln\\frac{r - x_f}{r - 1},

assuming the absorber recovers fully between pulses (Cr:YAG recovers in
about 4 us). Unlike active Q-switching, the pulse energy is fixed by
``T_0`` and the cavity and the pump power only sets the repetition rate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize

from .units import cm2, nm, us


@dataclass(frozen=True)
class SaturableAbsorber:
    """Parameters of a slow saturable absorber used as a passive Q-switch.

    Parameters
    ----------
    name : str
    ground_state_cross_section : float
        Ground-state absorption cross section ``sigma_gs`` [m^2].
    excited_state_cross_section : float
        Excited-state absorption cross section ``sigma_es`` [m^2]; it sets
        the residual loss of the bleached absorber.
    recovery_time : float
        Excited-state lifetime [s].
    wavelength : float
        Wavelength the cross sections refer to [m].
    notes : str
    """

    name: str
    ground_state_cross_section: float
    excited_state_cross_section: float
    recovery_time: float
    wavelength: float
    notes: str = ""

    @property
    def saturation_fluence(self) -> float:
        """Ground-state saturation fluence ``h nu / sigma_gs`` [J/m^2]."""
        from .units import photon_energy
        return photon_energy(self.wavelength) / self.ground_state_cross_section

    def losses(self, initial_transmission: float, passes: int = 2) -> tuple[float, float]:
        """Unbleached and bleached logarithmic round-trip losses ``(L_gs, L_es)``.

        Parameters
        ----------
        initial_transmission : float
            Small-signal single-pass transmission ``T_0`` (0 to 1).
        passes : int
            Passes through the absorber per round trip.
        """
        if not 0 < initial_transmission <= 1:
            raise ValueError("initial_transmission must be in (0, 1]")
        l_gs = passes * np.log(1 / initial_transmission)
        l_es = l_gs * self.excited_state_cross_section / self.ground_state_cross_section
        return float(l_gs), float(l_es)


#: Cr4+:YAG at 1064 nm (Burshtein et al., IEEE JQE 34, 292 (1998); Degnan 1995).
CR_YAG = SaturableAbsorber(
    name="Cr4+:YAG",
    ground_state_cross_section=8.7e-19 * cm2,
    excited_state_cross_section=2.2e-19 * cm2,
    recovery_time=3.4 * us,
    wavelength=1064 * nm,
    notes=("Values at 1064 nm. Published sigma_gs ranges from about 4e-19 to "
           "8.7e-19 cm^2 and sigma_es from 0.8e-19 to 2.2e-19 cm^2; the ratio "
           "matters most for the residual loss."),
)

#: Predefined saturable absorbers keyed by a short lower-case id.
ABSORBERS: dict[str, SaturableAbsorber] = {"cr:yag": CR_YAG}


def get_absorber(name: str) -> SaturableAbsorber:
    """Look up a predefined saturable absorber by name (case-insensitive)."""
    key = name.strip().lower()
    if key not in ABSORBERS:
        raise KeyError(f"Unknown absorber {name!r}; known: {sorted(ABSORBERS)}")
    return ABSORBERS[key]


def saturation_ratio(absorber: SaturableAbsorber, gain_cross_section: float,
                     gain_area: float, absorber_area: float, gamma: float = 1.0,
                     gain_passes: int = 2, absorber_passes: int = 2) -> float:
    """``alpha = p_s sigma_gs A / (gamma p sigma A_s)``, see the module docstring."""
    return float(absorber_passes * absorber.ground_state_cross_section * gain_area
                 / (gamma * gain_passes * gain_cross_section * absorber_area))


def _photon_function(x, delta, l_gs, l_es, alpha):
    """Bracket in Phi(x) (Phi divided by A / (gamma p sigma))."""
    x = np.asarray(x, dtype=float)
    return ((delta + l_gs) * (1 - x) - (delta + l_es) * np.log(1 / x)
            - (l_gs - l_es) * (1 - x**alpha) / alpha)


@dataclass
class PassiveQSwitchPulse:
    """Result of :func:`passive_q_switch_pulse`.

    Attributes
    ----------
    energy : float
        Output pulse energy [J].
    peak_power : float
        Output peak power [W].
    pulse_width : float
        ``energy / peak_power`` [s].
    final_fraction : float
        ``x_f = N_f / N_i``.
    peak_fraction : float
        ``x_p``, inversion at the photon peak over ``N_i``.
    extraction_efficiency : float
        ``1 - x_f``.
    alpha : float
        Absorber-to-gain saturation ratio.
    bleaching_criterion : float
        ``alpha (L_gs - L_es) / (delta + L_gs)``; a pulse forms only above 1.
    initial_gain : float
        Round-trip gain at the start of the pulse, ``delta + L_gs``.
    l_gs, l_es : float
        Unbleached and bleached absorber round-trip losses.
    pulse_forms : bool
    """

    energy: float
    peak_power: float
    pulse_width: float
    final_fraction: float
    peak_fraction: float
    extraction_efficiency: float
    alpha: float
    bleaching_criterion: float
    initial_gain: float
    l_gs: float
    l_es: float
    pulse_forms: bool


def passive_q_switch_pulse(absorber: SaturableAbsorber, initial_transmission: float,
                           gain_area: float, absorber_area: float,
                           gain_cross_section: float, photon_energy: float,
                           delta: float, delta_oc: float, round_trip_time: float,
                           gamma: float = 1.0, gain_passes: int = 2,
                           absorber_passes: int | None = None) -> PassiveQSwitchPulse:
    """Analytic (Degnan) energy, peak power and width of a passively Q-switched pulse.

    Parameters
    ----------
    absorber : SaturableAbsorber
    initial_transmission : float
        Small-signal single-pass absorber transmission ``T_0``.
    gain_area, absorber_area : float
        Effective mode areas ``A`` in the gain medium and ``A_s`` in the
        absorber [m^2] (``pi w^2 / 2`` for a TEM00 mode of radius ``w``).
    gain_cross_section : float
        ``sigma`` of the gain medium [m^2] (``sigma_e + sigma_a`` for
        quasi-three-level media).
    photon_energy : float
        Laser photon energy [J].
    delta : float
        Logarithmic round-trip loss *excluding* the absorber.
    delta_oc : float
        Output-coupler part of ``delta``.
    round_trip_time : float
        [s].
    gamma : float
        Inversion reduction factor of the gain medium.
    gain_passes, absorber_passes : int
        Passes per round trip; ``absorber_passes`` defaults to ``gain_passes``.
    """
    p_s = gain_passes if absorber_passes is None else absorber_passes
    l_gs, l_es = absorber.losses(initial_transmission, p_s)
    alpha = saturation_ratio(absorber, gain_cross_section, gain_area, absorber_area, gamma,
                             gain_passes, p_s)
    g_i = delta + l_gs
    crit = alpha * (l_gs - l_es) / g_i if l_gs > l_es else 0.0
    pref = gain_area / (gamma * gain_passes * gain_cross_section)
    nan = float("nan")
    if crit <= 1:
        return PassiveQSwitchPulse(0.0, 0.0, nan, 1.0, 1.0, 0.0, alpha, crit, g_i, l_gs, l_es,
                                   False)

    # Peak: h(x) = (delta + L_es) + (L_gs - L_es) x^alpha - g_i x = 0, other than x = 1.
    def h(x):
        return delta + l_es + (l_gs - l_es) * x**alpha - g_i * x

    # h > 0 at x -> 0 and h < 0 just below 1 (because crit > 1): find the sign change.
    xs = np.concatenate([np.geomspace(1e-12, 0.5, 400), np.linspace(0.5, 1 - 1e-9, 4000)])
    hv = h(xs)
    neg = np.where(hv < 0)[0]
    j = int(neg[0])
    x_p = optimize.brentq(h, xs[j - 1], xs[j], xtol=1e-15) if j > 0 else xs[0]

    def f(x):
        return _photon_function(x, delta, l_gs, l_es, alpha)

    x_f = optimize.brentq(f, 1e-300, x_p, xtol=1e-15, rtol=1e-13)
    phi_peak = pref * float(f(x_p))
    energy = photon_energy * delta_oc * pref * np.log(1 / x_f)
    peak = photon_energy * delta_oc * phi_peak / round_trip_time
    return PassiveQSwitchPulse(
        energy=float(energy), peak_power=float(peak), pulse_width=float(energy / peak),
        final_fraction=float(x_f), peak_fraction=float(x_p),
        extraction_efficiency=float(1 - x_f), alpha=alpha, bleaching_criterion=float(crit),
        initial_gain=float(g_i), l_gs=l_gs, l_es=l_es, pulse_forms=True)


def passive_repetition_rate(pump_ratio: float, final_fraction: float, lifetime: float) -> float:
    """Pulse repetition rate with CW pumping [Hz].

    Parameters
    ----------
    pump_ratio : float
        ``r = N_inf / N_i``: pump power over the CW threshold of the cavity
        with the *unbleached* absorber. No pulses form for ``r <= 1``.
    final_fraction : float
        ``x_f`` from :func:`passive_q_switch_pulse`.
    lifetime : float
        Upper-state lifetime [s].
    """
    if pump_ratio <= 1:
        return 0.0
    return float(1 / (lifetime * np.log((pump_ratio - final_fraction) / (pump_ratio - 1))))


@dataclass
class PassiveQSwitchSimulation:
    """Result of :func:`simulate_passive_q_switch`.

    Attributes
    ----------
    t : ndarray
        Time [s], with zero at the start of the integration.
    output_power : ndarray
        [W].
    inversion_ratio : ndarray
        ``N / N_i``.
    ground_state_fraction : ndarray
        Absorber ground-state fraction ``g``.
    energy, peak_power, fwhm : float
        [J], [W], [s].
    final_fraction : float
        Inversion after the pulse over ``N_i``.
    """

    t: np.ndarray
    output_power: np.ndarray
    inversion_ratio: np.ndarray
    ground_state_fraction: np.ndarray
    energy: float
    peak_power: float
    fwhm: float
    final_fraction: float


def simulate_passive_q_switch(absorber: SaturableAbsorber, initial_transmission: float,
                              gain_area: float, absorber_area: float,
                              gain_cross_section: float, photon_energy: float,
                              delta: float, delta_oc: float, round_trip_time: float,
                              gamma: float = 1.0, gain_passes: int = 2,
                              absorber_passes: int | None = None,
                              initial_excess: float = 1e-4, initial_photons: float = 1.0,
                              n_points: int = 4000) -> PassiveQSwitchSimulation:
    """Integrate the passive Q-switch rate equations numerically.

    Uses the same equations as the analytic theory (module docstring), in
    terms of ``ln Phi``, ``n = N / N_i`` and ``g``. The gain starts a fraction
    ``initial_excess`` above the unbleached threshold, standing in for the
    slow pump-driven crossing of threshold; the pulse shape and energy depend
    only weakly on it, but the time from the start to the pulse does, so no
    build-up time is reported.
    """
    p_s = gain_passes if absorber_passes is None else absorber_passes
    l_gs, l_es = absorber.losses(initial_transmission, p_s)
    g_i = delta + l_gs
    k_n = gamma * gain_passes * gain_cross_section / (gain_area * round_trip_time)
    k_g = p_s * absorber.ground_state_cross_section / (absorber_area * round_trip_time)

    def rhs(_t, y):
        ln_phi, n, g = y
        phi = np.exp(ln_phi)
        net = g_i * n - delta - l_es - (l_gs - l_es) * g
        return [net / round_trip_time, -k_n * n * phi, -k_g * g * phi]

    # Event: the inversion has fallen well below threshold (pulse over).
    ana = passive_q_switch_pulse(absorber, initial_transmission, gain_area, absorber_area,
                                 gain_cross_section, photon_energy, delta, delta_oc,
                                 round_trip_time, gamma, gain_passes, p_s)
    if not ana.pulse_forms:
        raise ValueError("Bleaching criterion not met: no giant pulse forms")
    n_peak = ana.peak_fraction

    def past_peak(_t, y):
        return y[1] - n_peak

    past_peak.terminal = True
    past_peak.direction = -1
    y0 = [np.log(initial_photons), 1 + initial_excess, 1.0]
    t_guess = 60 * round_trip_time / (g_i * initial_excess)
    sol1 = integrate.solve_ivp(rhs, (0, 10 * t_guess), y0, method="LSODA", rtol=1e-10,
                               atol=[1e-9, 1e-13, 1e-13], events=past_peak,
                               dense_output=True)
    t_pk = sol1.t[-1]
    tail = 40 * max(ana.pulse_width, round_trip_time)
    sol2 = integrate.solve_ivp(rhs, (t_pk, t_pk + tail), sol1.y[:, -1], method="LSODA",
                               rtol=1e-10, atol=[1e-9, 1e-13, 1e-13], dense_output=True)

    def sample(t):
        out = np.empty((3, len(t)))
        m = t <= t_pk
        out[:, m] = sol1.sol(t[m])
        out[:, ~m] = sol2.sol(t[~m])
        return out

    t = np.linspace(max(0.0, t_pk - tail), t_pk + tail, n_points)
    ln_phi, n, g = sample(t)
    power = np.exp(ln_phi) * photon_energy * delta_oc / round_trip_time
    i_pk = int(np.argmax(power))
    above = np.where(power > power[i_pk] * 1e-4)[0]
    t = np.linspace(t[max(above[0] - 1, 0)], t[min(above[-1] + 1, len(t) - 1)], n_points)
    ln_phi, n, g = sample(t)
    power = np.exp(ln_phi) * photon_energy * delta_oc / round_trip_time
    i_pk = int(np.argmax(power))
    half = np.where(power >= power[i_pk] / 2)[0]
    return PassiveQSwitchSimulation(
        t=t, output_power=power, inversion_ratio=n, ground_state_fraction=g,
        energy=float(integrate.trapezoid(power, t)), peak_power=float(power[i_pk]),
        fwhm=float(t[half[-1]] - t[half[0]]), final_fraction=float(n[-1]))
