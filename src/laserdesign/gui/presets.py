"""Ready-made designs matching the scripts in ``examples/``.

Each function returns a fresh :class:`~laserdesign.gui.spec.DesignSpec`, so
the GUI can load it and the user can modify it without affecting the preset.
"""

from __future__ import annotations

import math

import numpy as np

from .. import abcd
from .spec import DesignSpec


def cw_nd_yvo4() -> DesignSpec:
    """30 W end-pumped CW Nd:YVO4 (examples/cw_nd_yvo4.py)."""
    return DesignSpec(
        name="CW Nd:YVO4, 30 W pump", material="nd:yvo4", doping=0.27, crystal_length=10e-3,
        pump_power=30.0, pump_waist=250e-6, pump_m2=170, pump_waist_position=2e-3,
        R1=math.inf, R2=0.5,
        elements=[{"type": "crystal"}, {"type": "space", "length": 0.045}],
        output_coupling=0.20, passive_loss=0.01, mode="cw")


def qswitched_nd_yag() -> DesignSpec:
    """AO Q-switched end-pumped Nd:YAG (examples/qswitched_nd_yag.py)."""
    return DesignSpec(
        name="Q-switched Nd:YAG, 20 W pump", material="nd:yag", doping=1.0, crystal_length=8e-3,
        pump_power=20.0, pump_waist=300e-6, pump_m2=80, pump_waist_position=2e-3,
        R1=math.inf, R2=-0.2,
        elements=[{"type": "crystal"}, {"type": "space", "length": 0.010},
                  {"type": "medium", "length": 0.025, "n": 1.45, "name": "AO Q-switch"},
                  {"type": "space", "length": 0.040}],
        output_coupling=0.20, passive_loss=0.02, mode="qswitch", rep_rate=10e3)


def modelocked_nd_yvo4() -> DesignSpec:
    """100 MHz SESAM mode-locked Nd:YVO4 (examples/modelocked_nd_yvo4_sesam.py)."""
    n = 2.165
    long_arm = 1.5 - 0.35 - 4e-3 * n
    return DesignSpec(
        name="SESAM mode-locked Nd:YVO4, 100 MHz", material="nd:yvo4", doping=0.5,
        crystal_length=4e-3, pump_power=12.0, pump_waist=150e-6, pump_m2=30,
        pump_waist_position=1e-3, R1=math.inf, R2=math.inf,
        elements=[{"type": "crystal"}, {"type": "space", "length": 0.35},
                  {"type": "mirror", "R": 0.5, "angle_deg": 5.0, "name": "fold mirror"},
                  {"type": "space", "length": long_arm / 2},
                  {"type": "mirror", "R": math.inf, "angle_deg": 0.0,
                   "name": "output coupler (fold)"},
                  {"type": "space", "length": long_arm / 2}],
        output_coupling=0.05, passive_loss=0.02, mode="modelock",
        sesam_saturation_fluence=0.6, sesam_modulation_depth=0.01)


def passive_nd_yag_cr_yag() -> DesignSpec:
    """Cr:YAG passively Q-switched Nd:YAG (examples/passive_qswitch_nd_yag_cr_yag.py)."""
    return DesignSpec(
        name="Passively Q-switched Nd:YAG / Cr:YAG", material="nd:yag", doping=1.1,
        crystal_length=5e-3, pump_power=8.0, pump_waist=150e-6, pump_m2=60,
        pump_waist_position=1e-3, R1=math.inf, R2=0.1,
        elements=[{"type": "crystal"}, {"type": "space", "length": 0.003},
                  {"type": "medium", "length": 0.002, "n": 1.82, "name": "Cr:YAG"},
                  {"type": "space", "length": 0.015}],
        output_coupling=0.30, passive_loss=0.02, mode="passive", absorber="cr:yag",
        absorber_transmission=0.85, absorber_location="Cr:YAG")


def klm_ti_sapphire() -> DesignSpec:
    """Kerr-lens mode-locked Ti:sapphire X-cavity (after examples/klm_ti_sapphire.py).

    Adds a 4 W, 532 nm pump focused to 30 um, which the example leaves out.
    """
    n = 1.76
    theta = float(np.degrees(abcd.astigmatism_compensation_angle(
        0.1, 4e-3 * n / np.sqrt(n**2 + 1), n)))
    sep = 0.1035
    return DesignSpec(
        name="KLM Ti:sapphire X-cavity", material="ti:sapphire", doping=0.25,
        crystal_length=4e-3, crystal_brewster=True, pump_power=4.0, pump_waist=30e-6,
        pump_m2=1.2, pump_waist_position=2e-3, R1=math.inf, R2=math.inf,
        elements=[{"type": "space", "length": 0.8, "name": "OC arm"},
                  {"type": "mirror", "R": 0.1, "angle_deg": theta, "name": "M1"},
                  {"type": "space", "length": sep / 2}, {"type": "crystal"},
                  {"type": "space", "length": sep / 2},
                  {"type": "mirror", "R": 0.1, "angle_deg": theta, "name": "M2"},
                  {"type": "space", "length": 0.6, "name": "HR arm"}],
        output_coupling=0.05, passive_loss=0.01, mode="klm", klm_aperture="mirror1",
        klm_slices=6, klm_pulse_width=15e-15)


def side_pumped_nd_yag() -> DesignSpec:
    """Diode side-pumped multimode Nd:YAG rod (examples/side_pumped_nd_yag.py)."""
    return DesignSpec(
        name="Side-pumped Nd:YAG rod, 400 W diodes", material="nd:yag", doping=1.0,
        crystal_length=0.065, pump_geometry="side", pump_power=400.0, rod_radius=2e-3,
        absorption_efficiency=0.7, rod_thermal_lens="average", multimode_fill=0.8,
        R1=math.inf, R2=math.inf,
        elements=[{"type": "space", "length": 0.3, "name": "HR arm"}, {"type": "crystal"},
                  {"type": "space", "length": 0.3, "name": "OC arm"}],
        output_coupling=0.20, passive_loss=0.04, mode="qswitch", rep_rate=1e3)


def ring_nd_yvo4() -> DesignSpec:
    """Unidirectional bow-tie ring Nd:YVO4 (examples/ring_nd_yvo4.py)."""
    fold = 6.0
    return DesignSpec(
        name="Ring Nd:YVO4 (bow-tie)", material="nd:yvo4", doping=0.3, crystal_length=10e-3,
        pump_power=12.0, pump_waist=200e-6, pump_m2=20, pump_waist_position=2e-3,
        cavity_type="ring",
        elements=[{"type": "space", "length": 0.2}, {"type": "crystal"},
                  {"type": "space", "length": 0.2},
                  {"type": "mirror", "R": 0.3, "angle_deg": fold, "name": "M1"},
                  {"type": "space", "length": 0.2},
                  {"type": "mirror", "R": math.inf, "angle_deg": fold, "name": "M2"},
                  {"type": "space", "length": 0.2},
                  {"type": "mirror", "R": math.inf, "angle_deg": fold, "name": "M3"},
                  {"type": "space", "length": 0.2},
                  {"type": "mirror", "R": 0.3, "angle_deg": fold, "name": "M4"}],
        output_coupling=0.05, passive_loss=0.03, mode="cw", sesam_location="M3",
        absorber_location="M3", klm_aperture="M2")


#: Presets by display name.
PRESETS = {
    "CW Nd:YVO4 (30 W pump)": cw_nd_yvo4,
    "Q-switched Nd:YAG (20 W pump)": qswitched_nd_yag,
    "SESAM mode-locked Nd:YVO4 (100 MHz)": modelocked_nd_yvo4,
    "Passively Q-switched Nd:YAG / Cr:YAG": passive_nd_yag_cr_yag,
    "Kerr-lens mode-locked Ti:sapphire": klm_ti_sapphire,
    "Side-pumped Nd:YAG rod (Q-switched, 400 W)": side_pumped_nd_yag,
    "Ring Nd:YVO4 (unidirectional bow-tie)": ring_nd_yvo4,
}
