import numpy as np
import pytest

from laserdesign import gaussian, pump, thermal
from laserdesign.materials import ND_YAG, ND_YVO4, get_material


def test_q_roundtrip():
    q = gaussian.q_from_w_R(1e-3, 2.0, 1064e-9)
    assert gaussian.spot_size(q, 1064e-9) == pytest.approx(1e-3)
    assert gaussian.radius_of_curvature(q) == pytest.approx(2.0)


def test_rayleigh_range_in_medium():
    # Siegman sec. 17.1: z_R = pi n w0^2 / lambda0
    w0, n = 50e-6, 1.82
    q = gaussian.q_from_waist(w0, 1064e-9, z=0.0, n=n)
    assert q.imag * n == pytest.approx(np.pi * n * w0**2 / 1064e-9)


def test_absorbed_fraction():
    assert pump.absorbed_fraction(100.0, 0.01) == pytest.approx(1 - np.exp(-1))
    double = pump.absorbed_fraction(100.0, 0.01, passes=2)
    assert double == pytest.approx(1 - np.exp(-2))


def test_absorption_length_inverse():
    L = pump.absorption_length_for(0.9, 300.0)
    assert pump.absorbed_fraction(300.0, L) == pytest.approx(0.9)


def test_material_lookup_and_absorption():
    assert get_material("nd:yag") is ND_YAG
    # ~7 /cm for 1 at.% Nd:YAG and ~31 /cm for 1 at.% Nd:YVO4 at 808 nm
    assert ND_YAG.pump_absorption_coefficient(1.0) / 100 == pytest.approx(7.0, rel=0.05)
    assert ND_YVO4.pump_absorption_coefficient(1.0) / 100 == pytest.approx(31.5, rel=0.05)


def test_effective_radius_collimated():
    pb = pump.PumpBeam(1.0, 200e-6, 808e-9, m2=1.0)
    assert pb.effective_radius(300.0, 0.005, n=1.82) == pytest.approx(200e-6, rel=1e-3)


def test_effective_radius_grows_with_m2():
    pb1 = pump.PumpBeam(1.0, 100e-6, 808e-9, m2=1.0, waist_position=0.0)
    pb2 = pump.PumpBeam(1.0, 100e-6, 808e-9, m2=50.0, waist_position=0.0)
    assert pb2.effective_radius(200.0, 0.01, 1.82) > pb1.effective_radius(200.0, 0.01, 1.82)


def test_opd_near_axis_is_thin_lens():
    f = thermal.end_pumped_focal_length(5.0, 300e-6, 14.0, 7.3e-6)
    r = np.linspace(0, 10e-6, 5)
    opd = thermal.end_pumped_opd(r, 5.0, 300e-6, 14.0, 7.3e-6)
    np.testing.assert_allclose(opd, -r**2 / (2 * f), rtol=2e-3, atol=1e-15)


def test_temperature_profile_limits():
    # Far from the pump the Innocenzi profile becomes the line-source log law.
    p, w, K, L, r0 = 10.0, 200e-6, 14.0, 0.01, 2e-3
    t = thermal.end_pumped_temperature(np.array([1e-3]), p, w, K, L, r0)
    expected = p / (2 * np.pi * K * L) * np.log(r0 / 1e-3)
    assert t[0] == pytest.approx(expected, rel=1e-6)
    assert thermal.end_pumped_temperature(r0, p, w, K, L, r0) == pytest.approx(0.0, abs=1e-12)


def test_side_pumped_rod_parabolic_lens():
    # f = K A / (P dn/dT / 2) when only the dn/dT term is kept (Koechner eq. 7.41)
    f = thermal.side_pumped_rod_focal_length(500.0, 3.175e-3, 0.1, 14.0, 7.3e-6)
    assert f == pytest.approx(14.0 * np.pi * 3.175e-3**2 / (500.0 * 7.3e-6 / 2))


def test_fracture_limit_nd_yag():
    # Koechner: P_h/L = 8 pi R_T; with R_T = 790 W/m this is ~200 W/cm
    # (reproduced from memory, check against Koechner sec. 7.1.3).
    assert thermal.fracture_limit_per_length(ND_YAG.thermal_shock_parameter) / 100 == \
        pytest.approx(198.5, rel=0.01)
