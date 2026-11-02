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
    if "Q-switched" in name:
        assert "Pulse energy" in rows
    if "mode-locked" in name:
        assert "QML margin" in rows


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
