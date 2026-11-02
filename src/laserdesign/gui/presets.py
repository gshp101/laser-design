"""Ready-made designs matching the scripts in ``examples/``.

Each function returns a fresh :class:`~laserdesign.gui.spec.DesignSpec`, so
the GUI can load it and the user can modify it without affecting the preset.
"""

from __future__ import annotations

import math

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


#: Presets by display name.
PRESETS = {
    "CW Nd:YVO4 (30 W pump)": cw_nd_yvo4,
    "Q-switched Nd:YAG (20 W pump)": qswitched_nd_yag,
    "SESAM mode-locked Nd:YVO4 (100 MHz)": modelocked_nd_yvo4,
}
