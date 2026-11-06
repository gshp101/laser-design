"""Tests for the browser front end's Python side and the static site builder."""

import importlib.util
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from laserdesign.gui import presets
from laserdesign.gui.spec import DesignSpec, build_laser
from laserdesign.web import STEPS, api
from laserdesign.web import report as report_mod

ROOT = Path(__file__).resolve().parent.parent


def _run(spec: DesignSpec, step: str) -> dict:
    text = api.run(json.dumps(spec.to_dict()), step)
    assert "NaN" not in text and "Infinity" not in text  # strict JSON for the browser
    return json.loads(text)


@pytest.mark.parametrize("name", list(presets.PRESETS))
@pytest.mark.parametrize("step", STEPS)
def test_every_preset_and_step_reports(name, step):
    out = _run(presets.PRESETS[name](), step)
    assert out["error"] is None, out.get("traceback")
    assert out["problems"] == []
    for p in out["plots"]:
        assert p["message"] or p["series"]
        for s in p["series"]:
            assert len(s["x"]) == len(s["y"])
    if step == "results":
        assert len(out["rows"]) >= 12
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in out["rows"])


def test_results_match_library():
    spec = presets.qswitched_nd_yag()
    laser = build_laser(spec)
    op = laser.analyze(spec.pump_power)
    qs = laser.q_switched(spec.pump_power, spec.rep_rate)
    rows = dict(_run(spec, "results")["rows"])
    assert rows["CW output power"] == f"{op.output_power:.3g} W"
    assert rows["Pulse energy"] == f"{qs['energy'] * 1e3:.3g} mJ"


@pytest.mark.parametrize("name", ["CW Nd:YVO4 (30 W pump)", "Ring Nd:YVO4 (unidirectional bow-tie)"])
def test_resonator_plots_one_round_trip(name):
    spec = presets.PRESETS[name]()
    cav = build_laser(spec).resonator(spec.pump_power)
    mode = _run(spec, "resonator")["plots"][0]
    x = mode["series"][0]["x"]
    labels = [v["label"] for v in mode["vlines"]]
    assert any("crystal" in label for label in labels)
    if spec.cavity_type == "standing":
        assert x[-1] == pytest.approx(2 * cav.physical_length * 1e3)
        assert labels[0].startswith("M1") and labels[-1].endswith("M1") and "M2" in labels
    else:
        assert x[-1] == pytest.approx(cav.physical_length * 1e3)
    w = mode["series"][0]["y"]
    assert w[0] == pytest.approx(w[-1])


def test_unstable_resonator_is_reported():
    spec = presets.cw_nd_yvo4()
    spec.elements = [{"type": "crystal"}, {"type": "space", "length": 2.0}]
    res = _run(spec, "resonator")
    assert any("Unstable" in line for line in res["info"])
    assert _run(spec, "results")["rows"][0] == ["Resonator", "unstable at this pump power"]


def test_invalid_design_gives_problems_not_exceptions():
    spec = DesignSpec(output_coupling=1.5)
    out = _run(spec, "results")
    assert out["error"]
    assert any("Output coupling" in p for p in out["problems"])
    broken = json.loads(api.run("{not json", "pump"))
    assert broken["error"].startswith("JSONDecodeError")
    with pytest.raises(ValueError):
        report_mod.report(DesignSpec(), "nonsense")


def test_catalog_and_normalise():
    cat = json.loads(api.catalog())
    assert cat["steps"] == list(STEPS)
    assert set(cat["presets"]) == set(presets.PRESETS)
    assert "nd:yag" in cat["materials"]
    assert cat["materials"]["nd:yag"]["values"]["refractive_index"] > 1
    spec = json.loads(api.normalise(json.dumps({"name": "x", "R2": "inf", "bogus": 1})))
    assert spec["name"] == "x" and spec["R2"] == "inf" and "bogus" not in spec
    assert DesignSpec.from_dict(spec).R2 == math.inf


def test_finite_or_none():
    assert report_mod.finite_or_none({"a": [1.0, math.nan, math.inf], "b": "s"}) == {
        "a": [1.0, None, None], "b": "s"}


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "tools" / "build_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_site(tmp_path):
    out = _load_builder().build(tmp_path / "site")
    for f in ("index.html", "app.js", "worker.js", "plot.js", "style.css", "config.js",
              "laserdesign.zip", ".nojekyll", "icons/app.svg", "icons/step-results.svg"):
        assert (out / f).exists(), f
    assert "cdn.jsdelivr.net/pyodide" in (out / "config.js").read_text()
    with zipfile.ZipFile(out / "laserdesign.zip") as zf:
        names = set(zf.namelist())
    assert {"laserdesign/__init__.py", "laserdesign/web/api.py",
            "laserdesign/gui/spec.py"} <= names
    assert not any("__pycache__" in n for n in names)
    # The zipped package works on its own (as it does when unpacked in Pyodide)
    code = ("import json, laserdesign.web.api as a; "
            "print(len(json.loads(a.catalog())['presets']))")
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={"PYTHONPATH": str(out / "laserdesign.zip")}, check=True)
    assert int(res.stdout) == len(presets.PRESETS)


def test_vendor_pyodide_copies_only_what_is_needed(tmp_path):
    src = tmp_path / "pyodide"
    src.mkdir()
    lock = {"packages": {
        "numpy": {"file_name": "numpy.whl", "depends": []},
        "scipy": {"file_name": "scipy.whl", "depends": ["numpy", "libopenblas"]},
        "libopenblas": {"file_name": "libopenblas.zip", "depends": []},
        "pandas": {"file_name": "pandas.whl", "depends": ["numpy"]},
    }}
    (src / "pyodide-lock.json").write_text(json.dumps(lock))
    for f in ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip",
              "numpy.whl", "scipy.whl", "libopenblas.zip", "pandas.whl"):
        (src / f).write_bytes(b"x")
    out = _load_builder().build(tmp_path / "site", pyodide_dir=src)
    copied = {p.name for p in (out / "pyodide").iterdir()}
    assert {"numpy.whl", "scipy.whl", "libopenblas.zip", "pyodide.mjs",
            "pyodide-lock.json"} <= copied
    assert "pandas.whl" not in copied
    assert '"pyodide/"' in (out / "config.js").read_text()
