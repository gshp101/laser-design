"""Example 1: a 30 W diode end-pumped CW Nd:YVO4 laser at 1064 nm.

Design goals: close to 20 W of output with M^2 around 2 from a simple
two-mirror resonator, with the operating point well inside the stable range.

The design trade-off this example shows: the multimode pump (M^2 = 170) gives
an absorption-weighted pump radius of about 275 um. Matching the laser mode to
it improves beam quality, but the only way to make the mode that large is to
run the resonator close to the edge of stability, where the mode size swings
quickly with pump power. A 45 mm gap with a 500 mm output coupler keeps
m = (A+D)/2 near -0.7 at full power.

Run ``python examples/cw_nd_yvo4.py`` to print a summary and write figures to
``docs/examples/images``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import EndPumpedLaser, abcd, gain, pump
from laserdesign.materials import get_material
from laserdesign.units import mm, nm, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

MATERIAL = get_material("Nd:YVO4")
DOPING = 0.27              # at.%
LENGTH = 10 * mm
PUMP_POWER = 30.0          # W, fibre-coupled 400 um / 0.22 NA diode
PUMP = pump.PumpBeam(PUMP_POWER, waist=250 * um, wavelength=808 * nm,
                     m2=170, waist_position=2 * mm)
GAP = 45 * mm              # crystal to output coupler
R_OC = 500 * mm            # output coupler radius of curvature
T_OC = 0.20                # output coupler transmission
LOSS = 0.01                # other round-trip losses


def cavity(f_thermal: float, gap: float | None = None,
           r_oc: float | None = None) -> abcd.StandingWaveCavity:
    """Plano-concave resonator: HR coating on the pumped crystal face (mirror 1),
    crystal with thermal lens, air gap, curved output coupler (mirror 2)."""
    gap = GAP if gap is None else gap
    r_oc = R_OC if r_oc is None else r_oc
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(gap)],
        R1=np.inf, R2=r_oc, wavelength=MATERIAL.laser_wavelength)


def build(output_coupling: float = T_OC) -> EndPumpedLaser:
    return EndPumpedLaser(material=MATERIAL, doping=DOPING, crystal_length=LENGTH,
                          pump_beam=PUMP, cavity=cavity, crystal_element="YVO4 thermal lens",
                          output_coupling=output_coupling, passive_loss=LOSS)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    laser = build()
    powers = np.linspace(1, 34, 34)
    ops = laser.scan(powers)
    op = laser.analyze(PUMP_POWER)

    # Output coupler optimisation at full pump power
    couplings = np.array([0.03, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4])
    oc_power = np.array([build(t).analyze(PUMP_POWER).output_power for t in couplings])

    summary = {
        "absorbed_fraction": laser.absorbed_fraction,
        "pump_radius_um": op.pump_radius / um,
        "thermal_focal_length_mm": op.thermal_focal_length / mm,
        "stability_parameter": op.stability_parameter,
        "laser_radius_um": op.laser_radius / um,
        "threshold_W": op.threshold,
        "output_W": op.output_power,
        "optical_efficiency": op.output_power / PUMP_POWER,
        "m2_estimate": op.m2_estimate,
        "best_output_coupling": float(couplings[np.argmax(oc_power)]),
        "max_stable_pump_W": float(max(p for p, o in zip(powers, ops) if o.stable)),
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        stable = [o for o in ops if o.stable]
        p = np.array([o.pump_power for o in stable])
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        ax[0, 0].plot(p, [o.output_power for o in stable])
        ax[0, 0].set(xlabel="pump power [W]", ylabel="output [W]", title="Output power")
        ax[0, 1].plot(powers, [o.stability_parameter for o in ops])
        ax[0, 1].axhline(-1, ls="--", c="k")
        ax[0, 1].axhline(1, ls="--", c="k")
        ax[0, 1].set(xlabel="pump power [W]", ylabel="m = (A+D)/2", title="Resonator stability")
        ax[1, 0].plot(p, [o.laser_radius / um for o in stable], label="laser mode")
        ax[1, 0].plot(p, [o.pump_radius / um for o in stable], "--", label="pump")
        ax[1, 0].set(xlabel="pump power [W]", ylabel="radius in crystal [um]", title="Mode match")
        ax[1, 0].legend()
        ax[1, 1].plot(p, [o.m2_estimate for o in stable], label="combined")
        ax[1, 1].plot(p, [o.m2_aberration for o in stable], ":", label="thermal aberration")
        ax[1, 1].plot(p, [o.m2_multimode for o in stable], "--", label="pump/mode ratio")
        ax[1, 1].set(xlabel="pump power [W]", ylabel="M^2", title="Beam quality estimate")
        ax[1, 1].legend()
        fig.tight_layout()
        fig.savefig(outdir / "cw_nd_yvo4_performance.png", dpi=110)
        plt.close(fig)

        prof = laser.resonator(PUMP_POWER).mode_profile()
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.5))
        a1.plot(prof.z / mm, prof.w / um)
        a1.axvspan(0, LENGTH / mm, color="C1", alpha=0.2, label="crystal")
        a1.set(xlabel="distance from HR face [mm]", ylabel="w [um]",
               title=f"TEM00 mode at {PUMP_POWER:.0f} W pump")
        a1.legend()
        a2.plot(couplings * 100, oc_power, "o-")
        a2.set(xlabel="output coupling T [%]", ylabel="output [W]", title="Output coupler choice")
        fig.tight_layout()
        fig.savefig(outdir / "cw_nd_yvo4_mode_and_oc.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:28s} {v:.4g}")
