"""Checks on the materials database: sane values, and every medium runs end to end."""

import json
import math
from pathlib import Path

import pytest

from laserdesign import thermal
from laserdesign.gui.spec import DesignSpec
from laserdesign.materials import MATERIALS, get_material
from laserdesign.units import cm, nm, um
from laserdesign.web import STEPS, api

#: A doping that absorbs most of the pump in a few mm to a few cm.
TYPICAL_DOPING = {
    "nd:yag": 1.0, "nd:yvo4": 0.3, "nd:gdvo4": 0.3, "nd:ylf 1047": 1.0, "nd:ylf 1053": 1.0,
    "nd:glass": 3.0, "yb:yag": 5.0, "yb:kgw": 5.0, "yb:kyw": 5.0, "yb:glass": 10.0,
    "yb:caf2": 3.0, "yb:lu2o3": 3.0, "ti:sapphire": 0.15, "cr:lisaf": 1.5,
    "cr:forsterite": 5.0, "alexandrite": 0.2, "cr:znse": 8.0, "er:yag": 0.5,
    "tm:yag": 4.0, "ho:yag": 1.0,
}


def test_typical_doping_covers_database():
    assert set(TYPICAL_DOPING) == set(MATERIALS)


@pytest.mark.parametrize("key", list(MATERIALS))
def test_values_are_physical(key):
    m = MATERIALS[key]
    assert get_material(key.upper()) is m
    assert 500 * nm < m.pump_wavelength < m.laser_wavelength < 3 * um
    assert 1e-25 < m.emission_cross_section < 1e-21          # 1e-21 .. 1e-17 cm^2
    assert 1e-7 < m.upper_state_lifetime < 20e-3
    assert 1.3 < m.refractive_index < 2.6
    assert abs(m.dn_dT) < 1e-4
    assert 0.3 < m.thermal_conductivity < 40
    assert m.pump_absorption_cross_section > 0 and m.ion_density_per_unit_doping > 0
    assert m.gain_bandwidth > 0
    assert m.laser_absorption_cross_section < m.emission_cross_section
    assert 0 < m.effective_heat_fraction < 0.5
    assert 0 < m.quantum_efficiency <= 2
    assert m.notes, "every material must name its sources"


@pytest.mark.parametrize("key", list(MATERIALS))
def test_typical_doping_absorbs_pump(key):
    alpha = MATERIALS[key].pump_absorption_coefficient(TYPICAL_DOPING[key])
    assert 0.3 / cm < alpha < 100 / cm


@pytest.mark.parametrize("key", list(MATERIALS))
@pytest.mark.parametrize("step", STEPS)
def test_every_material_runs_in_the_apps(key, step):
    """The default CW design with each medium reports without error in every step."""
    spec = DesignSpec(material=key, doping=TYPICAL_DOPING[key], pump_power=5.0)
    text = api.run(json.dumps(spec.to_dict()), step)
    assert "NaN" not in text and "Infinity" not in text
    out = json.loads(text)
    assert out["error"] is None, out.get("traceback")


def test_catalog_lists_all_materials():
    cat = json.loads(api.catalog())
    assert set(cat["materials"]) == set(MATERIALS)


def test_published_pump_absorption():
    # Nd:GdVO4, 1 at.%, pi-pol. at 808 nm: ~57 /cm (Jensen et al. 1994).
    assert MATERIALS["nd:gdvo4"].pump_absorption_coefficient(1.0) == pytest.approx(57 / cm, rel=0.05)
    # Alexandrite: 0.1 at.% Cr is 3.5e19 /cm^3 (Koechner).
    assert MATERIALS["alexandrite"].ion_density(0.1) == pytest.approx(3.5e19 / cm**3)


def test_negative_dn_dT_gives_diverging_lens():
    ylf = MATERIALS["nd:ylf 1047"]
    assert ylf.dn_dT < 0
    assert thermal.thermal_lens(ylf, 5.0, 300 * um) < 0


def test_two_for_one_pumping_raises_stokes_limit():
    tm = MATERIALS["tm:yag"]
    assert tm.quantum_efficiency * tm.quantum_defect == pytest.approx(0.70, abs=0.01)
    assert math.isclose(tm.effective_heat_fraction, 0.30)


def test_docs_list_every_material():
    text = (Path(__file__).resolve().parent.parent / "docs" / "materials.md").read_text()
    for key, m in MATERIALS.items():
        assert f"`{key}`" in text and m.notes in text
