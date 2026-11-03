"""Ring resonators, passive Q-switching, Kerr-lens mode locking and side pumping."""

import numpy as np
import pytest
from scipy import integrate

from laserdesign import abcd, design, gain, kerr, passive_qswitch as pq, pump, qswitch
from laserdesign.materials import ND_YAG, ND_YVO4, TI_SAPPHIRE
from laserdesign.units import c, photon_energy


# ---------------------------------------------------------------------- #
# Overlap and gain passes
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("lp", gain.PROFILES)
@pytest.mark.parametrize("pp", gain.PROFILES)
@pytest.mark.parametrize("wl, wp", [(100e-6, 150e-6), (300e-6, 120e-6)])
def test_mode_overlap_matches_numeric_integral(lp, pp, wl, wp):
    def f(r):
        return (gain.normalized_profile(r, wl, lp) * gain.normalized_profile(r, wp, pp)
                * 2 * np.pi * r)

    pts = [w for w in (wl, wp)]
    num, _ = integrate.quad(f, 0, 5 * max(wl, wp), points=pts, limit=200)
    assert gain.mode_overlap(wl, wp, lp, pp) == pytest.approx(num, rel=1e-6)


def test_profiles_are_normalised():
    for prof in gain.PROFILES:
        val, _ = integrate.quad(lambda r: gain.normalized_profile(r, 1e-3, prof) * 2 * np.pi * r,
                                0, 5e-3, points=[1e-3])
        assert val == pytest.approx(1, rel=1e-6)


def test_ring_threshold_is_twice_standing_wave():
    d = gain.round_trip_loss(0.1, 0.01)
    sw = gain.threshold_pump_power(ND_YVO4, 200e-6, 150e-6, d, 0.9)
    ring = gain.threshold_pump_power(ND_YVO4, 200e-6, 150e-6, d, 0.9, gain_passes=1)
    assert ring == pytest.approx(2 * sw)


@pytest.mark.parametrize("passes", [1, 2])
@pytest.mark.parametrize("pp", gain.PROFILES)
def test_cw_model_threshold_matches_formula(passes, pp):
    kw = dict(laser_radius=200e-6, pump_radius=300e-6, output_coupling=0.1, passive_loss=0.01,
              absorbed_fraction=0.9, gain_passes=passes, pump_profile=pp)
    th = gain.threshold_pump_power(ND_YVO4, 200e-6, 300e-6, gain.round_trip_loss(0.1, 0.01),
                                   0.9, gain_passes=passes, pump_profile=pp)
    assert not gain.end_pumped_cw(ND_YVO4, 0.99 * th, **kw).above_threshold
    assert gain.end_pumped_cw(ND_YVO4, 1.01 * th, **kw).above_threshold


def test_ring_slope_matches_ideal_for_small_pump():
    """Far above threshold with pump << mode, the ring slope is the ideal one too."""
    kw = dict(laser_radius=400e-6, pump_radius=50e-6, output_coupling=0.1, passive_loss=0.0,
              absorbed_fraction=1.0)
    for passes in (1, 2):
        a = gain.end_pumped_cw(ND_YVO4, 40.0, gain_passes=passes, **kw).output_power
        b = gain.end_pumped_cw(ND_YVO4, 41.0, gain_passes=passes, **kw).output_power
        ideal = gain.slope_efficiency(ND_YVO4, 0.1, gain.round_trip_loss(0.1), 1.0)
        assert (b - a) == pytest.approx(ideal, rel=0.03)


def test_tophat_multimode_slope_scales_with_fill():
    """A flat-top beam of radius b < a in a flat-top pump extracts (b/a)^2."""
    a, b = 2e-3, 1.4e-3
    kw = dict(laser_radius=b, pump_radius=a, output_coupling=0.2, passive_loss=0.0,
              absorbed_fraction=1.0, laser_profile="tophat", pump_profile="tophat")
    p1 = gain.end_pumped_cw(ND_YAG, 2000.0, **kw).output_power
    p2 = gain.end_pumped_cw(ND_YAG, 2100.0, **kw).output_power
    ideal = gain.slope_efficiency(ND_YAG, 0.2, gain.round_trip_loss(0.2), 1.0)
    assert (p2 - p1) / 100 == pytest.approx(ideal * (b / a) ** 2, rel=0.03)


QS = dict(mode_area=np.pi * (200e-6) ** 2 / 2, emission_cross_section=2.8e-23,
          photon_energy=photon_energy(1064e-9), delta=0.25, delta_oc=0.22,
          round_trip_time=1e-9)


def test_ring_q_switch_energy_doubles_and_simulation_agrees():
    sw = qswitch.q_switch_pulse(3.0, **QS)
    ring = qswitch.q_switch_pulse(3.0, gain_passes=1, **QS)
    assert ring.energy == pytest.approx(2 * sw.energy)
    sim = qswitch.simulate_q_switch(3.0, gain_passes=1, **QS)
    assert sim.energy == pytest.approx(ring.energy, rel=0.01)


# ---------------------------------------------------------------------- #
# Passive Q-switching
# ---------------------------------------------------------------------- #
A = np.pi * (200e-6) ** 2 / 2
PQ = dict(absorber=pq.CR_YAG, initial_transmission=0.85, gain_area=A, absorber_area=A,
          gain_cross_section=2.8e-23, photon_energy=photon_energy(1064e-9),
          delta=-np.log(0.8) + 0.02, delta_oc=-np.log(0.8), round_trip_time=2 * 0.1 / c)


def test_absorber_losses():
    l_gs, l_es = pq.CR_YAG.losses(0.8)
    assert l_gs == pytest.approx(2 * np.log(1 / 0.8))
    assert l_es / l_gs == pytest.approx(2.2 / 8.7)
    assert pq.CR_YAG.losses(0.8, passes=1)[0] == pytest.approx(np.log(1 / 0.8))


def test_passive_pulse_is_self_consistent():
    p = pq.passive_q_switch_pulse(**PQ)
    assert p.pulse_forms and p.bleaching_criterion > 1
    # Phi(x_f) = 0 and energy formula
    f = pq._photon_function(p.final_fraction, PQ["delta"], p.l_gs, p.l_es, p.alpha)
    assert abs(f) < 1e-10
    e = (PQ["photon_energy"] * PQ["delta_oc"] * A / (2 * PQ["gain_cross_section"])
         * np.log(1 / p.final_fraction))
    assert p.energy == pytest.approx(e)


def test_passive_analytic_matches_simulation():
    a = pq.passive_q_switch_pulse(**PQ)
    s = pq.simulate_passive_q_switch(**PQ)
    assert s.energy == pytest.approx(a.energy, rel=0.01)
    assert s.peak_power == pytest.approx(a.peak_power, rel=0.02)
    assert s.final_fraction == pytest.approx(a.final_fraction, rel=0.01)


def test_passive_ring_analytic_matches_simulation():
    kw = dict(PQ, gain_passes=1, initial_transmission=0.7, absorber_area=A / 2)
    a = pq.passive_q_switch_pulse(**kw)
    s = pq.simulate_passive_q_switch(**kw)
    assert s.energy == pytest.approx(a.energy, rel=0.01)


def test_fast_absorber_limit_is_active_q_switching():
    """alpha -> infinity: the absorber bleaches at once, like an active switch."""
    kw = dict(PQ, absorber_area=A / 1e4)
    p = pq.passive_q_switch_pulse(**kw)
    r = (PQ["delta"] + p.l_gs) / (PQ["delta"] + p.l_es)
    act = qswitch.q_switch_pulse(r, A, PQ["gain_cross_section"], PQ["photon_energy"],
                                 PQ["delta"] + p.l_es, PQ["delta_oc"], PQ["round_trip_time"])
    assert p.energy == pytest.approx(act.energy, rel=1e-3)


def test_no_pulse_when_absorber_saturates_too_slowly():
    p = pq.passive_q_switch_pulse(**dict(PQ, absorber_area=4 * A))
    assert not p.pulse_forms and p.energy == 0


def test_lower_transmission_gives_more_energy():
    e = [pq.passive_q_switch_pulse(**dict(PQ, initial_transmission=t)).energy
         for t in (0.9, 0.8, 0.7)]
    assert e[0] < e[1] < e[2]


def test_passive_repetition_rate():
    assert pq.passive_repetition_rate(0.9, 0.5, 230e-6) == 0
    f = pq.passive_repetition_rate(2.0, 0.5, 230e-6)
    assert f == pytest.approx(1 / (230e-6 * np.log(1.5 / 1.0)))
    # high pump: f -> r / (tau (1 - x_f))
    big = pq.passive_repetition_rate(1e4, 0.5, 230e-6)
    assert big == pytest.approx(1e4 / (0.5 * 230e-6), rel=1e-3)


# ---------------------------------------------------------------------- #
# Kerr lens
# ---------------------------------------------------------------------- #
def test_critical_power_ti_sapphire():
    p = kerr.critical_power(800e-9, 1.76, 3.2e-20)
    assert p == pytest.approx((800e-9) ** 2 / (2 * np.pi * 1.76 * 3.2e-20))
    assert 1e6 < p < 3e6


def test_kerr_lens_power_round_beam():
    px, py = kerr.kerr_lens_power(1e5, 30e-6, 30e-6, 3e-20, 1e-3)
    assert px == py == pytest.approx(8 * 3e-20 * 1e5 * 1e-3 / (np.pi * (30e-6) ** 4))


def _x_cavity(sep, theta, L1=0.8, L2=0.6, R=0.1, lc=4e-3, slices=6):
    n = TI_SAPPHIRE.refractive_index

    def cav(crystal):
        return abcd.StandingWaveCavity(
            [abcd.FreeSpace(L1), abcd.CurvedMirror(R=R, angle=theta, name="M1"),
             abcd.FreeSpace(sep / 2), *crystal, abcd.FreeSpace(sep / 2),
             abcd.CurvedMirror(R=R, angle=theta, name="M2"), abcd.FreeSpace(L2)],
            R1=np.inf, R2=np.inf, wavelength=TI_SAPPHIRE.laser_wavelength)

    return kerr.KerrLensModel(cav, lc, n, TI_SAPPHIRE.nonlinear_index,
                              TI_SAPPHIRE.laser_wavelength, brewster=True, slices=slices,
                              name="TiS")


def test_astigmatism_compensation_formula():
    t, n, R = 3e-3, 1.76, 0.1
    th = abcd.astigmatism_compensation_angle(R, t, n)
    assert R * np.sin(th) * np.tan(th) == pytest.approx(abcd.brewster_astigmatism(t, n))
    th1 = abcd.astigmatism_compensation_angle(R, t, n, mirrors=1)
    assert R * np.sin(th1) * np.tan(th1) == pytest.approx(2 * abcd.brewster_astigmatism(t, n))


def _zone_centres(theta):
    seps = np.linspace(0.09, 0.12, 601)
    out = {}
    for plane in "ts":
        ok = [s for s in seps
              if abs(_x_cavity(s, theta).cold_cavity().stability_parameter(plane)) < 1]
        out[plane] = np.mean(ok)
    return out


def test_compensation_aligns_tangential_and_sagittal_zones():
    n = TI_SAPPHIRE.refractive_index
    thickness = 4e-3 * n / np.sqrt(n**2 + 1)
    th = abcd.astigmatism_compensation_angle(0.1, thickness, n)
    good = _zone_centres(th)
    bad = _zone_centres(0.0)
    assert abs(good["t"] - good["s"]) < 0.2 * abs(bad["t"] - bad["s"])


def test_kerr_solution_zero_power_is_cold_cavity():
    m = _x_cavity(0.100, np.radians(7))
    s = m.solve(0.0)
    cold = m.cold_cavity()
    assert s.stable
    assert m.spot_size(s, 1) == pytest.approx(cold.spot_size_on_mirror(1))


def test_klm_strength_matches_small_power_change():
    m = _x_cavity(0.100, np.radians(7))
    d = m.klm_strength(1, "t")
    w = m.spot_vs_power([0.0, 0.004], 1, "t")
    assert (w[1] / w[0] - 1) / 0.004 == pytest.approx(d, rel=0.05)
    # The Kerr lens shrinks the mode in the crystal (soft aperture) here.
    assert m.klm_strength("crystal", "t") < 0


def test_kerr_lens_is_self_consistent():
    m = _x_cavity(0.100, np.radians(7))
    sol = m.solve(0.2 * m.critical_power)
    sl = m.crystal_length / m.slices
    for ft, fs, wt, ws in zip(sol.focal_lengths_t, sol.focal_lengths_s, sol.spot_t, sol.spot_s):
        pt, ps = kerr.kerr_lens_power(0.2 * m.critical_power, wt, ws, m.n2, sl, m.n)
        assert 1 / ft == pytest.approx(pt, rel=1e-6)
        assert 1 / fs == pytest.approx(ps, rel=1e-6)


# ---------------------------------------------------------------------- #
# Side-pumped rod and ring lasers in the design layer
# ---------------------------------------------------------------------- #
def _rod_cavity(f, L=0.1, arm=0.15):
    return abcd.StandingWaveCavity(
        [abcd.FreeSpace(arm), *abcd.crystal_with_thermal_lens(L, ND_YAG.refractive_index, f,
                                                              name="rod"),
         abcd.FreeSpace(arm)], R1=np.inf, R2=np.inf, wavelength=ND_YAG.laser_wavelength)


def _rod(**kw):
    args = dict(material=ND_YAG, doping=1.0, rod_radius=2e-3, rod_length=0.1, cavity=_rod_cavity,
                crystal_element="rod thermal lens", output_coupling=0.2, passive_loss=0.03,
                absorption_efficiency=0.7)
    args.update(kw)
    return design.SidePumpedRodLaser(**args)


def test_side_pumped_threshold_formula():
    las = _rod()
    op = las.analyze(150.0)
    a = 2e-3
    expected = (ND_YAG.pump_photon_energy * las.delta
                / (2 * ND_YAG.emission_cross_section * ND_YAG.upper_state_lifetime * 0.7
                   * gain.mode_overlap(op.laser_radius, a, "gaussian", "tophat")))
    assert op.threshold == pytest.approx(expected)
    # TEM00 mode much smaller than the rod: overlap is nearly 1 / (pi a^2)
    assert op.threshold == pytest.approx(
        ND_YAG.pump_photon_energy * las.delta * np.pi * a**2
        / (2 * ND_YAG.emission_cross_section * ND_YAG.upper_state_lifetime * 0.7), rel=1e-3)


def test_side_pumped_bifocusing_and_average():
    las = _rod()
    f = las.thermal_focal_lengths(300.0)
    assert f["radial"] < f["tangential"] < f["dn_dT"]
    assert 1 / f["average"] == pytest.approx((1 / f["radial"] + 1 / f["tangential"]) / 2)
    assert las.thermal_focal_length(300 / 0.7) == pytest.approx(f["average"])
    assert _rod(thermal_lens="radial").thermal_focal_length(300 / 0.7) == pytest.approx(
        f["radial"])


def test_side_pumped_multimode():
    tem = _rod().analyze(300.0)
    mm = _rod(multimode_fill=0.8).analyze(300.0)
    assert mm.output_power > 5 * tem.output_power
    assert mm.m2_estimate == pytest.approx((0.8 * 2e-3 / mm.tem00_radius) ** 2)
    assert mm.laser_profile == "tophat" and tem.m2_estimate == 1.0


def test_side_pumped_q_switch_modes_run():
    las = _rod(multimode_fill=0.8)
    act = las.q_switched(300.0, 1e3)
    pas = las.passively_q_switched(300.0, 0.85)
    assert act["energy"] > 0 and pas["energy"] > 0 and pas["rep_rate"] > 0
    assert las.stress_fracture_pump() > 1000


def _ring(f, d=0.115, R=0.2, theta=np.radians(8)):
    return abcd.RingCavity(
        [abcd.FreeSpace(d), *abcd.crystal_with_thermal_lens(10e-3, ND_YVO4.refractive_index, f,
                                                            name="c"),
         abcd.FreeSpace(d), abcd.CurvedMirror(R=R, angle=theta, name="M1"), abcd.FreeSpace(0.2),
         abcd.FlatMirror(angle=theta, name="M2"), abcd.FreeSpace(0.2),
         abcd.FlatMirror(angle=theta, name="M3"), abcd.FreeSpace(0.2),
         abcd.CurvedMirror(R=R, angle=theta, name="M4")],
        wavelength=ND_YVO4.laser_wavelength)


def _ring_laser(cavity=_ring):
    beam = pump.PumpBeam(10.0, 80e-6, 808e-9, m2=1.0)
    return design.EndPumpedLaser(ND_YVO4, 0.3, 10e-3, beam, cavity, "c thermal lens", 0.05,
                                 0.01)


def test_ring_laser_uses_single_gain_pass():
    las = _ring_laser()
    op = las.analyze(10.0)
    assert op.stable and op.gain_passes == 1
    th = gain.threshold_pump_power(ND_YVO4, op.laser_radius, op.pump_radius, las.delta,
                                   las.absorbed_fraction, gain_passes=1)
    assert op.threshold == pytest.approx(th)
    assert design.gain_passes(abcd.StandingWaveCavity([], wavelength=1e-6)) == 2


def test_ring_laser_sesam_and_passive_q_switch():
    las = _ring_laser()
    res = las.sesam_mode_locked(10.0, 0.6, 0.01, absorber_mirror="M2")
    cav = las.resonator(10.0)
    assert res["check"].repetition_rate == pytest.approx(c / cav.optical_length)
    with pytest.raises(ValueError):
        las.sesam_mode_locked(10.0, 0.6, 0.01, absorber_mirror=2)
    pas = las.passively_q_switched(10.0, 0.95, absorber_location="M2")
    assert pas["pulse"].l_gs == pytest.approx(np.log(1 / 0.95))
