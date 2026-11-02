"""Checks built from Koechner, Solid-State Laser Engineering (6th ed., 2006).

The numbers marked "from memory" were reproduced without the book at hand;
verify them against your copy (section numbers given) and correct the test
if they differ.
"""

import numpy as np
import pytest

from laserdesign import gain, qswitch, thermal
from laserdesign.materials import ND_YAG

# Koechner Table 2.2 (from memory): Nd:YAG at room temperature
def test_nd_yag_table_values():
    assert ND_YAG.emission_cross_section == pytest.approx(2.8e-23)
    assert ND_YAG.upper_state_lifetime == pytest.approx(230e-6)
    assert ND_YAG.refractive_index == pytest.approx(1.82)
    assert ND_YAG.thermal_conductivity == pytest.approx(14.0)
    assert ND_YAG.dn_dT == pytest.approx(7.3e-6)


def test_nd_yag_saturation_fluence():
    # h nu / sigma = 0.67 J/cm^2 for Nd:YAG at 1064 nm (Koechner sec. 4.1, from memory)
    assert ND_YAG.saturation_fluence / 1e4 == pytest.approx(0.67, rel=0.01)


def test_nd_yag_saturation_intensity():
    # I_s = h nu / (sigma tau) ~ 2.9 kW/cm^2 (Koechner sec. 4.1, from memory)
    assert ND_YAG.saturation_intensity / 1e4 == pytest.approx(2.9e3, rel=0.02)


def test_side_pumped_rod_bifocusing():
    # Koechner sec. 7.1.2 (from memory): stress-induced birefringence makes
    # the thermal lens different for radial and tangential polarisation, with
    # photoelastic coefficients C_r = 0.017 and C_phi = -0.0025 for Nd:YAG.
    # Uniform heat load: 1 kW of heat in a 6.35 mm x 75 mm rod.
    args = dict(heat_power=1000.0, rod_radius=3.175e-3, length=75e-3,
                thermal_conductivity=ND_YAG.thermal_conductivity, dn_dT=ND_YAG.dn_dT,
                thermal_expansion=ND_YAG.thermal_expansion,
                refractive_index=ND_YAG.refractive_index)
    f_r = thermal.side_pumped_rod_focal_length(photoelastic_coefficient=0.017, **args)
    f_phi = thermal.side_pumped_rod_focal_length(photoelastic_coefficient=-0.0025, **args)
    f_dn = thermal.side_pumped_rod_focal_length(**{**args, "thermal_expansion": 0.0})
    # Radial polarisation focuses more strongly; both are within ~25 % of the
    # dn/dT-only value, and the radial/tangential ratio is about 1.2.
    assert f_r < f_phi
    assert f_r / f_phi == pytest.approx(0.82, abs=0.04)
    assert 0.6 < f_r / f_dn < 1.0


def test_fracture_limit_order_of_magnitude():
    # Koechner eq. 7.25: P_h / L = 8 pi R_T; R_T(Nd:YAG) ~ 790 W/m (from memory)
    p_per_cm = thermal.fracture_limit_per_length(ND_YAG.thermal_shock_parameter) / 100
    assert 150 < p_per_cm < 250


def test_q_switch_energy_utilisation_curve():
    # Koechner fig. 8.4 (energy utilisation vs n_i / n_th), same curve as Siegman:
    # r = 1.5 -> ~0.58, r = 3 -> ~0.94 (read from the figure, from memory)
    assert qswitch.extraction_efficiency(1.5) == pytest.approx(0.583, abs=0.01)
    assert qswitch.extraction_efficiency(3.0) == pytest.approx(0.940, abs=0.01)


def test_end_pumped_threshold_scaling():
    # Koechner ch. 3 (end-pumped lasers): P_th is proportional to
    # (w_l^2 + w_p^2) and to the loss.
    d = gain.round_trip_loss(0.05, 0.01)
    base = gain.threshold_pump_power(ND_YAG, 100e-6, 100e-6, d, 1.0)
    assert gain.threshold_pump_power(ND_YAG, 200e-6, 200e-6, d, 1.0) == pytest.approx(4 * base)
    assert gain.threshold_pump_power(ND_YAG, 100e-6, 100e-6, 2 * d, 1.0) == pytest.approx(2 * base)
