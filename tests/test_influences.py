"""Tests for the notes on what sets each Results row."""

import pytest

from laserdesign.gui.influences import PARAMETERS, influences, tooltip_html
from laserdesign.gui.presets import PRESETS
from laserdesign.gui.spec import DesignSpec
from laserdesign.web.report import results

SKIP = {"Design"}


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_result_row_has_a_note(name):
    spec = PRESETS[name]()
    out = results(spec)
    assert len(out["tips"]) == len(out["rows"])
    for (label, _), tip in zip(out["rows"], out["tips"]):
        if label in SKIP:
            assert tip is None
            continue
        assert tip is not None, f"{name}: no note for {label!r}"
        assert tip["summary"] and tip["inputs"]
        keys = [d["key"] for d in tip["inputs"]]
        assert len(keys) == len(set(keys))
        assert all(d["value"] != "?" for d in tip["inputs"]), (label, tip)


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_input_formats(name):
    spec = PRESETS[name]()
    for key, (_, _, get) in PARAMETERS.items():
        assert isinstance(get(spec), str), key


def test_note_follows_the_design():
    spec = DesignSpec(pump_power=12.3)
    tip = influences("Absorbed power", spec)
    names = {d["name"]: d["value"] for d in tip["inputs"]}
    assert names["Pump power"] == "12.3 W"
    assert "doping" in names["Pump absorption coefficient"]
    side = influences("Absorbed power", DesignSpec(pump_geometry="side"))
    assert [d["key"] for d in side["inputs"]] == ["pump_power", "absorption_efficiency"]
    # The repetition rate is an input for active Q-switching only.
    assert [d["key"] for d in influences("Repetition rate", DesignSpec(mode="qswitch"))
            ["inputs"]] == ["rep_rate"]
    passive = influences("Repetition rate", DesignSpec(mode="passive"))
    assert "pump_power" in [d["key"] for d in passive["inputs"]]
    # Ring resonators have no end mirrors.
    ring = influences("Stability parameter m", DesignSpec(cavity_type="ring"))
    assert "R1" not in [d["key"] for d in ring["inputs"]]


def test_inputs_are_ordered_by_step():
    tip = influences("CW output power", DesignSpec())
    steps = [d["step"] for d in tip["inputs"]]
    assert steps == sorted(steps)


def test_tooltip_html():
    text = tooltip_html("Heat load", DesignSpec())
    assert "<b>Heat load</b>" in text and "Heat fraction" in text
    assert tooltip_html("Design", DesignSpec()) == ""
