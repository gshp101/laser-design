import numpy as np
import pytest

from laserdesign import gain
from laserdesign.materials import ND_YVO4, YB_YAG


def test_round_trip_loss_small_values():
    assert gain.round_trip_loss(0.02, 0.01) == pytest.approx(0.03, rel=0.02)


def test_threshold_formula_value():
    # Hand evaluation of the Moulton/Risk formula for Nd:YVO4.
    w = 200e-6
    d = gain.round_trip_loss(0.1, 0.02)
    p = gain.threshold_pump_power(ND_YVO4, w, w, d, 1.0)
    expected = (np.pi * ND_YVO4.pump_photon_energy * 2 * w**2 * d
                / (4 * ND_YVO4.emission_cross_section * ND_YVO4.upper_state_lifetime))
    assert p == pytest.approx(expected)


def test_numeric_model_threshold_matches_analytic():
    args = dict(laser_radius=200e-6, pump_radius=150e-6, output_coupling=0.1,
                passive_loss=0.02, absorbed_fraction=0.95)
    th = gain.threshold_pump_power(ND_YVO4, 200e-6, 150e-6,
                                   gain.round_trip_loss(0.1, 0.02), 0.95)
    below = gain.end_pumped_cw(ND_YVO4, 0.99 * th, **args)
    above = gain.end_pumped_cw(ND_YVO4, 1.01 * th, **args)
    assert not below.above_threshold
    assert above.above_threshold and above.output_power > 0


def test_slope_tends_to_ideal_for_small_pump():
    """With w_p << w_l, slope efficiency approaches eta_abs * lambda_p/lambda_l * T/delta."""
    kw = dict(laser_radius=400e-6, pump_radius=40e-6, output_coupling=0.1,
              passive_loss=0.01, absorbed_fraction=1.0)
    p1 = gain.end_pumped_cw(ND_YVO4, 20.0, **kw).output_power
    p2 = gain.end_pumped_cw(ND_YVO4, 21.0, **kw).output_power
    ideal = gain.slope_efficiency(ND_YVO4, 0.1, gain.round_trip_loss(0.1, 0.01), 1.0)
    assert (p2 - p1) == pytest.approx(ideal, rel=0.05)


def test_large_pump_reduces_slope():
    common = dict(laser_radius=150e-6, output_coupling=0.1, passive_loss=0.01,
                  absorbed_fraction=1.0)
    def slope(wp):
        a = gain.end_pumped_cw(ND_YVO4, 10.0, pump_radius=wp, **common).output_power
        b = gain.end_pumped_cw(ND_YVO4, 11.0, pump_radius=wp, **common).output_power
        return b - a
    assert slope(400e-6) < slope(100e-6)


def test_quasi_three_level_threshold_includes_reabsorption():
    d = gain.round_trip_loss(0.05, 0.01)
    p4 = gain.threshold_pump_power(YB_YAG, 100e-6, 100e-6, d, 0.9)
    p3 = gain.threshold_pump_power(YB_YAG, 100e-6, 100e-6, d, 0.9, crystal_length=2e-3,
                                   doping=10.0)
    assert p3 > p4
    # numeric model agrees with the analytic quasi-three-level threshold
    kw = dict(laser_radius=100e-6, pump_radius=100e-6, output_coupling=0.05,
              passive_loss=0.01, absorbed_fraction=0.9, crystal_length=2e-3, doping=10.0)
    assert not gain.end_pumped_cw(YB_YAG, 0.99 * p3, **kw).above_threshold
    assert gain.end_pumped_cw(YB_YAG, 1.01 * p3, **kw).above_threshold


def test_rigrod_optimum():
    g0, L = 0.5, 0.02
    t_opt = gain.optimum_output_coupling(g0, L)
    ts = np.linspace(0.001, 0.4, 4000)
    best = ts[np.argmax([gain.rigrod_output_intensity(g0, t, L, 1.0) for t in ts])]
    assert t_opt == pytest.approx(best, abs=2e-4)
