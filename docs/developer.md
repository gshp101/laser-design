# Developer guide

This page is for anyone extending `laserdesign`: adding a material, a model,
an example or a GUI feature.

## Layout

```text
src/laserdesign/
    units.py          SI helpers and constants
    materials.py      GainMedium and the material database
    gaussian.py       q-parameter helpers
    abcd.py           elements, resonators, eigenmodes
    pump.py           absorption and pump geometry
    thermal.py        temperature, thermal lens, fracture
    gain.py           threshold and CW model
    qswitch.py        Q-switching
    modelocking.py    mode-locking estimates
    beam_quality.py   M^2
    design.py         EndPumpedLaser (combines the modules above)
    gui/
        spec.py       DesignSpec: Qt-free, JSON-serialisable design
        presets.py    example designs as DesignSpecs
        widgets.py    unit-aware inputs, matplotlib canvas
        pages.py      the five wizard pages
        main_window.py, app.py
examples/             runnable example designs (also used by the docs)
tests/                pytest suite
tools/                maintenance scripts (GUI screenshots)
docs/                 Sphinx + MyST documentation
```

The dependency direction is strictly one way: physics modules depend only on
NumPy, SciPy and each other; `design.py` combines them; `gui/spec.py` builds
an `EndPumpedLaser` from plain data; and only the Qt files import PySide6.
Keep it that way, so the physics stays testable and scriptable without a
display.

## Conventions

- **SI units everywhere** in code, with conversions only at the edges
  (GUI widgets and printed output). See {doc}`conventions`.
- **Numpy-style docstrings** with units in brackets, e.g.
  `pump_radius : float` / `Pump 1/e^2 radius [m].` The API reference is
  generated from them.
- **Cite the source** of every formula in the docstring (book and equation
  number, or paper) and add it to the matching theory page.
- Losses are logarithmic round-trip losses; mirror radii are positive for
  concave mirrors.

## Setting up

```bash
python -m pip install -e ".[plot,gui,docs,test]"
QT_QPA_PLATFORM=offscreen python -m pytest      # all tests, including the GUI
sphinx-build -W -b html docs docs/_build/html   # docs, warnings as errors
```

On a headless Linux machine the GUI tests need the Qt runtime libraries
(`libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3`).

## Adding a material

1. Add a `GainMedium` to `materials.py` with every value in SI units and a
   `notes` string naming the sources.
2. Register it in `MATERIALS` under a lower-case key.
3. Add a test in `tests/test_gaussian_pump_thermal.py` (or a new file) that
   checks at least the derived pump absorption coefficient against a
   published value.

The GUI's material list is built from `MATERIALS`, so the new material
appears there automatically.

## Adding a model

1. Put the function in the module it belongs to, with a docstring giving the
   equation and its source.
2. Test it against an independent result: a closed form from a textbook, a
   limiting case, or a numerical integration (see
   `tests/test_qswitch_modelocking.py` for the ODE-versus-analytic pattern).
3. Document the theory, assumptions and limits on the matching page under
   `docs/theory/`.
4. If designers will use it routinely, expose it through `EndPumpedLaser`
   and then on the GUI results page.

## Adding an example

1. Write `examples/<name>.py` with a module docstring describing the design
   and a `run(make_plots=True, outdir=OUT) -> dict` function returning the
   headline numbers.
2. Add a page `docs/examples/<name>.md` and link it from
   `docs/examples/index.md`.
3. Add smoke assertions to `tests/test_examples.py`.
4. If it is an end-pumped standing-wave design, add a matching preset to
   `gui/presets.py` and a check in `tests/test_gui_spec.py` that the two give
   the same numbers.

## Regenerating figures

```bash
for f in examples/*.py; do python "$f"; done           # docs/examples/images
QT_QPA_PLATFORM=offscreen python tools/gui_screenshots.py  # docs/gui/images
```

Commit the regenerated images together with the change that caused them.

## Releasing

1. Update the version in `pyproject.toml` and `src/laserdesign/__init__.py`,
   and add an entry to `CHANGELOG.md`.
2. Check the build: `python -m build && python -m twine check dist/*`.
3. Tag the release (`git tag v0.x.y`) and publish the wheel and sdist.
