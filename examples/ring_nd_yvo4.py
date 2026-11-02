"""Example 8: a unidirectional bow-tie ring Nd:YVO4 laser.

Ring lasers with an optical diode (Faraday rotator plus wave plate) run in a
single direction, so there is no standing wave and no spatial hole burning:
the usual route to single-frequency output. The price is one gain pass per
round trip instead of two, which doubles the threshold inversion. This
example

* designs a bow-tie ring (two R = 300 mm curved mirrors around the crystal,
  two flat folds) whose mode in the crystal barely changes with the strong
  Nd:YVO4 thermal lens;
* compares it with a plano-concave standing-wave laser with the same crystal,
  pump and mode size (threshold, slope and output);
* shows the ring's longitudinal mode spacing ``c / L``;
* and checks the same ring SESAM mode-locked, with the SESAM replacing the
  flat fold M3: the repetition rate is ``c / L`` and the Q-switched
  mode-locking threshold uses a single gain pass, which makes it higher than
  in a linear laser. With the large mode on M3 the margin is below 1, and the
  example reports the SESAM spot that a focusing mirror pair would need.

Run ``python examples/ring_nd_yvo4.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import EndPumpedLaser, abcd, pump
from laserdesign.materials import get_material
from laserdesign.units import MHz, mm, nm, nJ, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

MATERIAL = get_material("Nd:YVO4")
DOPING = 0.3
LENGTH = 10 * mm
PUMP_POWER = 12.0
PUMP = pump.PumpBeam(PUMP_POWER, waist=200 * um, wavelength=808 * nm, m2=20,
                     waist_position=2 * mm)
R = 300 * mm
SHORT = 200 * mm           # curved mirror to crystal face, each side
LONG = 600 * mm            # M1 -> M2 -> M3 -> M4 path
FOLD = np.radians(6)       # angle of incidence on all four mirrors
T_OC = 0.05                # output through M2
RING_LOSS = 0.03           # Faraday rotator, wave plate, four mirrors
LINEAR_LOSS = 0.01


def ring(f_thermal: float) -> abcd.RingCavity:
    """Bow-tie: crystal, M1 (curved), M2 (flat, output), M3 (flat), M4 (curved)."""
    return abcd.RingCavity(
        [abcd.FreeSpace(SHORT),
         *abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(SHORT),
         abcd.CurvedMirror(R=R, angle=FOLD, name="M1"), abcd.FreeSpace(LONG / 3),
         abcd.FlatMirror(angle=FOLD, name="M2"), abcd.FreeSpace(LONG / 3),
         abcd.FlatMirror(angle=FOLD, name="M3"), abcd.FreeSpace(LONG / 3),
         abcd.CurvedMirror(R=R, angle=FOLD, name="M4")],
        wavelength=MATERIAL.laser_wavelength)


def linear(f_thermal: float, gap: float = 60 * mm, r_oc: float = 200 * mm):
    """HR on the crystal face, gap, curved output coupler."""
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(gap)], R1=np.inf, R2=r_oc, wavelength=MATERIAL.laser_wavelength)


def build(cavity, loss: float) -> EndPumpedLaser:
    return EndPumpedLaser(material=MATERIAL, doping=DOPING, crystal_length=LENGTH,
                          pump_beam=PUMP, cavity=cavity, crystal_element="YVO4 thermal lens",
                          output_coupling=T_OC, passive_loss=loss)


def matched_linear_gap(target: float) -> float:
    """Gap of the linear laser whose mode at full pump matches ``target``."""
    las = build(linear, LINEAR_LOSS)
    f = las.thermal_focal_length(PUMP_POWER)
    best, err = None, np.inf
    for gap in np.linspace(5 * mm, 200 * mm, 391):
        cav = linear(f, gap)
        if cav.is_stable():
            e = abs(cav.spot_size_at("YVO4 thermal lens") - target)
            if e < err:
                best, err = gap, e
    return float(best)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    ring_laser = build(ring, RING_LOSS)
    op_r = ring_laser.analyze(PUMP_POWER)
    gap = matched_linear_gap(op_r.laser_radius)
    lin_laser = build(lambda f: linear(f, gap), LINEAR_LOSS)
    lin_same_loss = build(lambda f: linear(f, gap), RING_LOSS)
    op_l = lin_laser.analyze(PUMP_POWER)
    powers = np.linspace(0.5, 14, 28)
    ring_ops = ring_laser.scan(powers)
    lin_ops = lin_laser.scan(powers)
    cav = ring_laser.resonator(PUMP_POWER)
    ml = ring_laser.sesam_mode_locked(PUMP_POWER, 0.6, 0.01, absorber_mirror="M3")
    chk = ml["check"]

    summary = {
        "ring_length_mm": cav.optical_length / mm,
        "ring_fsr_MHz": cav.free_spectral_range / MHz,
        "thermal_focal_length_mm": op_r.thermal_focal_length / mm,
        "ring_mode_um": op_r.laser_radius / um,
        "ring_mode_at_2W_um": ring_laser.analyze(2.0).laser_radius / um,
        "pump_radius_um": op_r.pump_radius / um,
        "ring_threshold_W": op_r.threshold,
        "ring_output_W": op_r.output_power,
        "linear_gap_mm": gap / mm,
        "linear_mode_um": op_l.laser_radius / um,
        "linear_threshold_W": op_l.threshold,
        "linear_same_loss_threshold_W": lin_same_loss.analyze(PUMP_POWER).threshold,
        "linear_output_W": op_l.output_power,
        "linear_fsr_MHz": lin_laser.resonator(PUMP_POWER).free_spectral_range / MHz,
        "ml_repetition_rate_MHz": chk.repetition_rate / MHz,
        "ml_pulse_energy_nJ": chk.pulse_energy / nJ,
        "ml_qml_margin": chk.qml_margin,
        "ml_sesam_saturation": chk.absorber_saturation,
        "ml_sesam_radius_um": ml["absorber_radius"] / um,
        # E_c scales with w_A and E_p is fixed, so the margin scales as 1 / w_A
        "sesam_radius_for_margin_2_um": ml["absorber_radius"] * chk.qml_margin / 2 / um,
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        for ops, label in ((ring_ops, "ring (1 gain pass)"), (lin_ops, "linear (2 passes)")):
            st = [o for o in ops if o.stable]
            ax[0, 0].plot([o.pump_power for o in st], [o.output_power for o in st], label=label)
        ax[0, 0].set(xlabel="pump power [W]", ylabel="output [W]", title="CW output")
        ax[0, 0].legend()
        for ops, label in ((ring_ops, "ring"), (lin_ops, "linear")):
            st = [o for o in ops if o.stable]
            ax[0, 1].plot([o.pump_power for o in st], [o.laser_radius / um for o in st],
                          label=label)
        ax[0, 1].plot(powers, [o.pump_radius / um for o in ring_ops], "k:", label="pump")
        ax[0, 1].set(xlabel="pump power [W]", ylabel="radius in crystal [um]",
                     title="Mode size vs thermal lens")
        ax[0, 1].legend()
        for plane, ls in (("t", "-"), ("s", "--")):
            prof = cav.mode_profile(plane)
            ax[1, 0].plot(prof.z / mm, prof.w / um, ls, label=plane)
        for s, el in zip(cav.mode_profile().element_starts, cav.elements):
            if el.name in ("M1", "M2", "M3", "M4"):
                ax[1, 0].axvline(s / mm, c="0.7", lw=0.6)
                ax[1, 0].text(s / mm, ax[1, 0].get_ylim()[1] * 0.95, el.name, fontsize=7)
        ax[1, 0].set(xlabel="position around the ring [mm]", ylabel="w [um]",
                     title=f"Ring mode at {PUMP_POWER:.0f} W")
        ax[1, 0].legend()
        nu = np.arange(-3, 4)
        ax[1, 1].stem(nu * cav.free_spectral_range / MHz, np.ones_like(nu), basefmt=" ",
                      label=f"ring, c/L = {cav.free_spectral_range / MHz:.0f} MHz")
        fl = lin_laser.resonator(PUMP_POWER).free_spectral_range
        ax[1, 1].stem(nu * fl / MHz, 0.6 * np.ones_like(nu), linefmt="C1-", markerfmt="C1o",
                      basefmt=" ", label=f"linear, c/2L = {fl / MHz:.0f} MHz")
        ax[1, 1].set(xlabel="frequency offset [MHz]", yticks=[],
                     title="Longitudinal modes")
        ax[1, 1].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / "ring_nd_yvo4.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:30s} {v:.4g}")
