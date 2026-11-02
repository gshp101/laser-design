import numpy as np
import pytest

from laserdesign import abcd, pump
from laserdesign.design import EndPumpedLaser
from laserdesign.materials import ND_YVO4
from laserdesign.units import mm, nm, um


def make_laser():
    def cavity(f_th):
        return abcd.StandingWaveCavity(
            [*abcd.crystal_with_thermal_lens(4 * mm, ND_YVO4.refractive_index, f_th,
                                             name="YVO4"),
             abcd.FreeSpace(60 * mm)],
            R1=np.inf, R2=200 * mm, wavelength=ND_YVO4.laser_wavelength)

    return EndPumpedLaser(
        material=ND_YVO4, doping=0.5, crystal_length=4 * mm,
        pump_beam=pump.PumpBeam(1.0, 200 * um, 808 * nm, m2=30, waist_position=1 * mm),
        cavity=cavity, crystal_element="YVO4 thermal lens",
        output_coupling=0.1, passive_loss=0.01)


def test_cw_operating_point_sane():
    laser = make_laser()
    op = laser.analyze(10.0)
    assert op.stable
    assert 0 < op.output_power < 10.0 * laser.absorbed_fraction
    assert op.threshold < 2.0
    assert np.isfinite(op.thermal_focal_length) and op.thermal_focal_length > 0
    assert op.m2_estimate >= 1


def test_thermal_lens_shrinks_with_power():
    laser = make_laser()
    assert laser.thermal_focal_length(20.0) < laser.thermal_focal_length(5.0)


def test_q_switched_runs():
    laser = make_laser()
    out = laser.q_switched(10.0, 20e3)
    assert out["initial_ratio"] > 1
    assert out["energy"] > 0
    assert out["average_power"] < laser.analyze(10.0).output_power * 1.2


def test_sesam_check_runs():
    laser = make_laser()
    out = laser.sesam_mode_locked(10.0, 70e-6 / 1e-4, 0.005)
    assert out["check"].repetition_rate > 1e9 * 0.5
    assert out["check"].pulse_width_estimate > out["check"].transform_limit
