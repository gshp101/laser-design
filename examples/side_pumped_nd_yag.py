"""Example 7: a diode side-pumped Nd:YAG rod laser, CW and Q-switched.

Complements the Koechner example (thermal effects only) with the full
:class:`laserdesign.design.SidePumpedRodLaser` model: a 4 mm x 65 mm Nd:YAG
rod pumped uniformly from three sides by 808 nm diode bars, in a flat-flat
resonator. The example compares

* TEM00 operation (as with an intracavity aperture) and free-running
  multimode operation, where the beam fills about 80 % of the rod;
* the stable pump range for the radially and tangentially polarised thermal
  lenses (stress bifocusing) and their average;
* M^2 against pump power for the multimode laser;
* and actively (AO, 1 kHz) and passively (Cr:YAG) Q-switched pulse energies.

Rod, pump and coefficient values are typical of Koechner, *Solid-State Laser
Engineering*, ch. 6 and 7; check them against your hardware.

Run ``python examples/side_pumped_nd_yag.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import SidePumpedRodLaser, abcd
from laserdesign.materials import get_material
from laserdesign.units import mJ, mm, ns

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

YAG = get_material("Nd:YAG")
ROD_RADIUS = 2 * mm
ROD_LENGTH = 65 * mm
ARM = 300 * mm               # rod end to each flat mirror
T_OC = 0.20
LOSS = 0.04                  # AO cell, rod AR coatings, scatter
ABSORPTION = 0.70            # diode light absorbed in the rod (eta_t eta_a)
PUMP = 400.0                 # W of diode light
FILL = 0.8                   # multimode beam radius / rod radius


def cavity(f_thermal: float) -> abcd.StandingWaveCavity:
    """Flat HR, arm, rod (thin thermal lens at its centre), arm, flat output coupler."""
    return abcd.StandingWaveCavity(
        [abcd.FreeSpace(ARM, name="HR arm"),
         *abcd.crystal_with_thermal_lens(ROD_LENGTH, YAG.refractive_index, f_thermal,
                                         name="rod"),
         abcd.FreeSpace(ARM, name="OC arm")],
        R1=np.inf, R2=np.inf, wavelength=YAG.laser_wavelength)


def build(multimode_fill: float | None = None, lens: str = "average") -> SidePumpedRodLaser:
    return SidePumpedRodLaser(material=YAG, doping=1.0, rod_radius=ROD_RADIUS,
                              rod_length=ROD_LENGTH, cavity=cavity,
                              crystal_element="rod thermal lens", output_coupling=T_OC,
                              passive_loss=LOSS, absorption_efficiency=ABSORPTION,
                              thermal_lens=lens, multimode_fill=multimode_fill)


def stable_range(laser: SidePumpedRodLaser, powers) -> tuple[float, float]:
    ok = [p for p in powers if laser.resonator(p).is_stable()]
    return (min(ok), max(ok)) if ok else (np.nan, np.nan)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    tem = build()
    mm_laser = build(FILL)
    powers = np.linspace(20, 1500, 75)
    tem_ops = tem.scan(powers)
    mm_ops = mm_laser.scan(powers)
    op_t = tem.analyze(PUMP)
    op_m = mm_laser.analyze(PUMP)
    f = tem.thermal_focal_lengths(PUMP * ABSORPTION)
    ranges = {lens: stable_range(build(lens=lens), powers)
              for lens in ("radial", "tangential", "average")}

    qs_pumps = np.linspace(150, 900, 16)
    act = [mm_laser.q_switched(p, 1e3) for p in qs_pumps]
    pas = [mm_laser.passively_q_switched(p, 0.7, "cr:yag", absorber_location=2)
           for p in qs_pumps]
    a_op = mm_laser.q_switched(PUMP, 1e3)
    p_op = mm_laser.passively_q_switched(PUMP, 0.7, "cr:yag", absorber_location=2)

    summary = {
        "threshold_W": op_t.threshold,
        "f_radial_mm": f["radial"] / mm,
        "f_tangential_mm": f["tangential"] / mm,
        "f_average_mm": f["average"] / mm,
        "tem00_radius_mm": op_t.tem00_radius / mm,
        "tem00_output_W": op_t.output_power,
        "multimode_output_W": op_m.output_power,
        "multimode_m2": op_m.m2_estimate,
        "fracture_pump_W": tem.stress_fracture_pump() / ABSORPTION,
        "active_1kHz_energy_mJ": a_op["energy"] / mJ,
        "active_1kHz_width_ns": a_op["pulse_width"] / ns,
        "passive_energy_mJ": p_op["energy"] / mJ,
        "passive_width_ns": p_op["pulse_width"] / ns,
        "passive_rep_rate_Hz": p_op["rep_rate"],
        "passive_threshold_W": p_op["threshold"],
    }
    for lens, (lo, hi) in ranges.items():
        summary[f"stable_{lens}_W"] = f"{lo:.0f}-{hi:.0f}"

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        for ops, label in ((tem_ops, "TEM00 (aperture)"), (mm_ops, f"multimode, fill {FILL}")):
            st = [o for o in ops if o.stable]
            ax[0, 0].plot([o.pump_power for o in st], [o.output_power for o in st], label=label)
        ax[0, 0].set(xlabel="diode pump power [W]", ylabel="output [W]", title="CW output")
        ax[0, 0].legend()
        for lens, ls in (("radial", "-"), ("tangential", "--"), ("average", ":")):
            las = build(lens=lens)
            ax[0, 1].plot(powers, [las.resonator(p).stability_parameter() for p in powers], ls,
                          label=lens)
        ax[0, 1].axhline(1, c="k", lw=0.6)
        ax[0, 1].axhline(-1, c="k", lw=0.6)
        ax[0, 1].set(xlabel="diode pump power [W]", ylabel="m = (A+D)/2", ylim=(-3, 1.5),
                     title="Stability with bifocusing")
        ax[0, 1].legend()
        st = [o for o in mm_ops if o.stable]
        ax[1, 0].plot([o.pump_power for o in st], [o.m2_estimate for o in st])
        ax[1, 0].set(xlabel="diode pump power [W]", ylabel="M^2",
                     title="Multimode beam quality (fill x rod / w00)^2")
        ax[1, 1].plot(qs_pumps, [a["energy"] / mJ for a in act], label="AO Q-switch, 1 kHz")
        ax[1, 1].plot(qs_pumps, [p["energy"] / mJ for p in pas], "--",
                      label="Cr:YAG, T0 = 0.7")
        ax2 = ax[1, 1].twinx()
        ax2.plot(qs_pumps, [p["rep_rate"] for p in pas], "C1:", label="Cr:YAG rep. rate")
        ax2.set_ylabel("Cr:YAG repetition rate [Hz]", color="C1")
        ax[1, 1].set(xlabel="diode pump power [W]", ylabel="pulse energy [mJ]",
                     title="Q-switched (multimode)")
        ax[1, 1].legend(loc="upper left")
        fig.tight_layout()
        fig.savefig(outdir / "side_pumped_nd_yag.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:28s} {v:.4g}" if isinstance(v, float) else f"{k:28s} {v}")
