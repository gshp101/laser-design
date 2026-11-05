# laserdesign

A Python library, Qt GUI and browser app for designing solid state lasers:
resonator stability and modes (standing-wave and ring), end and side
pumping, thermal lensing, gain and threshold, CW output, active and passive
Q-switching, SESAM and Kerr-lens mode locking, and M² estimates.

```python
import numpy as np
from laserdesign import abcd, pump, EndPumpedLaser
from laserdesign.materials import get_material
from laserdesign.units import mm, um, nm

yvo4 = get_material("Nd:YVO4")

def cavity(f_thermal):
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(6 * mm, yvo4.refractive_index, f_thermal, name="YVO4"),
         abcd.FreeSpace(40 * mm)],
        R1=np.inf, R2=200 * mm, wavelength=yvo4.laser_wavelength)

laser = EndPumpedLaser(material=yvo4, doping=0.3, crystal_length=6 * mm,
                       pump_beam=pump.PumpBeam(20.0, 200 * um, 808 * nm, m2=30, waist_position=1 * mm),
                       cavity=cavity, crystal_element="YVO4 thermal lens",
                       output_coupling=0.1, passive_loss=0.01)
op = laser.analyze(20.0)
print(op.output_power, op.laser_radius, op.m2_estimate)
```

## Install

```bash
python -m pip install -e ".[plot,gui,test]"
python -m pytest
laserdesign-gui        # start the guided design GUI
```

## Run it in a web browser

The guided wizard also runs entirely in the browser: the page loads
[Pyodide](https://pyodide.org) (CPython for WebAssembly) and runs this
package, NumPy and SciPy client-side, so it can be hosted on any static web
server such as GitHub Pages.

```bash
python tools/build_web.py --serve    # build into build/web and open http://localhost:8000
```

The `pages` workflow publishes it to GitHub Pages on every push to `main`
(enable once under Settings → Pages → Source: GitHub Actions). See
`docs/web.md` for offline hosting and how it works.

## Documentation

Build with `pip install -e ".[docs]"` and `sphinx-build -b html docs docs/_build/html`
(a `.readthedocs.yaml` is included for hosting on Read the Docs). It contains:

- a library tutorial and a GUI guide,
- eight worked example designs,
- a theory page for each module with equations, references and assumptions,
- a validation summary and a developer guide,
- the full API reference.

## Roadmap

1. Physics core library (done).
2. Example designs in `examples/` (done): CW Nd:YVO4, Q-switched Nd:YAG,
   SESAM mode-locked Nd:YVO4, and a side-pumped Nd:YAG rod after Koechner's
   *Solid-State Laser Engineering*. Each is documented in `docs/examples/`.
3. Qt (PySide6) GUI that guides the user through building a laser (done;
   `laserdesign-gui`, guide in `docs/gui.md`).
4. Packaging, CI, full documentation and GUI tutorial (done).
5. Passive Q-switching, Kerr-lens mode locking, side-pumped rods and ring
   lasers in the library, examples and GUI (done).
6. Browser version of the wizard running the library under Pyodide (done;
   `tools/build_web.py`, guide in `docs/web.md`).

## References

Siegman, *Lasers*; Milonni and Eberly, *Laser Physics*; Koechner,
*Solid-State Laser Engineering*. See `docs/references.md` for the papers
behind specific models.

## License

[Zero-Clause BSD](LICENSE): use, copy, modify and distribute for any purpose,
with no conditions.
