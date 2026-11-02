"""Smoke tests: every example runs and its headline numbers stay sensible."""

import importlib.util
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def load(name):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cw_example():
    s = load("cw_nd_yvo4").run(make_plots=False)
    assert 15 < s["output_W"] < 25
    assert -1 < s["stability_parameter"] < -0.3
    assert 1 <= s["m2_estimate"] < 3
    assert s["max_stable_pump_W"] > 30


def test_qswitch_example():
    s = load("qswitched_nd_yag").run(make_plots=False)
    assert 0.5 < s["energy_10kHz_mJ"] < 2
    assert 2 < s["width_10kHz_ns"] < 15
    assert s["damage_margin"] > 1
    assert 0.9 < s["avg_over_cw_at_100kHz"] <= 1.0


def test_modelocked_example():
    s = load("modelocked_nd_yvo4_sesam").run(make_plots=False)
    assert s["repetition_rate_MHz"] == pytest.approx(100, rel=0.01)
    assert s["qml_margin"] > 1
    assert 3 < s["sesam_saturation"] < 20
    assert s["transform_limit_ps"] < s["sesam_pulse_width_ps"] < s["am_pulse_width_ps"]


def test_koechner_example():
    s = load("koechner_side_pumped_rod").run(make_plots=False)
    assert s["f_radial_at_500W_mm"] < s["f_tangential_at_500W_mm"]
    assert s["extraction_r2"] == pytest.approx(0.797, abs=0.002)


@pytest.mark.parametrize("name", ["cw_nd_yvo4", "qswitched_nd_yag",
                                  "modelocked_nd_yvo4_sesam", "koechner_side_pumped_rod"])
def test_examples_make_plots(name, tmp_path):
    pytest.importorskip("matplotlib")
    load(name).run(make_plots=True, outdir=tmp_path)
    assert list(tmp_path.glob("*.png"))
