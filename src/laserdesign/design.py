"""High-level end-pumped laser model that ties the physics modules together.

:class:`EndPumpedLaser` is the object the GUI builds step by step: a gain
medium, a pump, a resonator (given as a function of the thermal focal length)
and the output coupling. For a given pump power it

1. computes absorbed power and heat load (:mod:`laserdesign.pump`),
2. computes the thermal lens (:mod:`laserdesign.thermal`),
3. rebuilds the resonator with that lens and finds its TEM00 mode
   (:mod:`laserdesign.abcd`),
4. evaluates threshold and CW output with the spatially resolved model
   (:mod:`laserdesign.gain`),
5. estimates M^2 (:mod:`laserdesign.beam_quality`), and
6. optionally evaluates Q-switched or SESAM mode-locked operation
   (:mod:`laserdesign.qswitch`, :mod:`laserdesign.modelocking`).

The thermal lens depends only on the pump, not on the laser mode, so no
self-consistent iteration is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import beam_quality, gain, modelocking, pump, qswitch, thermal
from .abcd import StandingWaveCavity
from .materials import GainMedium


@dataclass
class OperatingPoint:
    """Everything :meth:`EndPumpedLaser.analyze` computes at one pump power.

    All quantities in SI units. ``laser_radius`` and the CW, M^2 fields are
    ``nan`` when the resonator is unstable.
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


@dataclass
class EndPumpedLaser:
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
        ``cavity(f_thermal) -> StandingWaveCavity``: builds the resonator for a
        given thermal focal length, normally using
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
    cavity: Callable[[float], StandingWaveCavity]
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

    @property
    def delta(self) -> float:
        """Logarithmic round-trip loss."""
        return gain.round_trip_loss(self.output_coupling, self.passive_loss)

    def thermal_focal_length(self, pump_power: float) -> float:
        """Thermal focal length at an incident pump power [m]."""
        p_abs = pump_power * self.absorbed_fraction
        return thermal.thermal_lens(self.material, p_abs, self.pump_radius)

    def resonator(self, pump_power: float) -> StandingWaveCavity:
        """The resonator including the thermal lens at this pump power."""
        return self.cavity(self.thermal_focal_length(pump_power))

    # ------------------------------------------------------------------ #
    def analyze(self, pump_power: float) -> OperatingPoint:
        """Evaluate CW operation at an incident pump power [W]."""
        mat = self.material
        eta = self.absorbed_fraction
        p_abs = pump_power * eta
        p_h = pump.heat_load(p_abs, mat.effective_heat_fraction)
        w_p = self.pump_radius
        f_th = thermal.thermal_lens(mat, p_abs, w_p)
        cav = self.cavity(f_th)
        m = cav.stability_parameter("t")
        stable = cav.is_stable()
        nan = float("nan")
        if not stable:
            return OperatingPoint(pump_power, p_abs, p_h, f_th, False, m, nan, w_p, nan,
                                  nan, nan, nan, nan, nan, nan)
        w_l = cav.spot_size_at(self.crystal_element)
        cw = gain.end_pumped_cw(mat, pump_power, w_l, w_p, self.output_coupling,
                                self.passive_loss, eta, self.crystal_length, self.doping)
        slope = gain.slope_efficiency(mat, self.output_coupling, self.delta, eta)
        m2_ab = beam_quality.m2_thermal_aberration(w_l, w_p, p_h, mat.thermal_conductivity,
                                                   mat.dn_dT, mat.laser_wavelength) if p_h > 0 else 1.0
        m2_mm = beam_quality.m2_from_mode_size_ratio(w_p, w_l)
        return OperatingPoint(
            pump_power=pump_power, absorbed_power=p_abs, heat_power=p_h,
            thermal_focal_length=f_th, stable=True, stability_parameter=m,
            laser_radius=w_l, pump_radius=w_p, threshold=cw.threshold,
            output_power=cw.output_power, circulating_power=cw.circulating_power,
            slope_efficiency_ideal=slope, m2_aberration=m2_ab, m2_multimode=m2_mm,
            m2_estimate=beam_quality.combine_m2(m2_ab, m2_mm),
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
        threshold of the same cavity, and the effective area as
        ``pi (w_l^2 + w_p^2) / 2``, so that the stored energy matches the
        absorbed pump energy. Energy and peak power are then multiplied by
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
        # Effective area pi (w_l^2 + w_p^2) / 2 makes the stored inversion
        # (r * N_th * A * l) equal to the absorbed pump photons times the
        # lifetime, consistent with the overlap used for the CW threshold.
        area = np.pi * (op.laser_radius**2 + op.pump_radius**2) / 2
        pulse = qswitch.q_switch_pulse(
            r_i, area, sigma,
            self.material.laser_photon_energy, self.delta,
            gain.output_coupling_loss(self.output_coupling), cav.round_trip_time)
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

    def sesam_mode_locked(self, pump_power: float, absorber_saturation_fluence: float,
                          modulation_depth: float, absorber_mirror: int = 2) -> dict:
        """Check SESAM mode locking with the SESAM as an end mirror.

        Returns the CW operating point (average power) and a
        :class:`laserdesign.modelocking.SesamCheck`.
        """
        op = self.analyze(pump_power)
        if not op.stable:
            raise ValueError("Resonator is unstable at this pump power")
        cav = self.resonator(pump_power)
        w_a = cav.spot_size_on_mirror(absorber_mirror)
        check = modelocking.sesam_design_check(
            op.circulating_power, cav.optical_length, self.material.saturation_fluence,
            op.laser_radius, absorber_saturation_fluence, w_a, modulation_depth,
            self.material.gain_bandwidth, self.delta + modulation_depth)
        return {"operating_point": op, "absorber_radius": w_a, "check": check}
