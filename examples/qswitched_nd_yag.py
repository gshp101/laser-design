"""Example 2: an acousto-optically Q-switched, end-pumped Nd:YAG laser.

A 20 W, 808 nm fibre-coupled diode (M^2 = 80) pumps an 8 mm, 1 at.% Nd:YAG
rod. The resonator holds a 25 mm fused-silica AO Q-switch and uses a convex
output coupler to compensate the strong Nd:YAG thermal lens. The example
answers the questions that drive a Q-switched design:

* how pulse energy, width and peak power vary with repetition rate,
* where the average power approaches the CW power,
* what the pulse looks like and how long it takes to build up, and
* how close the intracavity fluence comes to typical coating damage levels.

Nd:YAG is chosen over Nd:YVO4 because its 230 us lifetime stores more energy
at low repetition rates (compare the two in the Koechner example).

Run ``python examples/qswitched_nd_yag.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from laserdesign import EndPumpedLaser, abcd, gain, pump, qswitch
from laserdesign.materials import get_material
from laserdesign.units import kHz, mm, nm, um

OUT = Path(__file__).resolve().parent.parent / "docs" / "examples" / "images"

MATERIAL = get_material("Nd:YAG")
DOPING = 1.0
LENGTH = 8 * mm
PUMP_POWER = 20.0
PUMP = pump.PumpBeam(PUMP_POWER, waist=300 * um, wavelength=808 * nm, m2=80,
                     waist_position=2 * mm)
T_OC = 0.20
LOSS = 0.02                 # includes AOM insertion loss
R_OC = -200 * mm            # convex output coupler
COATING_DAMAGE = 10e4       # J/m^2 (10 J/cm^2 at ~10 ns), typical dielectric HR


def cavity(f_thermal: float) -> abcd.StandingWaveCavity:
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(LENGTH, MATERIAL.refractive_index, f_thermal,
                                         name="YAG"),
         abcd.FreeSpace(10 * mm),
         abcd.Medium(25 * mm, n=1.45, name="AO Q-switch"),
         abcd.FreeSpace(40 * mm)],
        R1=np.inf, R2=R_OC, wavelength=MATERIAL.laser_wavelength)


def build() -> EndPumpedLaser:
    return EndPumpedLaser(material=MATERIAL, doping=DOPING, crystal_length=LENGTH,
                          pump_beam=PUMP, cavity=cavity, crystal_element="YAG thermal lens",
                          output_coupling=T_OC, passive_loss=LOSS)


def run(make_plots: bool = True, outdir: Path = OUT) -> dict:
    laser = build()
    cw = laser.analyze(PUMP_POWER)
    cav = laser.resonator(PUMP_POWER)
    rates = np.geomspace(1 * kHz, 200 * kHz, 30)
    results = [laser.q_switched(PUMP_POWER, f) for f in rates]
    energy = np.array([r["energy"] for r in results])
    width = np.array([r["pulse_width"] for r in results])
    peak = np.array([r["peak_power"] for r in results])
    avg = np.array([r["average_power"] for r in results])

    f_demo = 10 * kHz
    demo = laser.q_switched(PUMP_POWER, f_demo)
    area = np.pi * (cw.laser_radius**2 + cw.pump_radius**2) / 2
    sim = qswitch.simulate_q_switch(
        demo["initial_ratio"], area, MATERIAL.emission_cross_section,
        MATERIAL.laser_photon_energy, laser.delta, gain.output_coupling_loss(T_OC),
        cav.round_trip_time)
    sim_scale = demo["overlap_efficiency"]

    # Peak fluence on the HR (mirror 1): circulating energy ~ E_out / T, Gaussian peak
    w_hr = cav.spot_size_on_mirror(1)
    fluence = 2 * demo["energy"] / T_OC / (np.pi * w_hr**2)

    summary = {
        "cw_output_W": cw.output_power,
        "cw_m2_estimate": cw.m2_estimate,
        "round_trip_time_ns": cav.round_trip_time * 1e9,
        "energy_10kHz_mJ": demo["energy"] * 1e3,
        "width_10kHz_ns": demo["pulse_width"] * 1e9,
        "peak_10kHz_kW": demo["peak_power"] / 1e3,
        "avg_10kHz_W": demo["average_power"],
        "simulated_fwhm_10kHz_ns": sim.fwhm * 1e9,
        "buildup_10kHz_ns": sim.buildup_time * 1e9,
        "hr_peak_fluence_J_cm2": fluence / 1e4,
        "damage_margin": COATING_DAMAGE / fluence,
        "avg_over_cw_at_100kHz": float(np.interp(100e3, rates, avg) / cw.output_power),
    }

    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        outdir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(2, 2, figsize=(10, 7))
        ax[0, 0].semilogx(rates / 1e3, energy * 1e3)
        ax[0, 0].set(xlabel="repetition rate [kHz]", ylabel="energy [mJ]", title="Pulse energy")
        ax[0, 1].semilogx(rates / 1e3, width * 1e9)
        ax[0, 1].set(xlabel="repetition rate [kHz]", ylabel="E / P_peak [ns]", title="Pulse width")
        ax[1, 0].loglog(rates / 1e3, peak / 1e3)
        ax[1, 0].set(xlabel="repetition rate [kHz]", ylabel="peak power [kW]", title="Peak power")
        ax[1, 1].semilogx(rates / 1e3, avg, label="Q-switched")
        ax[1, 1].axhline(cw.output_power, ls="--", c="k", label="CW")
        ax[1, 1].set(xlabel="repetition rate [kHz]", ylabel="average power [W]",
                     title="Average power")
        ax[1, 1].legend()
        fig.tight_layout()
        fig.savefig(outdir / "qs_nd_yag_vs_rate.png", dpi=110)
        plt.close(fig)

        fig, a1 = plt.subplots(figsize=(6, 3.5))
        t0 = sim.buildup_time
        a1.plot((sim.t - t0) * 1e9, sim.output_power * sim_scale / 1e3, label="output power")
        a1.set(xlabel="time from peak [ns]", ylabel="power [kW]",
               title=f"Pulse at {f_demo / 1e3:.0f} kHz (build-up {sim.buildup_time * 1e9:.0f} ns)")
        a2 = a1.twinx()
        a2.plot((sim.t - t0) * 1e9, sim.inversion_ratio, "C1--", label="N / N_th")
        a2.set_ylabel("N / N_th")
        fig.tight_layout()
        fig.savefig(outdir / "qs_nd_yag_pulse.png", dpi=110)
        plt.close(fig)

    return summary


if __name__ == "__main__":
    for k, v in run().items():
        print(f"{k:28s} {v:.4g}")
