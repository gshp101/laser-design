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


def test_new_presets_match_examples():
    import passive_qswitch_nd_yag_cr_yag as e5
    import ring_nd_yvo4 as e8
    import side_pumped_nd_yag as e7

    a = build_laser(presets.passive_nd_yag_cr_yag()).passively_q_switched(8.0, 0.85, "cr:yag",
                                                                          "Cr:YAG")
    b = e5.build().passively_q_switched(8.0, 0.85, "cr:yag", "Cr:YAG")
    assert a["energy"] == pytest.approx(b["energy"], rel=1e-3)
    side = build_laser(presets.side_pumped_nd_yag())
    assert side.analyze(400.0).output_power == pytest.approx(
        e7.build(0.8).analyze(400.0).output_power, rel=1e-3)
    ring = build_laser(presets.ring_nd_yvo4())
    assert ring.analyze(12.0).gain_passes == 1
    assert ring.analyze(12.0).output_power == pytest.approx(
        e8.build(e8.ring, e8.RING_LOSS).analyze(12.0).output_power, rel=1e-3)


def test_klm_preset_kerr_model():
    from laserdesign.gui.spec import kerr_model

    spec = presets.klm_ti_sapphire()
    laser = build_laser(spec)
    assert laser.analyze(spec.pump_power).stable
    km = kerr_model(spec, laser.thermal_focal_length(spec.pump_power))
    cav = km.cold_cavity()
    # thermal lens sits at the crystal centre under the usual name
    assert cav.spot_size_at("crystal thermal lens") > 0
    assert km.brewster and km.slices == spec.klm_slices
    assert abs(km.klm_strength(1)) < 10


def test_ring_and_location_validation():
    spec = presets.ring_nd_yvo4()
    spec.mode = "modelock"
    spec.sesam_location = "mirror2"
    assert any("ring has no end mirrors" in p for p in spec.validate())
    spec.sesam_location = "M3"
    assert spec.validate() == []
    spec.sesam_location = "nowhere"
    assert any("not an element name" in p for p in spec.validate())
    spec = DesignSpec(pump_geometry="side", absorption_efficiency=1.5)
    assert any("Absorption efficiency" in p for p in spec.validate())


def test_old_json_without_new_fields_loads(tmp_path):
    d = presets.cw_nd_yvo4().to_dict()
    for key in ("cavity_type", "pump_geometry", "crystal_brewster", "klm_slices"):
        d.pop(key)
    spec = DesignSpec.from_dict(d)
    assert spec.cavity_type == "standing" and spec.pump_geometry == "end"
