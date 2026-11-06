"""Headless tests of the Qt window (run with QT_QPA_PLATFORM=offscreen)."""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from laserdesign.gui import presets  # noqa: E402
from laserdesign.gui.spec import DesignSpec  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def window(app):
    from laserdesign.gui.main_window import MainWindow
    w = MainWindow()
    yield w
    w.close()


def walk(window, app):
    for i in range(len(window.pages)):
        window.go(i)
        app.processEvents()
    return dict(window.pages[-1].rows)


@pytest.mark.parametrize("name", list(presets.PRESETS))
def test_presets_reach_results(window, app, name):
    window.load_spec(presets.PRESETS[name]())
    rows = walk(window, app)
    assert "CW output power" in rows
    spec = window.spec
    if spec.mode in ("qswitch", "passive"):
        assert "Pulse energy" in rows
    if spec.mode == "passive":
        assert float(rows["Bleaching criterion (needs > 1)"]) > 1
    if spec.mode == "modelock":
        assert "QML margin" in rows
    if spec.mode == "klm":
        assert "KLM strength at aperture (t / s)" in rows
    if spec.cavity_type == "ring":
        assert rows["Resonator type"].startswith("ring")


def test_results_rows_have_tooltips(window, app):
    walk(window, app)
    table = window.pages[-1].table
    labels = [table.item(r, 0).text() for r in range(table.rowCount())]
    r = labels.index("CW output power")
    for col in (0, 1):
        tip = table.item(r, col).toolTip()
        assert "Output coupler transmission" in tip and "Pump power" in tip
    assert table.item(labels.index("Design"), 0).toolTip() == ""


def test_editing_a_page_updates_spec(window, app):
    page = window.pages[1]
    window.go(1)
    page.power.setValue(12.5)
    app.processEvents()
    assert window.spec.pump_power == pytest.approx(12.5)


def test_material_change_and_override(window, app):
    page = window.pages[0]
    window.go(0)
    page.material.setCurrentIndex(page.material.findData("nd:yag"))
    app.processEvents()
    assert window.spec.material == "nd:yag"
    page.props["thermal_conductivity"].setValue(10.0)
    app.processEvents()
    assert window.spec.material_overrides == {"thermal_conductivity": 10.0}


def test_every_database_material_is_selectable(window, app):
    from laserdesign.materials import MATERIALS
    page = window.pages[0]
    window.go(0)
    assert page.material.count() == len(MATERIALS)
    for key, mat in MATERIALS.items():
        page.material.setCurrentIndex(page.material.findData(key))
        app.processEvents()
        assert window.spec.material == key
        assert window.spec.material_overrides == {}
        assert page.props["dn_dT"].si() == pytest.approx(mat.dn_dT, abs=1e-8)
        assert "Sources:" in page.info.text()


def test_resonator_table_add_move_remove(window, app):
    page = window.pages[2]
    window.go(2)
    n = page.table.rowCount()
    page.table.selectRow(n - 1)
    page.add_element("medium")
    assert page.table.rowCount() == n + 1
    assert window.spec.elements[-1]["type"] == "medium"
    page.table.selectRow(n)
    page._move(-1)
    assert window.spec.elements[n - 1]["type"] == "medium"
    page.table.selectRow(n - 1)
    page._remove()
    assert page.table.rowCount() == n
    # the crystal cannot be removed
    page.table.selectRow(0)
    page._remove()
    assert page.table.rowCount() == n


def test_flat_mirror_and_unstable_message(window, app):
    page = window.pages[2]
    window.go(2)
    page.r2.set_si(math.inf)
    page.r2.changed.emit()
    app.processEvents()
    assert math.isinf(window.spec.R2)
    # A very long gap with a flat output coupler and a strong thermal lens is unstable
    window.spec.elements[-1]["length"] = 5.0
    page.load(window.spec)
    window.refresh()
    window.go(4)
    app.processEvents()
    assert dict(window.pages[4].rows)["Resonator"] == "unstable at this pump power"


def test_save_and_open(window, app, tmp_path):
    window.load_spec(presets.qswitched_nd_yag())
    path = tmp_path / "qs.json"
    window.path = path
    window.save_design()
    assert DesignSpec.load(path) == window.spec
    window.new_design()
    window.open_path(path)
    assert window.spec.mode == "qswitch"
    assert window.pages[3].mode() == "qswitch"


def test_switch_to_ring_and_side_pumping(window, app):
    window.load_spec(presets.ring_nd_yvo4())
    window.go(2)
    assert not window.pages[2].r1.isEnabled()
    # SESAM on a named fold mirror of the ring
    window.go(3)
    op_page = window.pages[3]
    op_page.radios["modelock"].click()
    idx = op_page.sesam_loc.findData("M3")
    assert idx >= 0 and op_page.sesam_loc.findData("mirror2") < 0
    op_page.sesam_loc.setCurrentIndex(idx)
    app.processEvents()
    window.refresh()
    assert window.spec.mode == "modelock" and window.spec.sesam_location == "M3"
    rows = walk(window, app)
    assert "QML margin" in rows

    # side pumping from the pump page
    window.go(1)
    pump_page = window.pages[1]
    pump_page.geometry.setCurrentIndex(pump_page.geometry.findData("side"))
    pump_page.power.setValue(300)
    pump_page.fill.setValue(80)
    app.processEvents()
    window.refresh()
    assert window.spec.pump_geometry == "side" and window.spec.multimode_fill == 0.8
    assert "Rod thermal lens" in pump_page.plot.axes[0].get_title()


def test_passive_mode_from_operation_page(window, app):
    window.load_spec(presets.cw_nd_yvo4())
    window.go(3)
    page = window.pages[3]
    page.radios["passive"].click()
    page.t0.setValue(90)
    app.processEvents()
    window.refresh()
    assert window.spec.mode == "passive"
    assert window.spec.absorber_transmission == pytest.approx(0.9)
    assert window.spec.absorber_location == "mirror2"
    rows = walk(window, app)
    assert "Repetition rate" in rows
