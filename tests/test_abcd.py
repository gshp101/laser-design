"""Resonator tests against closed-form results in Siegman, Lasers, ch. 19-21."""

import numpy as np
import pytest

from laserdesign import abcd, gaussian

LAM = 1064e-9


@pytest.mark.parametrize("L,R1,R2", [(1.0, 2.0, 2.0), (0.3, 0.5, np.inf),
                                     (0.25, 1.0, 0.4), (0.1, np.inf, 0.15)])
def test_two_mirror_matches_siegman(L, R1, R2):
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(L)], R1=R1, R2=R2, wavelength=LAM)
    ref = abcd.two_mirror_mode(L, R1, R2, LAM)
    assert cav.stability_parameter() == pytest.approx(2 * ref["g1"] * ref["g2"] - 1)
    assert cav.spot_size_on_mirror(1) == pytest.approx(ref["w1"], rel=1e-9)
    assert cav.spot_size_on_mirror(2) == pytest.approx(ref["w2"], rel=1e-9)
    w0, z = gaussian.waist_from_q(cav.eigen_q(), LAM)
    assert w0 == pytest.approx(ref["w0"], rel=1e-9)
    assert z == pytest.approx(ref["z1"], rel=1e-9)


def test_symmetric_confocal_spot_size():
    # Siegman eq. 19.25: confocal w0 = sqrt(L lambda / 2 pi), mirror w = sqrt(2) w0
    # The exactly confocal cavity is marginal (m = -1), so approach the limit.
    L = 0.5
    R = L * (1 + 1e-7)
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(L)], R1=R, R2=R, wavelength=LAM)
    w0 = np.sqrt(L * LAM / (2 * np.pi))
    assert cav.spot_size_on_mirror(1) == pytest.approx(np.sqrt(2) * w0, rel=1e-3)


def test_unstable_cavity_detected():
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(1.0)], R1=0.4, R2=0.4, wavelength=LAM)
    assert not cav.is_stable()
    with pytest.raises(ValueError):
        cav.eigen_q()


def test_dielectric_reduces_effective_length():
    # A crystal of length L and index n behaves like air of length L/n.
    n, L = 1.82, 0.02
    cav1 = abcd.StandingWaveCavity([abcd.FreeSpace(0.05), abcd.Medium(L, n=n)], R2=0.2,
                                   wavelength=LAM)
    cav2 = abcd.StandingWaveCavity([abcd.FreeSpace(0.05 + L / n)], R2=0.2, wavelength=LAM)
    assert cav1.spot_size(0) == pytest.approx(cav2.spot_size(0))
    assert cav1.optical_length == pytest.approx(0.05 + n * L)


def test_free_spectral_range():
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(1.5)], R1=2, R2=2, wavelength=LAM)
    assert cav.free_spectral_range == pytest.approx(299792458 / 3.0)


def test_transverse_mode_spacing_two_mirror():
    # Siegman eq. 19.31: delta_nu_T / FSR = arccos(sqrt(g1 g2)) / pi
    L, R = 1.0, 3.0
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(L)], R1=R, R2=R, wavelength=LAM)
    g = 1 - L / R
    assert cav.transverse_mode_spacing() / cav.free_spectral_range == pytest.approx(
        np.arccos(np.sqrt(g * g)) / np.pi)


def test_off_axis_mirror_astigmatism():
    m = abcd.CurvedMirror(R=0.1, angle=np.deg2rad(10))
    f_t = -1 / m.matrix("t")[1, 0]
    f_s = -1 / m.matrix("s")[1, 0]
    assert f_t == pytest.approx(0.05 * np.cos(np.deg2rad(10)))
    assert f_s == pytest.approx(0.05 / np.cos(np.deg2rad(10)))


def test_ring_equals_unfolded_standing_wave():
    # A ring of two lenses f spaced d is equivalent to a two-mirror cavity
    # of length d with R = 2f.
    f, d = 0.5, 0.6
    ring = abcd.RingCavity([abcd.FreeSpace(d), abcd.ThinLens(f), abcd.FreeSpace(d),
                            abcd.ThinLens(f)], wavelength=LAM)
    lin = abcd.StandingWaveCavity([abcd.FreeSpace(d)], R1=2 * f, R2=2 * f, wavelength=LAM)
    # The ring reference plane is just before the first gap, i.e. just after a lens.
    assert ring.spot_size(0) == pytest.approx(lin.spot_size_on_mirror(1))


def test_mode_profile_endpoints():
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(0.3)], R1=np.inf, R2=0.5, wavelength=LAM)
    prof = cav.mode_profile()
    assert prof.w[0] == pytest.approx(cav.spot_size_on_mirror(1))
    assert prof.w[-1] == pytest.approx(cav.spot_size_on_mirror(2))
    assert prof.z[-1] == pytest.approx(0.3)


def test_round_trip_profile_standing_wave():
    cav = abcd.StandingWaveCavity([abcd.FreeSpace(0.1), abcd.ThinLens(0.4, name="lens"),
                                   abcd.FreeSpace(0.2)], R1=np.inf, R2=0.5, wavelength=LAM)
    prof = cav.round_trip_profile()
    one = cav.mode_profile()
    # M1 -> M2 -> M1: twice the length, closes on itself, mirror symmetric about M2.
    assert prof.z[-1] == pytest.approx(0.6)
    assert prof.w[0] == pytest.approx(prof.w[-1])
    assert prof.w[0] == pytest.approx(cav.spot_size_on_mirror(1))
    assert np.interp(0.3, prof.z, prof.w) == pytest.approx(cav.spot_size_on_mirror(2))
    assert np.interp(0.45, prof.z, prof.w) == pytest.approx(np.interp(0.15, one.z, one.w))
    assert prof.landmarks == [(0.0, "M1"), (pytest.approx(0.1), "lens"), (pytest.approx(0.3), "M2"),
                              (pytest.approx(0.5), "lens"), (pytest.approx(0.6), "M1")]


def test_round_trip_profile_ring_is_one_loop():
    f, d = 0.5, 0.6
    ring = abcd.RingCavity([abcd.FreeSpace(d), abcd.CurvedMirror(2 * f, name="A"),
                            abcd.FreeSpace(d), abcd.CurvedMirror(2 * f)], wavelength=LAM)
    prof = ring.round_trip_profile()
    assert prof.z[-1] == pytest.approx(2 * d)
    assert prof.w[0] == pytest.approx(prof.w[-1])
    assert np.allclose(prof.w, ring.mode_profile().w)
    assert [label for _, label in prof.landmarks] == ["A", "mirror"]


def test_thermal_lens_crystal_helper():
    els = abcd.crystal_with_thermal_lens(0.01, 1.82, 0.2, name="YAG")
    assert [e.name for e in els][1] == "YAG thermal lens"
    m = abcd.system_matrix(els)
    assert m[1, 0] == pytest.approx(-1 / 0.2)


def test_interface_reversal_round_trip():
    # Lens made of two curved interfaces: forward then reversed should be
    # consistent with the lensmaker's equation in the thin limit.
    n, R = 1.5, 0.1
    els = [abcd.Interface(1, n, R), abcd.Interface(n, 1, -R)]
    m = abcd.system_matrix(els)
    assert -1 / m[1, 0] == pytest.approx(1 / ((n - 1) * 2 / R))
    rev = abcd.system_matrix([e.reversed() for e in reversed(els)])
    assert rev[1, 0] == pytest.approx(m[1, 0])
