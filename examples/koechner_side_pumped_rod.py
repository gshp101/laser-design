"""Example 4: a diode side-pumped Nd:YAG rod and its thermally loaded resonator.

This example follows the treatment of thermal effects and resonator design in
Koechner, *Solid-State Laser Engineering* (6th ed.), chapters 5, 7 and 8:

1. Thermal lensing of a uniformly pumped Nd:YAG rod (Koechner eq. 7.41),
   including stress-induced bifocusing for radially and tangentially
   polarised light (photo-elastic coefficients C_r = 0.017 and
   C_phi = -0.0025).
2. The fracture limit P_h / L = 8 pi R_T (Koechner eq. 7.25).
3. Stability of a flat-flat resonator around the rod as the pump power
   changes: the thermal lens makes an otherwise marginal resonator stable
   over a pump range set by the arm length, and bifocusing means the two
   polarisations leave the stable zone at different powers (Koechner sec. 5.1).
4. The Q-switch energy extraction curve (Koechner fig. 8.4) and why Nd:YAG
   stores more energy than Nd:YVO4 at low repetition rates.

The rod (6.35 mm x 75 mm) and coefficients are typical Koechner values but
were entered from memory; check them against your copy.

Run ``python examples/koechner_side_pumped_rod.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import abcd, qswitch, thermal
from laserdesign.materials import get_material
from laserdesign.units import mm

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

YAG = get_material("Nd:YAG")
YVO4 = get_material("Nd:YVO4")
ROD_RADIUS = 3.175 * mm
ROD_LENGTH = 75 * mm
C_RADIAL = 0.017
C_TANGENTIAL = -0.0025
HEAT_FRACTION = 0.32           # diode pumping; lamp pumping is several times worse


def rod_focal_lengths(absorbed_power: float) -> dict:
    """Thermal focal lengths [m] for dn/dT only, radial and tangential polarisation."""
    p_h = absorbed_power * HEAT_FRACTION
    common = dict(heat_power=p_h, rod_radius=ROD_RADIUS, length=ROD_LENGTH,
                  thermal_conductivity=YAG.thermal_conductivity, dn_dT=YAG.dn_dT,
                  refractive_index=YAG.refractive_index)
    return {
        "dn_dT_only": thermal.side_pumped_rod_focal_length(**common),
        "radial": thermal.side_pumped_rod_focal_length(
            thermal_expansion=YAG.thermal_expansion, photoelastic_coefficient=C_RADIAL,
            **common),
        "tangential": thermal.side_pumped_rod_focal_length(
            thermal_expansion=YAG.thermal_expansion, photoelastic_coefficient=C_TANGENTIAL,
            **common),
    }


def flat_flat_cavity(f_rod: float, arm: float) -> abcd.StandingWaveCavity:
    """Symmetric flat-flat resonator with the rod in the middle."""
    return abcd.StandingWaveCavity(
        [abcd.FreeSpace(arm),
         *abcd.crystal_with_thermal_lens(ROD_LENGTH, YAG.refractive_index, f_rod, name="rod"),
         abcd.FreeSpace(arm)],
        R1=np.inf, R2=np.inf, wavelength=YAG.laser_wavelength)


def stable_range(arm: float, pol: str, powers) -> tuple[float, float]:
    ok = [p for p in powers if flat_flat_cavity(rod_focal_lengths(p)[pol], arm).is_stable()]
    return (min(ok), max(ok)) if ok else (np.nan, np.nan)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    powers = np.linspace(20, 4000, 400)
    f_500 = rod_focal_lengths(500.0)  # 500 W absorbed
    fracture_heat = thermal.fracture_limit_per_length(YAG.thermal_shock_parameter) * ROD_LENGTH
    arms = [200 * mm, 500 * mm, 1000 * mm]
    ranges = {(a, pol): stable_range(a, pol, powers) for a in arms for pol in ("radial", "tangential")}

    summary = {
        "f_dn_dT_only_at_500W_mm": f_500["dn_dT_only"] / mm,
        "f_radial_at_500W_mm": f_500["radial"] / mm,
        "f_tangential_at_500W_mm": f_500["tangential"] / mm,
        "bifocal_ratio_r_over_phi": f_500["radial"] / f_500["tangential"],
        "centre_temperature_rise_at_500W_K": thermal.side_pumped_center_temperature(
            500 * HEAT_FRACTION, ROD_LENGTH, YAG.thermal_conductivity),
        "fracture_heat_W": fracture_heat,
        "fracture_absorbed_pump_W": fracture_heat / HEAT_FRACTION,
        "extraction_r2": qswitch.extraction_efficiency(2.0),
        "extraction_r5": qswitch.extraction_efficiency(5.0),
    }
    for a in arms:
        lo, hi = ranges[(a, "radial")]
        summary[f"stable_radial_arm{a / mm:.0f}mm_W"] = f"{lo:.0f}-{hi:.0f}"
        lo, hi = ranges[(a, "tangential")]
        summary[f"stable_tangential_arm{a / mm:.0f}mm_W"] = f"{lo:.0f}-{hi:.0f}"

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        fl = [rod_focal_lengths(p) for p in powers]
        for key, ls in (("radial", "-"), ("tangential", "--"), ("dn_dT_only", ":")):
            ax[0, 0].loglog(powers, [f[key] for f in fl], ls, label=key.replace("_", " "))
        ax[0, 0].set(xlabel="absorbed pump [W]", ylabel="thermal focal length [m]",
                     title="Rod thermal lens (bifocusing)")
        ax[0, 0].legend()

        for a, c in zip(arms, ("C0", "C1", "C2")):
            for pol, ls in (("radial", "-"), ("tangential", "--")):
                m = [flat_flat_cavity(f[pol], a).stability_parameter() for f in fl]
                ax[0, 1].plot(powers, m, ls, color=c,
                              label=f"arm {a / mm:.0f} mm" if pol == "radial" else None)
        ax[0, 1].axhline(1, c="k", lw=0.8)
        ax[0, 1].axhline(-1, c="k", lw=0.8)
        ax[0, 1].set(ylim=(-3, 1.5), xlabel="absorbed pump [W]", ylabel="m = (A+D)/2",
                     title="Flat-flat resonator stability (solid radial, dashed tangential)")
        ax[0, 1].legend(fontsize=8)

        for a, c in zip(arms, ("C0", "C1", "C2")):
            w = []
            for f in fl:
                cav = flat_flat_cavity(f["radial"], a)
                w.append(cav.spot_size_at("rod thermal lens") / mm if cav.is_stable() else np.nan)
            ax[1, 0].plot(powers, w, color=c, label=f"arm {a / mm:.0f} mm")
        ax[1, 0].axhline(ROD_RADIUS / mm, c="k", ls=":", label="rod radius")
        ax[1, 0].set(xlabel="absorbed pump [W]", ylabel="TEM00 radius in rod [mm]",
                     title="Mode size in the stable zone", ylim=(0, 3.5))
        ax[1, 0].legend(fontsize=8)

        r = np.linspace(1.05, 8, 200)
        ax[1, 1].plot(r, [qswitch.extraction_efficiency(x) for x in r], label="extraction")
        rep = np.geomspace(0.1, 100, 200)  # kHz
        ax2 = ax[1, 1].twiny()
        for mat, ls in ((YAG, "C1--"), (YVO4, "C2:")):
            ax2.semilogx(rep, 1 - np.exp(-1 / (rep * 1e3 * mat.upper_state_lifetime)), ls,
                         label=f"{mat.name.split()[0]} stored fraction")
        ax[1, 1].set(xlabel="N_i / N_th", ylabel="fraction", title="Q-switch energy (Koechner fig. 8.4)")
        ax2.set_xlabel("repetition rate [kHz]")
        ax[1, 1].legend(loc="center right", fontsize=8)
        ax2.legend(loc="lower left", fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / "koechner_rod.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:38s} {v if isinstance(v, str) else f'{v:.4g}'}")
