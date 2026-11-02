import numpy as np
import pytest

from laserdesign import beam_quality as bq
from laserdesign import gaussian


def test_gaussian_is_one():
    w = 1e-3
    r = np.linspace(0, 5 * w, 4000)
    assert bq.m2_radial_field(r, np.exp(-r**2 / w**2)) == pytest.approx(1.0, abs=1e-4)


def test_lens_does_not_change_m2():
    w, lam, f = 1e-3, 1e-6, 0.3
    r = np.linspace(0, 5 * w, 6000)
    e = np.exp(-r**2 / w**2) * np.exp(-1j * np.pi * r**2 / (lam * f))
    assert bq.m2_radial_field(r, e) == pytest.approx(1.0, abs=1e-3)


def test_laguerre_gauss_p1():
    # LG_10 has M^2 = 2p + |l| + 1 = 3 (Siegman, SPIE 1224)
    w = 1e-3
    r = np.linspace(0, 6 * w, 8000)
    x = 2 * r**2 / w**2
    e = (1 - x) * np.exp(-r**2 / w**2)
    assert bq.m2_radial_field(r, e) == pytest.approx(3.0, abs=1e-3)


def test_thermal_aberration_grows_with_heat_and_mode_size():
    args = dict(thermal_conductivity=5.23, dn_dT=3e-6, wavelength=1064e-9)
    small = bq.m2_thermal_aberration(150e-6, 200e-6, 2.0, **args)
    big_heat = bq.m2_thermal_aberration(150e-6, 200e-6, 8.0, **args)
    big_mode = bq.m2_thermal_aberration(300e-6, 200e-6, 2.0, **args)
    assert 1.0 <= small < big_heat
    assert small < big_mode


def test_small_mode_in_large_pump_is_nearly_perfect():
    m2 = bq.m2_thermal_aberration(50e-6, 500e-6, 5.0, 14.0, 7.3e-6, 1064e-9)
    assert m2 == pytest.approx(1.0, abs=0.01)


def test_caustic_fit():
    lam, w0, m2 = 1064e-9, 80e-6, 1.7
    z = np.linspace(-0.1, 0.1, 21)
    w = gaussian.beam_radius(z, w0, lam, z0=0.01, m2=m2)
    fit = bq.fit_m2_caustic(z, w, lam)
    assert fit.m2 == pytest.approx(m2, rel=1e-6)
    assert fit.waist == pytest.approx(w0, rel=1e-6)
    assert fit.waist_position == pytest.approx(0.01, abs=1e-9)


def test_combine():
    assert bq.combine_m2(1.0, 1.0) == pytest.approx(1.0)
    assert bq.combine_m2(2.0, 1.0) == pytest.approx(2.0)
