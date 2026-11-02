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


def test_passive_qswitch_example():
    s = load("passive_qswitch_nd_yag_cr_yag").run(make_plots=False)
    assert s["bleaching_criterion"] > 1
    assert 10 < s["energy_uJ"] < 200
    assert 1 < s["pulse_width_ns"] < 20
    assert s["average_power_W"] < s["cw_output_without_absorber_W"]
    assert s["sim_over_analytic_energy"] == pytest.approx(1, abs=0.02)
    assert s["sim_over_analytic_peak"] == pytest.approx(1, abs=0.03)


def test_klm_example():
    s = load("klm_ti_sapphire").run(make_plots=False)
    assert 5 < s["fold_angle_deg"] < 10
    assert s["hard_aperture_strength"] < 0 and s["soft_aperture_strength"] < 0
    assert s["repetition_rate_MHz"] == pytest.approx(99, rel=0.03)
    assert s["soliton_gdd_fs2"] < 0 and s["prism_gdd_needed_fs2"] < s["soliton_gdd_fs2"]


def test_side_pumped_example():
    s = load("side_pumped_nd_yag").run(make_plots=False)
    assert s["f_radial_mm"] < s["f_average_mm"] < s["f_tangential_mm"]
    assert s["multimode_output_W"] > 5 * s["tem00_output_W"]
    assert s["multimode_m2"] > 5
    assert s["passive_rep_rate_Hz"] > 0 and s["active_1kHz_energy_mJ"] > 0


def test_ring_example():
    s = load("ring_nd_yvo4").run(make_plots=False)
    assert s["ring_threshold_W"] == pytest.approx(2 * s["linear_same_loss_threshold_W"],
                                                  rel=0.02)
    assert abs(s["ring_mode_um"] - s["ring_mode_at_2W_um"]) < 5
    assert s["ml_repetition_rate_MHz"] == pytest.approx(s["ring_fsr_MHz"])


@pytest.mark.parametrize("name", ["cw_nd_yvo4", "qswitched_nd_yag",
                                  "modelocked_nd_yvo4_sesam", "koechner_side_pumped_rod",
                                  "passive_qswitch_nd_yag_cr_yag", "klm_ti_sapphire",
                                  "side_pumped_nd_yag", "ring_nd_yvo4"])
def test_examples_make_plots(name, tmp_path):
    pytest.importorskip("matplotlib")
    load(name).run(make_plots=True, outdir=tmp_path)
    assert list(tmp_path.glob("*.png"))
