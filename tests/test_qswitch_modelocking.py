import numpy as np
import pytest

from laserdesign import modelocking as ml
from laserdesign import qswitch as qs


def test_extraction_efficiency_reference_values():
    # Siegman fig. 26.6 / Koechner fig. 8.4: r = 2 extracts ~80 %, r = 5 ~99 %.
    assert qs.extraction_efficiency(2.0) == pytest.approx(0.797, abs=0.002)
    assert qs.extraction_efficiency(5.0) == pytest.approx(0.993, abs=0.002)


def test_final_inversion_satisfies_transcendental_equation():
    for r in [1.1, 1.5, 3.0, 10.0]:
        x = qs.final_inversion_fraction(r)
        assert r * (1 - x) == pytest.approx(-np.log(x), rel=1e-9)


PARAMS = dict(mode_area=qs.gaussian_mode_area(300e-6), emission_cross_section=2.8e-23,
              photon_energy=1.867e-19, delta=0.25, delta_oc=0.22, round_trip_time=1e-9)


@pytest.mark.parametrize("r", [1.5, 3.0, 6.0])
def test_simulation_matches_analytic(r):
    a = qs.q_switch_pulse(r, **PARAMS)
    s = qs.simulate_q_switch(r, **PARAMS)
    assert s.energy == pytest.approx(a.energy, rel=1e-3)
    assert s.peak_power == pytest.approx(a.peak_power, rel=1e-3)
    # E/P_pk is within ~25 % of the true FWHM (it overestimates the
    # asymmetric pulses of strongly pumped lasers)
    assert s.fwhm == pytest.approx(a.pulse_width, rel=0.25)


def test_repetitive_q_switch_limits():
    tau = 230e-6
    ri_low, _ = qs.repetitive_q_switch(5.0, 100.0, tau)  # f tau << 1: full recovery
    assert ri_low == pytest.approx(5.0, rel=1e-6)
    ri_high, _ = qs.repetitive_q_switch(5.0, 200e3, tau)  # fast: little recovery
    assert 1 < ri_high < 1.5


def test_transform_limits():
    assert ml.transform_limited_duration(1e12) == pytest.approx(0.315e-12)
    assert ml.transform_limited_duration(1e12, "gaussian") == pytest.approx(0.441e-12)


def test_am_mode_locking_matches_kuizenga_siegman():
    # Siegman sec. 27.5: tau = (sqrt(2 ln2)/pi) (g/delta_m)^(1/4) / sqrt(f_m dnu)
    # with g the round-trip power gain (= delta) and delta_m the modulation depth.
    delta, M, fm, dnu = 0.1, 0.5, 100e6, 120e9
    tau = ml.active_am_pulse_width(delta, M, fm, dnu)
    ks = np.sqrt(2 * np.log(2)) / np.pi * (delta / M) ** 0.25 / np.sqrt(fm * dnu)
    assert tau == pytest.approx(ks, rel=1e-9)


def test_soliton_inverse():
    spm = ml.spm_coefficient(3.2e-20, 4e-3, np.pi * (30e-6) ** 2, 800e-9)
    gdd = ml.soliton_required_gdd(50e-15, spm, 20e-9)
    assert ml.soliton_pulse_width(gdd, spm, 20e-9) == pytest.approx(50e-15)


def test_qml_threshold_formula():
    e = ml.qml_threshold_energy(1.0, 2.0, 3.0, 4.0, 0.01, gain_passes=1)
    assert e == pytest.approx(np.sqrt(2.0 * 12.0 * 0.01))


def test_repetition_rate():
    assert ml.repetition_rate(1.5) == pytest.approx(299792458 / 3.0)
