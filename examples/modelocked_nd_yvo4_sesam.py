"""Example 3: a 100 MHz SESAM mode-locked Nd:YVO4 laser.

A 12 W, 808 nm diode (M^2 = 30) end-pumps a 4 mm, 0.5 at.% Nd:YVO4 crystal
whose pumped face carries the HR coating (mirror 1). A curved fold mirror
(R = 500 mm, 5 deg) collimates the beam into a long arm ending on a SESAM
(mirror 2); a flat fold mirror in the long arm is the 5 % output coupler.
The 1.5 m optical length gives a 100 MHz pulse train.

The checks that decide a SESAM design, all from
:func:`laserdesign.modelocking.sesam_design_check`:

* the intracavity pulse energy must exceed the QML threshold
  (Hönninger et al. 1999) with margin,
* the SESAM should be saturated about 3 to 20 times (E_p / E_sat,A),
  enough for stable mode locking but not so much that it is damaged or
  multi-pulses, and
* the pulse width is set by the gain bandwidth and modulation depth.

For comparison the example also evaluates active AM mode locking of the same
cavity with an acousto-optic modulator.

Run ``python examples/modelocked_nd_yvo4_sesam.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import EndPumpedLaser, abcd, modelocking, pump
from laserdesign.materials import get_material
from laserdesign.units import cm2, mm, nm, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

MATERIAL = get_material("Nd:YVO4")
DOPING = 0.5
LENGTH = 4 * mm
PUMP_POWER = 12.0
PUMP = pump.PumpBeam(PUMP_POWER, waist=150 * um, wavelength=808 * nm, m2=30,
                     waist_position=1 * mm)
T_OC = 0.05
LOSS = 0.02
FOLD_R = 500 * mm
FOLD_ANGLE = np.deg2rad(5)
SHORT_ARM = 350 * mm
TOTAL_OPTICAL_LENGTH = 1500 * mm
SESAM_FSAT = 60e-6 / cm2        # 60 uJ/cm^2
SESAM_DR = 0.01                 # 1 % modulation depth


def long_arm() -> float:
    return TOTAL_OPTICAL_LENGTH - SHORT_ARM - LENGTH * MATERIAL.refractive_index


def cavity(f_thermal: float) -> abcd.StandingWaveCavity:
    d2 = long_arm()
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(SHORT_ARM),
         abcd.CurvedMirror(FOLD_R, angle=FOLD_ANGLE, name="fold mirror"),
         abcd.FreeSpace(d2 / 2),
         abcd.FlatMirror(name="output coupler (fold)"),
         abcd.FreeSpace(d2 / 2)],
        R1=np.inf, R2=np.inf, wavelength=MATERIAL.laser_wavelength)


def build() -> EndPumpedLaser:
    return EndPumpedLaser(material=MATERIAL, doping=DOPING, crystal_length=LENGTH,
                          pump_beam=PUMP, cavity=cavity, crystal_element="YVO4 thermal lens",
                          output_coupling=T_OC, passive_loss=LOSS)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    laser = build()
    res = laser.sesam_mode_locked(PUMP_POWER, SESAM_FSAT, SESAM_DR)
    op, chk = res["operating_point"], res["check"]
    cav = laser.resonator(PUMP_POWER)

    # Active AM mode locking of the same cavity, AOM driven at f_rep / 2
    # (standing-wave AOM gives loss modulation at twice the drive frequency).
    am_width = modelocking.active_am_pulse_width(laser.delta, modulation_depth=0.3,
                                                 modulation_frequency=chk.repetition_rate,
                                                 gain_bandwidth=MATERIAL.gain_bandwidth)

    stable = [p for p in np.linspace(1, 20, 77) if laser.resonator(p).is_stable()]
    summary = {
        "repetition_rate_MHz": chk.repetition_rate / 1e6,
        "average_output_W": op.output_power,
        "laser_radius_crystal_um": op.laser_radius / um,
        "pump_radius_um": op.pump_radius / um,
        "sesam_radius_um": res["absorber_radius"] / um,
        "stability_t": cav.stability_parameter("t"),
        "stability_s": cav.stability_parameter("s"),
        "intracavity_pulse_energy_nJ": chk.pulse_energy * 1e9,
        "qml_threshold_nJ": chk.qml_threshold * 1e9,
        "qml_margin": chk.qml_margin,
        "sesam_saturation": chk.absorber_saturation,
        "sesam_pulse_width_ps": chk.pulse_width_estimate * 1e12,
        "transform_limit_ps": chk.transform_limit * 1e12,
        "am_pulse_width_ps": am_width * 1e12,
        "m2_estimate": op.m2_estimate,
        "stable_pump_min_W": min(stable),
        "stable_pump_max_W": max(stable),
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
        for plane, ls in (("t", "-"), ("s", "--")):
            prof = cav.mode_profile(plane)
            ax[0].plot(prof.z / mm, prof.w / um, ls,
                       label="tangential" if plane == "t" else "sagittal")
        ax[0].set(xlabel="distance from HR face [mm]", ylabel="w [um]", title="Cavity mode")
        ax[0].legend()

        powers = np.array([p for p in np.linspace(4, 16, 49) if laser.resonator(p).is_stable()])
        checks = [laser.sesam_mode_locked(p, SESAM_FSAT, SESAM_DR)["check"] for p in powers]
        ax[1].plot(powers, [c.qml_margin for c in checks], label="E_p / E_p,QML")
        ax[1].plot(powers, [c.absorber_saturation for c in checks], label="E_p / E_sat,A")
        ax[1].axhline(1, c="k", ls=":")
        ax[1].set(xlabel="pump power [W]", ylabel="ratio", title="Mode-locking margins")
        ax[1].legend()

        dr = np.linspace(0.002, 0.03, 30)
        ax[2].plot(dr * 100, [modelocking.sesam_pulse_width_estimate(
            MATERIAL.gain_bandwidth, laser.delta + d, d) * 1e12 for d in dr], label="pulse width")
        ax2 = ax[2].twinx()
        ax2.plot(dr * 100, [laser.sesam_mode_locked(PUMP_POWER, SESAM_FSAT, d)["check"].qml_margin
                            for d in dr], "C1--", label="QML margin")
        ax[2].set(xlabel="SESAM modulation depth [%]", ylabel="pulse width estimate [ps]",
                  title="Choosing the SESAM")
        ax2.set_ylabel("QML margin", color="C1")
        fig.tight_layout()
        fig.savefig(outdir / "ml_nd_yvo4_sesam.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:30s} {v:.4g}")
