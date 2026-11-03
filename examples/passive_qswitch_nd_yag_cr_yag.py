"""Example 5: a passively Q-switched Nd:YAG / Cr:YAG laser.

A compact end-pumped Nd:YAG laser with a Cr4+:YAG saturable absorber, the
standard way to get ns pulses without a driver. Design questions:

* how pulse energy, width and peak power depend on the absorber's initial
  transmission ``T0`` (Degnan's theory, :mod:`laserdesign.passive_qswitch`);
* whether the absorber saturates fast enough for a clean giant pulse (the
  bleaching criterion, which depends on the mode-area ratio between gain and
  absorber);
* how the repetition rate grows with pump power while the pulse energy stays
  fixed;
* and a check of the analytic theory against the full rate equations.

Run ``python examples/passive_qswitch_nd_yag_cr_yag.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import EndPumpedLaser, abcd, passive_qswitch, pump
from laserdesign.materials import get_material
from laserdesign.units import mm, nm, ns, uJ, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

MATERIAL = get_material("Nd:YAG")
ABSORBER = passive_qswitch.CR_YAG
DOPING = 1.1               # at.%
LENGTH = 5 * mm
PUMP_POWER = 8.0           # W, 808 nm, 200 um / 0.22 NA fibre
PUMP = pump.PumpBeam(PUMP_POWER, waist=150 * um, wavelength=808 * nm, m2=60,
                     waist_position=1 * mm)
T0 = 0.85                  # Cr:YAG small-signal single-pass transmission
T_OC = 0.30
LOSS = 0.02
R_OC = 100 * mm


def cavity(f_thermal: float) -> abcd.StandingWaveCavity:
    """HR-coated Nd:YAG face, 3 mm gap, 2 mm Cr:YAG, 15 mm gap, curved output coupler."""
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YAG"),
         abcd.FreeSpace(3 * mm),
         abcd.Medium(2 * mm, n=1.82, name="Cr:YAG"),
         abcd.FreeSpace(15 * mm)],
        R1=np.inf, R2=R_OC, wavelength=MATERIAL.laser_wavelength)


def build() -> EndPumpedLaser:
    return EndPumpedLaser(material=MATERIAL, doping=DOPING, crystal_length=LENGTH,
                          pump_beam=PUMP, cavity=cavity, crystal_element="YAG thermal lens",
                          output_coupling=T_OC, passive_loss=LOSS)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    laser = build()
    res = laser.passively_q_switched(PUMP_POWER, T0, ABSORBER, absorber_location="Cr:YAG")
    pulse = res["pulse"]
    cw = res["operating_point"]

    t0s = np.linspace(0.6, 0.97, 38)
    sweep = [laser.passively_q_switched(PUMP_POWER, t, ABSORBER, "Cr:YAG") for t in t0s]
    pumps = np.linspace(1, 10, 37)
    vs_pump = [laser.passively_q_switched(p, T0, ABSORBER, "Cr:YAG") for p in pumps]

    # Rate-equation check (same areas and losses as the design method)
    cav = laser.resonator(PUMP_POWER)
    area = np.pi * (cw.laser_radius**2 + cw.pump_radius**2) / 2
    area_s = np.pi * res["absorber_radius"] ** 2 / 2
    sigma = MATERIAL.emission_cross_section
    common = dict(absorber=ABSORBER, initial_transmission=T0, gain_area=area,
                  absorber_area=area_s, gain_cross_section=sigma,
                  photon_energy=MATERIAL.laser_photon_energy, delta=laser.delta,
                  delta_oc=-np.log(1 - T_OC), round_trip_time=cav.round_trip_time)
    sim = passive_qswitch.simulate_passive_q_switch(**common)
    ana = passive_qswitch.passive_q_switch_pulse(**common)

    summary = {
        "cw_output_without_absorber_W": cw.output_power,
        "laser_radius_um": cw.laser_radius / um,
        "absorber_radius_um": res["absorber_radius"] / um,
        "alpha": pulse.alpha,
        "bleaching_criterion": pulse.bleaching_criterion,
        "threshold_with_absorber_W": res["threshold"],
        "energy_uJ": res["energy"] / uJ,
        "pulse_width_ns": res["pulse_width"] / ns,
        "peak_power_kW": res["peak_power"] / 1e3,
        "rep_rate_kHz": res["rep_rate"] / 1e3,
        "average_power_W": res["average_power"],
        "extraction_efficiency": pulse.extraction_efficiency,
        "absorber_recovered": float(res["absorber_recovered"]),
        "sim_over_analytic_energy": sim.energy / ana.energy,
        "sim_over_analytic_peak": sim.peak_power / ana.peak_power,
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        e = np.array([s["energy"] for s in sweep])
        ok = e > 0
        ax[0, 0].plot(t0s[ok], e[ok] / uJ, label="energy [uJ]")
        ax[0, 0].plot(t0s[ok], [s["peak_power"] / 1e3 for s, k in zip(sweep, ok) if k],
                      "--", label="peak power [kW]")
        ax[0, 0].set(xlabel="Cr:YAG initial transmission T0", title="Pulse vs absorber T0")
        ax[0, 0].legend()
        ax[0, 1].semilogy(t0s[ok], [s["pulse_width"] / ns for s, k in zip(sweep, ok) if k])
        ax[0, 1].set(xlabel="T0", ylabel="pulse width [ns]", title="Pulse width")
        ax2 = ax[0, 1].twinx()
        ax2.plot(t0s, [s["pulse"].bleaching_criterion for s in sweep], "C1:")
        ax2.axhline(1, color="C1", lw=0.6)
        ax2.set_ylabel("bleaching criterion (needs > 1)", color="C1")

        f = np.array([v["rep_rate"] for v in vs_pump])
        ax[1, 0].plot(pumps, [v["average_power"] for v in vs_pump], label="average power")
        ax[1, 0].plot(pumps, [v["operating_point"].output_power for v in vs_pump], ":",
                      label="CW output, no absorber")
        ax[1, 0].set(xlabel="pump power [W]", ylabel="power [W]",
                     title=f"T0 = {T0}: pump sets the rate")
        ax[1, 0].legend(loc="upper left")
        ax3 = ax[1, 0].twinx()
        ax3.plot(pumps, f / 1e3, "C2--")
        ax3.set_ylabel("repetition rate [kHz]", color="C2")

        t = (sim.t - sim.t[np.argmax(sim.output_power)]) / ns
        ax[1, 1].plot(t, sim.output_power / sim.peak_power, label="output power")
        ax[1, 1].plot(t, sim.inversion_ratio, "--", label="inversion N/N_i")
        ax[1, 1].plot(t, sim.ground_state_fraction, ":", label="Cr:YAG ground state")
        ax[1, 1].set(xlabel="time [ns]", ylabel="normalised", xlim=(-40, 15),
                     title="Rate-equation pulse")
        ax[1, 1].legend()
        fig.tight_layout()
        fig.savefig(outdir / "passive_qswitch_performance.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:32s} {v:.4g}")
