"""JSON entry points called from JavaScript by the web app.

Every function takes and returns JSON text, so the JavaScript side never
handles Python objects. Infinite radii and focal lengths travel as the
string ``"inf"`` (as in saved design files); ``nan`` and ``inf`` in results
become ``null``.
"""

from __future__ import annotations

import json
import traceback

from .. import __version__
from ..gui.presets import PRESETS
from ..gui.spec import ELEMENT_TYPES, OPERATION_MODES, DesignSpec
from ..materials import MATERIALS
from ..passive_qswitch import ABSORBERS
from .report import MATERIAL_FIELDS, STEPS, finite_or_none, report


def _dumps(obj) -> str:
    return json.dumps(finite_or_none(obj), allow_nan=False, ensure_ascii=False)


def catalog() -> str:
    """Everything the UI needs to build its forms: materials, presets, choices."""
    materials = {}
    for key, mat in MATERIALS.items():
        materials[key] = {
            "name": mat.name,
            "doping_unit": mat.doping_unit,
            "laser_wavelength": mat.laser_wavelength,
            "values": {attr: getattr(mat, attr) for attr, *_ in MATERIAL_FIELDS},
        }
    return _dumps({
        "version": __version__,
        "steps": list(STEPS),
        "materials": materials,
        "material_fields": [
            {"attr": a, "label": label, "scale": s, "unit": unit, "decimals": d}
            for a, label, s, unit, d in MATERIAL_FIELDS],
        "absorbers": {k: a.name for k, a in ABSORBERS.items()},
        "modes": list(OPERATION_MODES),
        "element_types": list(ELEMENT_TYPES),
        "presets": {name: f().to_dict() for name, f in PRESETS.items()},
        "default": DesignSpec().to_dict(),
    })


def normalise(spec_json: str) -> str:
    """Round-trip a design through :class:`DesignSpec` (drops unknown keys)."""
    return _dumps(DesignSpec.from_dict(json.loads(spec_json)).to_dict())


def run(spec_json: str, step: str) -> str:
    """Compute the report for ``step`` (see :mod:`laserdesign.web.report`)."""
    try:
        spec = DesignSpec.from_dict(json.loads(spec_json))
        return _dumps(report(spec, step))
    except Exception as exc:  # report every failure to the page instead of crashing
        return _dumps({"info": [], "rows": [], "plots": [], "notes": [], "problems": [],
                       "error": f"{type(exc).__name__}: {exc}",
                       "traceback": traceback.format_exc()})
