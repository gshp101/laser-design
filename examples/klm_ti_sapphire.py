"""Example 6: a Kerr-lens mode-locked Ti:sapphire X-cavity.

The classic femtosecond oscillator: a 4 mm Brewster-cut Ti:sapphire crystal
between two R = 100 mm folding mirrors, with a flat output coupler at the
end of a 0.8 m arm and a flat high reflector (behind a prism pair) at the
end of a 0.6 m arm. The example

1. finds the fold angle that cancels the astigmatism of the Brewster crystal
   (:func:`laserdesign.abcd.astigmatism_compensation_angle`);
2. maps the two stability zones against the folding-mirror separation;
3. computes the KLM strength ``delta = (1/w) dw/dp`` for a hard aperture at
   the output coupler and for the soft (gain) aperture in the crystal
   (:class:`laserdesign.kerr.KerrLensModel`), which shows why KLM lasers are
   aligned near a zone edge;
4. and estimates the net negative GDD the prisms must supply for 15 fs
   soliton pulses (:func:`laserdesign.modelocking.soliton_required_gdd`).

Run ``python examples/klm_ti_sapphire.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import abcd, kerr, modelocking
from laserdesign.materials import get_material
from laserdesign.units import fs, mm, nJ, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

TIS = get_material("Ti:sapphire")
N = TIS.refractive_index
CRYSTAL_PATH = 4 * mm                          # path length inside the crystal
THICKNESS = CRYSTAL_PATH * N / np.sqrt(N**2 + 1)
R = 100 * mm
ARM_OC = 800 * mm
ARM_HR = 600 * mm
OUTPUT_COUPLING = 0.05
AVERAGE_OUTPUT = 0.5                           # W, mode-locked
PULSE_WIDTH = 15 * fs
THETA = abcd.astigmatism_compensation_angle(R, THICKNESS, N, mirrors=2)
SEPARATIONS = np.linspace(97 * mm, 109 * mm, 121)   # air path mirror-crystal-mirror


def model(separation: float, theta: float = THETA, slices: int = 6) -> kerr.KerrLensModel:
    """X-cavity with ``separation`` of air between the folding mirrors."""

    def cavity(crystal):
        return abcd.StandingWaveCavity(
            [abcd.FreeSpace(ARM_OC, name="OC arm"),
             abcd.CurvedMirror(R=R, angle=theta, name="M1"),
             abcd.FreeSpace(separation / 2), *crystal, abcd.FreeSpace(separation / 2),
             abcd.CurvedMirror(R=R, angle=theta, name="M2"),
             abcd.FreeSpace(ARM_HR, name="HR arm")],
            R1=np.inf, R2=np.inf, wavelength=TIS.laser_wavelength)

    return kerr.KerrLensModel(cavity, CRYSTAL_PATH, N, TIS.nonlinear_index,
                              TIS.laser_wavelength, brewster=True, slices=slices,
                              name="Ti:sapphire")


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    stab = {plane: np.array([model(s).cold_cavity().stability_parameter(plane)
                             for s in SEPARATIONS]) for plane in "ts"}
    stab0 = {plane: np.array([model(s, 0.0).cold_cavity().stability_parameter(plane)
                              for s in SEPARATIONS]) for plane in "ts"}
    stable = (np.abs(stab["t"]) < 1) & (np.abs(stab["s"]) < 1)
    seps = SEPARATIONS[stable][::3]
    hard = np.array([model(s).klm_strength(1, "t") for s in seps])
    soft = np.array([model(s).klm_strength("crystal", "t") for s in seps])

    # Operating point: inner edge of the second zone, where the soft aperture is strong
    zone1 = seps[seps < 103 * mm]
    zone2 = seps[seps > 103 * mm]
    op_sep = float(zone2[0] + 0.5 * mm)
    m = model(op_sep)
    p_cr = m.critical_power
    cold = m.cold_cavity()
    rep = modelocking.repetition_rate(cold.optical_length)
    e_intra = AVERAGE_OUTPUT / OUTPUT_COUPLING / rep
    peak = 0.88 * e_intra / PULSE_WIDTH
    w_x = m.spot_size(m.solve(0.0), "crystal", "t") * N  # physical tangential size
    w_y = m.spot_size(m.solve(0.0), "crystal", "s")
    spm = modelocking.spm_coefficient(TIS.nonlinear_index, CRYSTAL_PATH, np.pi * w_x * w_y,
                                      TIS.laser_wavelength)
    gdd = modelocking.soliton_required_gdd(PULSE_WIDTH, spm, e_intra)
    material_gdd = 2 * TIS.gvd * CRYSTAL_PATH
    p_axis = np.linspace(0, 0.3, 13)
    w_oc = m.spot_vs_power(p_axis, 1, "t")
    w_xtal = m.spot_vs_power(p_axis, "crystal", "t")

    summary = {
        "fold_angle_deg": float(np.degrees(THETA)),
        "critical_power_MW": p_cr / 1e6,
        "zone1_mm": f"{zone1.min() / mm:.1f}-{zone1.max() / mm:.1f}",
        "zone2_mm": f"{zone2.min() / mm:.1f}-{zone2.max() / mm:.1f}",
        "operating_separation_mm": op_sep / mm,
        "hard_aperture_strength": m.klm_strength(1, "t"),
        "soft_aperture_strength": m.klm_strength("crystal", "t"),
        "repetition_rate_MHz": rep / 1e6,
        "intracavity_energy_nJ": e_intra / nJ,
        "peak_power_over_Pcr": peak / p_cr,
        "crystal_mode_um": f"{w_x / um:.0f} x {w_y / um:.0f}",
        "soliton_gdd_fs2": gdd / fs**2,
        "crystal_gdd_fs2": material_gdd / fs**2,
        "prism_gdd_needed_fs2": (gdd - material_gdd) / fs**2,
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        for plane, ls in (("t", "-"), ("s", "--")):
            ax[0, 0].plot(SEPARATIONS / mm, stab[plane], ls, color="C0",
                          label=f"{plane}, compensated ({np.degrees(THETA):.1f} deg)")
            ax[0, 0].plot(SEPARATIONS / mm, stab0[plane], ls, color="C3", alpha=0.6,
                          label=f"{plane}, no fold angle")
        ax[0, 0].axhline(1, c="k", lw=0.6)
        ax[0, 0].axhline(-1, c="k", lw=0.6)
        ax[0, 0].set(xlabel="folding-mirror separation (air) [mm]", ylabel="m = (A+D)/2",
                     ylim=(-3, 3), title="Stability zones")
        ax[0, 0].legend(fontsize=7)
        # break the lines between the two stability zones
        gap = np.r_[False, np.diff(seps) > 2 * np.diff(SEPARATIONS)[0] * 3]
        x = np.insert(seps / mm, np.where(gap)[0], np.nan)
        ax[0, 1].plot(x, np.insert(hard, np.where(gap)[0], np.nan), "o-", ms=3,
                      label="hard aperture at OC")
        ax[0, 1].plot(x, np.insert(soft, np.where(gap)[0], np.nan), "s-", ms=3,
                      label="soft aperture in crystal")
        ax[0, 1].axhline(0, c="k", lw=0.6)
        ax[0, 1].axvline(op_sep / mm, c="0.5", ls=":")
        ax[0, 1].set(xlabel="separation [mm]", ylabel="delta = (1/w) dw/dp",
                     ylim=(-6, 6), title="KLM strength (tangential)")
        ax[0, 1].legend()
        ax[1, 0].plot(p_axis, w_oc / w_oc[0], label="at output coupler")
        ax[1, 0].plot(p_axis, w_xtal / w_xtal[0], "--", label="in crystal")
        ax[1, 0].set(xlabel="P / P_cr", ylabel="w(P) / w(0)",
                     title=f"Self-consistent Kerr lens at {op_sep / mm:.1f} mm")
        ax[1, 0].legend()
        prof_t = m.cold_cavity().mode_profile("t")
        prof_s = m.cold_cavity().mode_profile("s")
        ax[1, 1].semilogy(prof_t.z / mm, prof_t.w / um, label="tangential")
        ax[1, 1].semilogy(prof_s.z / mm, prof_s.w / um, "--", label="sagittal")
        ax[1, 1].set(xlabel="distance from output coupler [mm]", ylabel="w [um]",
                     title="Cold-cavity mode")
        ax[1, 1].legend()
        fig.tight_layout()
        fig.savefig(outdir / "klm_ti_sapphire.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:28s} {v:.4g}" if isinstance(v, float) else f"{k:28s} {v}")
