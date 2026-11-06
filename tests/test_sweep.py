"""Tests for plotting a Results quantity against one of its inputs."""

import copy
import json
import math
import re

import numpy as np
import pytest

from laserdesign.gui.presets import PRESETS
from laserdesign.gui.spec import DesignSpec
from laserdesign.gui.sweep import evaluate, quantity, sweep, sweep_inputs
from laserdesign.web import api
from laserdesign.web.report import results, sweep_plot

#: Rows that are inputs or text, not numbers to plot.
NOT_NUMERIC = {"Design", "Pump power", "Resonator type", "Absorber"}


def _first_number(text: str) -> tuple[float, int]:
    m = re.search(r"[-+]?\d+(?:\.(\d+))?(?:e[-+]?\d+)?", text)
    return float(m.group(0)), len(m.group(1) or "")


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_numeric_row_can_be_plotted(name):
    spec = PRESETS[name]()
    out = results(spec)
    assert len(out["sweeps"]) == len(out["rows"])
    for (label, text), inputs in zip(out["rows"], out["sweeps"]):
        if label in NOT_NUMERIC or (spec.mode == "qswitch" and label == "Repetition rate"):
            assert quantity(label, spec) is None, label
            assert inputs == []
            continue
        assert inputs, f"{name}: {label!r} cannot be plotted"
        assert all(i["lo"] < i["hi"] for i in inputs), (label, inputs)
        # The plotted number is the one in the table.
        value, decimals = _first_number(text)
        y = evaluate(label, spec)[0]
        assert abs(y - value) <= 0.02 * abs(y) + 0.51 * 10 ** -decimals, (label, text, y)


@pytest.mark.parametrize("name", list(PRESETS))
def test_inputs_are_from_the_hover_note(name):
    spec = PRESETS[name]()
    out = results(spec)
    for tip, inputs in zip(out["tips"], out["sweeps"]):
        if not inputs:
            continue
        noted = {d["key"] for d in tip["inputs"]}
        for i in inputs:
            assert i["key"].split(":")[0] in noted
            assert i["step"] and i["name"]
            lo, hi = i["min"], i["max"]
            assert lo is None or i["lo"] >= lo - 1e-12
            assert hi is None or i["hi"] <= hi + 1e-12


def test_cw_output_rises_with_pump_power():
    spec = DesignSpec()
    d = sweep("CW output power", "pump_power", spec, 1, 30, points=12)
    assert d["xlabel"] == "Pump power [W]"
    assert d["x"][0] == pytest.approx(1) and d["x"][-1] == pytest.approx(30)
    y = np.array(d["series"][0]["y"])
    assert np.all(np.diff(y[np.isfinite(y)]) > 0)
    assert d["current"] == pytest.approx(spec.pump_power)
    assert d["current_y"][0] == pytest.approx(evaluate("CW output power", spec)[0])


def test_sweep_leaves_the_design_alone():
    spec = PRESETS["Kerr-lens mode-locked Ti:sapphire"]()
    before = copy.deepcopy(spec.to_dict())
    for inp in sweep_inputs("CW output power", spec):
        sweep("CW output power", inp.key, spec, points=3)
    assert spec.to_dict() == before


def test_air_gaps_and_material_properties_are_inputs():
    spec = DesignSpec()
    keys = [i.key for i in sweep_inputs("Paraxial stability (A+D)/2", spec)]
    assert "elements:1" in keys  # the air gap
    assert "R2" in keys and "R1" not in keys  # mirror 1 is flat
    assert "thermal_conductivity" in keys
    d = sweep("CW output power", "elements:1", spec, 10, 300, points=30, refine=False)
    assert d["xlabel"] == "Air gap [mm]"
    # A long gap with a 200 mm mirror goes unstable: those points have no result.
    assert 0 < d["unstable"] < 30 and d["refined"] is None
    # When most of the range has no result, the part that has one is resolved.
    d = sweep("CW output power", "elements:1", spec, 10, 2000, points=20)
    assert d["refined"] is not None and len(d["x"]) > 20
    assert d["x"] == sorted(d["x"]) and d["lo"] == 10 and d["hi"] == 2000
    d = sweep("Thermal focal length", "thermal_conductivity", spec, points=5)
    y = [v for v in d["series"][0]["y"] if math.isfinite(v)]
    assert len(y) >= 2 and y[-1] > y[0]  # better heat conduction, weaker thermal lens


def test_two_series_rows_and_log_axis():
    spec = DesignSpec(mode="qswitch")
    d = sweep("Pulse energy", "rep_rate", spec)
    assert d["xlog"] and d["x"][0] < d["x"][-1]
    d = sweep("Laser / pump radius in crystal", "pump_waist", spec, 200, 400, points=4)
    assert [s["label"] for s in d["series"]] == ["laser", "pump"]
    assert d["series"][1]["y"][-1] > d["series"][1]["y"][0]


def test_bad_requests():
    spec = DesignSpec()
    with pytest.raises(KeyError):
        sweep("CW output power", "rep_rate", spec)
    with pytest.raises(KeyError):
        sweep("Design", "pump_power", spec)
    with pytest.raises(ValueError):
        sweep("CW output power", "pump_power", spec, 5, 5)


def test_web_plot_and_api():
    spec = DesignSpec()
    p = sweep_plot(spec, "M² estimate", "pump_power", 2, 20, 6)
    assert [s["label"] for s in p["series"][:3]] == ["combined", "thermal aberration",
                                                    "pump/mode ratio"]
    assert p["vlines"][0]["x"] == pytest.approx(spec.pump_power)
    out = json.loads(api.sweep(json.dumps(spec.to_dict()),
                               json.dumps({"label": "CW threshold", "key": "output_coupling",
                                           "lo": 2, "hi": 30, "points": 5})))
    assert out["xlabel"] == "Output coupler transmission [%]"
    assert len(out["series"][0]["x"]) == 5
    err = json.loads(api.sweep(json.dumps(spec.to_dict()),
                               json.dumps({"label": "CW threshold", "key": "nope"})))
    assert "error" in err
    assert math.isfinite(out["series"][0]["y"][0])


def test_paraxial_stability_is_defined_when_unstable():
    spec = DesignSpec()
    d = sweep("Paraxial stability (A+D)/2", "elements:1", spec, 10, 2000, points=20)
    assert d["unstable"] == 0 and d["refined"] is None and d["band"] == (-1.0, 1.0)
    assert [s["label"] for s in d["series"]] == ["t", "s"]
    m = d["series"][0]["y"]
    assert min(m) < -1 < max(m)  # crosses out of the stable range, and is still plotted
    # A tilted fold mirror separates the planes.
    spec = DesignSpec(elements=[{"type": "crystal"}, {"type": "space", "length": 0.05},
                                {"type": "mirror", "R": 0.1, "angle_deg": 0.0},
                                {"type": "space", "length": 0.05}])
    keys = [i.key for i in sweep_inputs("Paraxial stability (A+D)/2", spec)]
    assert "elements:2" in keys and "elements:2:angle_deg" in keys
    d = sweep("Paraxial stability (A+D)/2", "elements:2:angle_deg", spec, 0, 20, points=5)
    assert d["xlabel"] == "Fold mirror angle [°]"
    t, s = (np.array(x["y"]) for x in d["series"])
    assert t[0] == pytest.approx(s[0]) and abs(t[-1] - s[-1]) > 1e-3


def test_unstable_design_still_reports_paraxial_stability():
    spec = DesignSpec(elements=[{"type": "crystal"}, {"type": "space", "length": 2.0}])
    out = results(spec)
    rows = dict(out["rows"])
    assert rows["Paraxial stability (A+D)/2"].endswith("unstable")
    assert "CW output power" not in rows
    i = [k for k, _ in out["rows"]].index("Paraxial stability (A+D)/2")
    assert out["tips"][i] and out["sweeps"][i]
    assert any("unstable" in n["text"] for n in out["notes"])
    assert evaluate("Paraxial stability (A+D)/2", spec)[0] > 1
    assert math.isfinite(evaluate("Thermal focal length", spec)[0])
    assert math.isnan(evaluate("CW threshold", spec)[0])
