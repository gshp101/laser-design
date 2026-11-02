"""Tests for the Qt-free design spec and presets used by the GUI."""

import math
import sys
from pathlib import Path

import pytest

from laserdesign.gui import presets
from laserdesign.gui.spec import DesignSpec, build_laser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))


def test_default_spec_builds_and_is_stable():
    laser = build_laser(DesignSpec())
    assert laser.analyze(20.0).stable


@pytest.mark.parametrize("factory", list(presets.PRESETS.values()))
def test_json_round_trip(factory, tmp_path):
    spec = factory()
    path = tmp_path / "design.json"
    spec.save(path)
    again = DesignSpec.load(path)
    assert again == spec
    assert '"inf"' in path.read_text() or all(math.isfinite(x) for x in (spec.R1, spec.R2))


def test_presets_match_examples():
    import cw_nd_yvo4
    import modelocked_nd_yvo4_sesam
    import qswitched_nd_yag

    a = build_laser(presets.cw_nd_yvo4()).analyze(30.0).output_power
    b = cw_nd_yvo4.build().analyze(30.0).output_power
    assert a == pytest.approx(b, rel=1e-3)
    qa = build_laser(presets.qswitched_nd_yag()).q_switched(20.0, 10e3)["energy"]
    qb = qswitched_nd_yag.build().q_switched(20.0, 10e3)["energy"]
    assert qa == pytest.approx(qb, rel=1e-3)
    ma = build_laser(presets.modelocked_nd_yvo4()).sesam_mode_locked(12.0, 0.6, 0.01)
    mb = modelocked_nd_yvo4_sesam.build().sesam_mode_locked(12.0, 0.6, 0.01)
    assert ma["check"].qml_margin == pytest.approx(mb["check"].qml_margin, rel=1e-3)


def test_validation_messages():
    spec = DesignSpec(elements=[{"type": "space", "length": 0.1}], output_coupling=1.5)
    problems = spec.validate()
    assert any("crystal" in p for p in problems)
    assert any("Output coupling" in p for p in problems)
    with pytest.raises(ValueError):
        build_laser(spec)


def test_material_overrides_apply():
    spec = DesignSpec(material="nd:yag", material_overrides={"thermal_conductivity": 10.0})
    assert spec.gain_medium().thermal_conductivity == 10.0
    assert build_laser(spec).material.thermal_conductivity == 10.0
