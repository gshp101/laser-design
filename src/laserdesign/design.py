"""High-level laser models that tie the physics modules together.

:class:`EndPumpedLaser` is the object the GUI builds step by step: a gain
medium, a pump, a resonator (given as a function of the thermal focal length)
and the output coupling. :class:`SidePumpedRodLaser` is the same for a
uniformly side-pumped rod. For a given pump power they

1. computes absorbed power and heat load (:mod:`laserdesign.pump`),
2. computes the thermal lens (:mod:`laserdesign.thermal`),
3. rebuilds the resonator with that lens and finds its TEM00 mode
   (:mod:`laserdesign.abcd`),
4. evaluates threshold and CW output with the spatially resolved model
   (:mod:`laserdesign.gain`),
5. estimates M^2 (:mod:`laserdesign.beam_quality`), and
6. optionally evaluates actively or passively Q-switched or SESAM
   mode-locked operation (:mod:`laserdesign.qswitch`,
   :mod:`laserdesign.passive_qswitch`, :mod:`laserdesign.modelocking`).

The resonator may be a :class:`~laserdesign.abcd.StandingWaveCavity` or a
unidirectional :class:`~laserdesign.abcd.RingCavity`; the models detect which
and use one gain pass per round trip for a ring.

The thermal lens depends only on the pump, not on the laser mode, so no
self-consistent iteration is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import beam_quality, gain, modelocking, passive_qswitch, pump, qswitch, thermal
from .abcd import RingCavity, StandingWaveCavity
from .materials import GainMedium


def gain_passes(cavity) -> int:
    """Passes through the gain per round trip: 1 for a ring, 2 otherwise."""
    return 1 if isinstance(cavity, RingCavity) else 2


def spot_size_at_location(cavity, location: int | str, plane: str = "t") -> float:
    """Spot size at an end mirror (``1`` or ``2``) or a named element [m]."""
    if isinstance(location, str):
        return cavity.spot_size_at(location, plane)
    if not isinstance(cavity, StandingWaveCavity):
        raise ValueError("A ring cavity has no end mirrors; give the element name instead")
    return cavity.spot_size_on_mirror(location, plane)


@dataclass
class OperatingPoint:
    """Everything :meth:`EndPumpedLaser.analyze` computes at one pump power.

    All quantities in SI units. ``laser_radius`` and the CW, M^2 fields are
    ``nan`` when the resonator is unstable.

    ``laser_radius`` is the radius used in the gain model: the TEM00 radius
    ``tem00_radius`` of the resonator, or for a multimode side-pumped rod the
    radius of the top-hat beam (``laser_profile = "tophat"``).
    """

    pump_power: float
    absorbed_power: float
    heat_power: float
    thermal_focal_length: float
    stable: bool
    stability_parameter: float
    laser_radius: float
    pump_radius: float
    threshold: float
    output_power: float
    circulating_power: float
    slope_efficiency_ideal: float
    m2_aberration: float
    m2_multimode: float
    m2_estimate: float
    gain_passes: int = 2
    tem00_radius: float = float("nan")
    laser_profile: str = "gaussian"


class _LaserModel:
    """Analysis shared by the end- and side-pumped models.

    Subclasses provide ``absorbed_fraction``, ``pump_radius``,
    ``pump_profile``, :meth:`thermal_focal_length_from_absorbed`,
    :meth:`_gain_mode` and :meth:`_m2_contributions`.
    """

    pump_profile = "gaussian"

    @property
    def delta(self) -> float:
        """Logarithmic round-trip loss."""
        return gain.round_trip_loss(self.output_coupling, self.passive_loss)

    def thermal_focal_length(self, pump_power: float) -> float:
        """Thermal focal length used for the resonator at an incident pump power [m]."""
        return self.thermal_focal_length_from_absorbed(pump_power * self.absorbed_fraction)

    def resonator(self, pump_power: float):
        """The resonator including the thermal lens at this pump power."""
        return self.cavity(self.thermal_focal_length(pump_power))

    def _gain_mode(self, tem00_radius: float) -> tuple[float, str]:
        """Laser radius and profile used in the gain model."""
        return tem00_radius, "gaussian"

    def _profiles(self, op: "OperatingPoint") -> dict:
        return dict(gain_passes=op.gain_passes, laser_profile=op.laser_profile,
                    pump_profile=self.pump_profile)

    # ------------------------------------------------------------------ #
    def analyze(self, pump_power: float) -> OperatingPoint:
        """Evaluate CW operation at an incident pump power [W]."""
        mat = self.material
        eta = self.absorbed_fraction
        p_abs = pump_power * eta
        p_h = pump.heat_load(p_abs, mat.effective_heat_fraction)
        w_p = self.pump_radius
        f_th = self.thermal_focal_length_from_absorbed(p_abs)
        cav = self.cavity(f_th)
        m = cav.stability_parameter("t")
        passes = gain_passes(cav)
        nan = float("nan")
        if not cav.is_stable():
            return OperatingPoint(pump_power, p_abs, p_h, f_th, False, m, nan, w_p, nan,
                                  nan, nan, nan, nan, nan, nan, passes)
        w00 = cav.spot_size_at(self.crystal_element)
        w_l, profile = self._gain_mode(w00)
        cw = gain.end_pumped_cw(mat, pump_power, w_l, w_p, self.output_coupling,
                                self.passive_loss, eta, self.crystal_length, self.doping,
                                gain_passes=passes, laser_profile=profile,
                                pump_profile=self.pump_profile)
        slope = gain.slope_efficiency(mat, self.output_coupling, self.delta, eta)
        m2_ab, m2_mm = self._m2_contributions(w00, w_p, p_h)
        return OperatingPoint(
            pump_power=pump_power, absorbed_power=p_abs, heat_power=p_h,
            thermal_focal_length=f_th, stable=True, stability_parameter=m,
            laser_radius=w_l, pump_radius=w_p, threshold=cw.threshold,
            output_power=cw.output_power, circulating_power=cw.circulating_power,
            slope_efficiency_ideal=slope, m2_aberration=m2_ab, m2_multimode=m2_mm,
            m2_estimate=beam_quality.combine_m2(m2_ab, m2_mm), gain_passes=passes,
            tem00_radius=w00, laser_profile=profile,
        )

    def scan(self, pump_powers) -> list[OperatingPoint]:
        """:meth:`analyze` over an array of pump powers."""
        return [self.analyze(float(p)) for p in np.atleast_1d(pump_powers)]

    # ------------------------------------------------------------------ #
    def q_switched(self, pump_power: float, rep_rate: float) -> dict:
        """Actively Q-switched operation with CW pumping.

        Returns a dict with ``initial_ratio``, ``energy`` [J], ``peak_power``
        [W], ``pulse_width`` [s], ``average_power`` [W] and the CW operating
        point used for the mode size. Returns ``energy = 0`` if the inversion
        does not reach threshold between pulses.

        The inversion over threshold is taken as pump power over the CW
        threshold of the same cavity, and the effective area as the inverse
        pump-mode overlap (:func:`laserdesign.gain.effective_mode_area`;
        ``pi (w_l^2 + w_p^2) / 2`` for Gaussian beams), so that the stored
        energy matches the absorbed pump energy. Energy and peak power are then multiplied by
        :meth:`overlap_efficiency`, the fraction of the ideal output above
        threshold that the CW model achieves, so pump light outside the laser
        mode is not counted. This is an approximate, overlap-consistent extension of the
        plane-wave theory in :mod:`laserdesign.qswitch`.
        """
        op = self.analyze(pump_power)
        if not op.stable:
            raise ValueError("Resonator is unstable at this pump power")
        cav = self.resonator(pump_power)
        pump_ratio = pump_power / op.threshold
        r_i, _ = qswitch.repetitive_q_switch(pump_ratio, rep_rate, self.material.upper_state_lifetime)
        out = {"operating_point": op, "initial_ratio": r_i, "pump_ratio": pump_ratio}
        if r_i <= 1:
            out.update(energy=0.0, peak_power=0.0, pulse_width=float("nan"), average_power=0.0)
            return out
        sigma = self.material.emission_cross_section + self.material.laser_absorption_cross_section
        # The effective area 1 / overlap makes the stored inversion
        # (r * N_th * A * l) equal to the absorbed pump photons times the
        # lifetime, consistent with the overlap used for the CW threshold.
        area = self._gain_area(op)
        pulse = qswitch.q_switch_pulse(
            r_i, area, sigma,
            self.material.laser_photon_energy, self.delta,
            gain.output_coupling_loss(self.output_coupling), cav.round_trip_time,
            gain_passes=op.gain_passes)
        # Apply the transverse overlap efficiency found by the CW model, so
        # that pump light outside the mode is not counted as extractable.
        overlap = self.overlap_efficiency(pump_power)
        energy = pulse.energy * overlap
        out.update(energy=energy, peak_power=pulse.peak_power * overlap,
                   pulse_width=pulse.pulse_width, average_power=energy * rep_rate,
                   extraction_efficiency=pulse.extraction_efficiency,
                   overlap_efficiency=overlap)
        return out

    def overlap_efficiency(self, pump_power: float) -> float:
        """Actual CW output over the ideal output above threshold.

        ``P_out / (eta_s,ideal (P - P_th))``. A value of 1 means every absorbed
        pump photon above threshold reaches the TEM00 mode (pump much smaller
        than the mode); it falls as the pump grows larger than the mode. Using
        the average rather than the differential slope makes the Q-switched
        average power tend to the CW output at high repetition rates.
        """
        op = self.analyze(pump_power)
        if not op.stable:
            raise ValueError("Resonator is unstable at this pump power")
        ideal = op.slope_efficiency_ideal * (pump_power - op.threshold)
        if ideal <= 0:
            return 0.0
        return float(min(1.0, op.output_power / ideal))

    def _gain_area(self, op: OperatingPoint) -> float:
        return gain.effective_mode_area(op.laser_radius, op.pump_radius, op.laser_profile,
                                        self.pump_profile)

    def passively_q_switched(self, pump_power: float, initial_transmission: float,
                             absorber: passive_qswitch.SaturableAbsorber | str = "cr:yag",
                             absorber_location: int | str = 2) -> dict:
        """Passively Q-switched operation with CW pumping.

        Parameters
        ----------
        pump_power : float
            Incident pump power [W].
        initial_transmission : float
            Small-signal single-pass transmission ``T_0`` of the absorber.
        absorber : SaturableAbsorber or str
            The absorber, or the name of a predefined one.
        absorber_location : int or str
            Where the mode size in the absorber is read: an end mirror (1 or 2)
            of a standing-wave cavity, or an element name (e.g. a ``Medium``
            representing the Cr:YAG). The absorber is assumed thin.

        Returns
        -------
        dict
            ``pulse`` (:class:`~laserdesign.passive_qswitch.PassiveQSwitchPulse`),
            ``energy``, ``peak_power``, ``pulse_width``, ``rep_rate``,
            ``average_power``, ``threshold`` (CW threshold with the
            unbleached absorber), ``absorber_radius``, ``overlap_efficiency``,
            ``absorber_recovered`` (period longer than three recovery
            times) and the CW ``operating_point`` without the absorber.

        Notes
        -----
        Energy and peak power come from Degnan's theory with the same
        effective gain area and overlap efficiency as :meth:`q_switched`.
        The pulse energy does not depend on the pump power; the repetition
        rate does.
        """
        if isinstance(absorber, str):
            absorber = passive_qswitch.get_absorber(absorber)
        op = self.analyze(pump_power)
        if not op.stable:
            raise ValueError("Resonator is unstable at this pump power")
        cav = self.resonator(pump_power)
        mat = self.material
        w_s = spot_size_at_location(cav, absorber_location)
        # A multimode beam is wider by sqrt(M^2) and roughly flat-topped.
        area_s = (np.pi * w_s**2 / 2 if op.laser_profile == "gaussian"
                  else np.pi * w_s**2 * op.m2_multimode)
        area = self._gain_area(op)
        sigma = mat.emission_cross_section + mat.laser_absorption_cross_section
        pulse = passive_qswitch.passive_q_switch_pulse(
            absorber, initial_transmission, area, area_s, sigma, mat.laser_photon_energy,
            self.delta, gain.output_coupling_loss(self.output_coupling),
            cav.round_trip_time, gain_passes=op.gain_passes)
        p_th = gain.threshold_pump_power(
            mat, op.laser_radius, op.pump_radius, self.delta + pulse.l_gs,
            self.absorbed_fraction, self.crystal_length, self.doping, **self._profiles(op))
        overlap = self.overlap_efficiency(pump_power) if pulse.pulse_forms else 0.0
        f_rep = (passive_qswitch.passive_repetition_rate(pump_power / p_th, pulse.final_fraction,
                                                         mat.upper_state_lifetime)
                 if pulse.pulse_forms else 0.0)
        energy = pulse.energy * overlap
        return {
            "operating_point": op, "pulse": pulse, "energy": energy,
            "peak_power": pulse.peak_power * overlap, "pulse_width": pulse.pulse_width,
            "rep_rate": f_rep, "average_power": energy * f_rep, "threshold": p_th,
            "absorber_radius": w_s, "overlap_efficiency": overlap,
            "absorber_recovered": bool(f_rep == 0 or 1 / f_rep > 3 * absorber.recovery_time),
        }

    def sesam_mode_locked(self, pump_power: float, absorber_saturation_fluence: float,
                          modulation_depth: float, absorber_mirror: int | str = 2) -> dict:
        """Check SESAM mode locking.

        ``absorber_mirror`` is the end mirror (1 or 2) of a standing-wave
        cavity that is the SESAM, or for any cavity the name of the element
        (e.g. a flat :class:`~laserdesign.abcd.FlatMirror` in a ring) at which
        to read the mode size on the SESAM.

        Returns the CW operating point (average power) and a
        :class:`laserdesign.modelocking.SesamCheck`.
        """
        op = self.analyze(pump_power)
        if not op.stable:
            raise ValueError("Resonator is unstable at this pump power")
        cav = self.resonator(pump_power)
        w_a = spot_size_at_location(cav, absorber_mirror)
        check = modelocking.sesam_design_check(
            op.circulating_power, cav.optical_length, self.material.saturation_fluence,
            op.laser_radius, absorber_saturation_fluence, w_a, modulation_depth,
            self.material.gain_bandwidth, self.delta + modulation_depth,
            ring=isinstance(cav, RingCavity))
        return {"operating_point": op, "absorber_radius": w_a, "check": check}


@dataclass
class EndPumpedLaser(_LaserModel):
    """An end-pumped solid state laser.

    Parameters
    ----------
    material : GainMedium
    doping : float
        Doping in ``material.doping_unit``.
    crystal_length : float
        [m].
    pump_beam : PumpBeam
        Pump geometry; its ``power`` is overridden by the pump power passed
        to :meth:`analyze`.
    cavity : callable
        ``cavity(f_thermal) -> StandingWaveCavity or RingCavity``: builds the
        resonator for a given thermal focal length, normally using
        :func:`laserdesign.abcd.crystal_with_thermal_lens`.
    crystal_element : str
        Name of the element at which to read the laser mode radius in the
        crystal (usually the thermal lens, ``"<crystal> thermal lens"``).
    output_coupling : float
        Output coupler transmission.
    passive_loss : float
        Other round-trip losses (fraction).
    pump_passes : int
        1 or 2 (double-pass pumping).
    effective_absorption : float or None
        Override the small-signal pump absorption coefficient [1/m], e.g. to
        account for a broad diode spectrum. ``None`` uses the material value.
    """

    material: GainMedium
    doping: float
    crystal_length: float
    pump_beam: pump.PumpBeam
    cavity: Callable[[float], StandingWaveCavity | RingCavity]
    crystal_element: str
    output_coupling: float
    passive_loss: float = 0.01
    pump_passes: int = 1
    effective_absorption: float | None = None

    # ------------------------------------------------------------------ #
    @property
    def absorption_coefficient(self) -> float:
        """Pump absorption coefficient used by the model [1/m]."""
        if self.effective_absorption is not None:
            return self.effective_absorption
        return self.material.pump_absorption_coefficient(self.doping)

    @property
    def absorbed_fraction(self) -> float:
        """Fraction of incident pump absorbed."""
        return pump.absorbed_fraction(self.absorption_coefficient, self.crystal_length,
                                      passes=self.pump_passes)

    @property
    def pump_radius(self) -> float:
        """Absorption-weighted pump radius in the crystal [m]."""
        return self.pump_beam.effective_radius(self.absorption_coefficient, self.crystal_length,
                                               n=self.material.refractive_index)

    def thermal_focal_length_from_absorbed(self, absorbed_power: float) -> float:
        """Thermal focal length for an absorbed pump power [m]."""
        return thermal.thermal_lens(self.material, absorbed_power, self.pump_radius)

    def _m2_contributions(self, w00: float, w_p: float, p_h: float) -> tuple[float, float]:
        mat = self.material
        m2_ab = (beam_quality.m2_thermal_aberration(w00, w_p, p_h, mat.thermal_conductivity,
                                                    mat.dn_dT, mat.laser_wavelength)
                 if p_h > 0 else 1.0)
        return m2_ab, beam_quality.m2_from_mode_size_ratio(w_p, w00)


@dataclass
class SidePumpedRodLaser(_LaserModel):
    """A uniformly side-pumped, barrel-cooled laser rod.

    The pump is absorbed uniformly over the rod cross section (a top-hat
    pump profile of radius ``rod_radius``), which is a good description of
    diode side-pumping with three or more pump directions and of lamp
    pumping. The thermal lens follows Koechner eq. 7.41, including stress
    bifocusing.

    Parameters
    ----------
    material : GainMedium
    doping : float
        Doping in ``material.doping_unit`` (only used for reabsorption in
        quasi-three-level media).
    rod_radius, rod_length : float
        [m].
    cavity : callable
        ``cavity(f_thermal) -> StandingWaveCavity or RingCavity``.
    crystal_element : str
        Element at which the mode radius in the rod is read.
    output_coupling : float
    passive_loss : float
        Other round-trip losses (fraction).
    absorption_efficiency : float
        Fraction of the pump power (diode or lamp output) absorbed in the
        rod, Koechner's transfer times absorption efficiency
        ``eta_t eta_a``; typically 0.5 to 0.8 for diode side pumping.
    thermal_lens : {"average", "radial", "tangential", "dn_dT"}
        Which focal length to put in the resonator. ``"average"`` uses the
        mean optical power of the radially and tangentially polarised lenses,
        appropriate for an unpolarised laser; use ``"radial"`` or
        ``"tangential"`` to check the two extremes, or ``"dn_dT"`` to ignore
        stress and end-face bulging.
    photoelastic_radial, photoelastic_tangential : float
        Photo-elastic coefficients ``C_r`` and ``C_phi`` (Koechner eq. 7.20;
        defaults are the Nd:YAG [111] values 0.017 and -0.0025).
    multimode_fill : float or None
        ``None`` assumes TEM00 operation (in practice this needs an aperture).
        A number ``0 < fill <= 1`` models a multimode beam filling a radius
        ``fill * rod_radius`` with a flat top; its M^2 is then
        ``(fill * rod_radius / w_00)^2``.
    """

    material: GainMedium
    doping: float
    rod_radius: float
    rod_length: float
    cavity: Callable[[float], StandingWaveCavity | RingCavity]
    crystal_element: str
    output_coupling: float
    passive_loss: float = 0.02
    absorption_efficiency: float = 0.7
    thermal_lens: str = "average"
    photoelastic_radial: float = 0.017
    photoelastic_tangential: float = -0.0025
    multimode_fill: float | None = None

    pump_profile = "tophat"

    def __post_init__(self):
        if self.thermal_lens not in ("average", "radial", "tangential", "dn_dT"):
            raise ValueError("thermal_lens must be 'average', 'radial', 'tangential' or 'dn_dT'")
        if self.multimode_fill is not None and not 0 < self.multimode_fill <= 1:
            raise ValueError("multimode_fill must be in (0, 1]")

    @property
    def crystal_length(self) -> float:
        """The rod length [m] (same role as an end-pumped crystal length)."""
        return self.rod_length

    @property
    def absorbed_fraction(self) -> float:
        return self.absorption_efficiency

    @property
    def pump_radius(self) -> float:
        """Radius of the uniformly pumped region, the rod radius [m]."""
        return self.rod_radius

    def thermal_focal_lengths(self, absorbed_power: float) -> dict:
        """Radial, tangential and dn/dT-only focal lengths [m] (Koechner eq. 7.41)."""
        mat = self.material
        p_h = pump.heat_load(absorbed_power, mat.effective_heat_fraction)
        common = dict(heat_power=p_h, rod_radius=self.rod_radius, length=self.rod_length,
                      thermal_conductivity=mat.thermal_conductivity, dn_dT=mat.dn_dT,
                      refractive_index=mat.refractive_index)
        out = {"dn_dT": thermal.side_pumped_rod_focal_length(**common)}
        for key, c in (("radial", self.photoelastic_radial),
                       ("tangential", self.photoelastic_tangential)):
            out[key] = thermal.side_pumped_rod_focal_length(
                thermal_expansion=mat.thermal_expansion, photoelastic_coefficient=c, **common)
        inv = [1 / out[k] if np.isfinite(out[k]) else 0.0 for k in ("radial", "tangential")]
        out["average"] = 2 / sum(inv) if sum(inv) != 0 else np.inf
        return out

    def thermal_focal_length_from_absorbed(self, absorbed_power: float) -> float:
        return self.thermal_focal_lengths(absorbed_power)[self.thermal_lens]

    def _gain_mode(self, tem00_radius: float) -> tuple[float, str]:
        if self.multimode_fill is None:
            return tem00_radius, "gaussian"
        return self.multimode_fill * self.rod_radius, "tophat"

    def _m2_contributions(self, w00: float, w_p: float, p_h: float) -> tuple[float, float]:
        # A uniformly pumped rod has a parabolic temperature profile: no
        # spherical aberration to first order.
        if self.multimode_fill is None:
            return 1.0, 1.0
        return 1.0, beam_quality.m2_from_mode_size_ratio(self.multimode_fill * self.rod_radius,
                                                         w00)

    def stress_fracture_pump(self) -> float:
        """Absorbed pump power at the fracture limit (no safety factor) [W].

        Uses Koechner eq. 7.25; ``nan`` if the material has no thermal shock
        parameter.
        """
        r_t = self.material.thermal_shock_parameter
        if r_t is None:
            return float("nan")
        p_h = thermal.fracture_limit_per_length(r_t) * self.rod_length
        return float(p_h / self.material.effective_heat_fraction)
