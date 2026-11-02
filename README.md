# laserdesign

A Python library and Qt GUI for designing solid state lasers:
resonator stability and modes, pump absorption, thermal lensing, gain and
threshold, CW output, Q-switching, mode locking and M² estimates.

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

## Documentation

Build with `pip install -e ".[docs]"` and `sphinx-build -b html docs docs/_build/html`.
It contains a step-by-step tutorial, a theory page for each module (with the
equations, references and assumptions) and the full API reference.

## Roadmap

1. Physics core library (done).
2. Example designs in `examples/` (done): CW Nd:YVO4, Q-switched Nd:YAG,
   SESAM mode-locked Nd:YVO4, and a side-pumped Nd:YAG rod after Koechner's
   *Solid-State Laser Engineering*. Each is documented in `docs/examples/`.
3. Qt (PySide6) GUI that guides the user through building a laser (done;
   `laserdesign-gui`, guide in `docs/gui.md`).
4. Packaging, full documentation and GUI tutorial.

## References

Siegman, *Lasers*; Milonni and Eberly, *Laser Physics*; Koechner,
*Solid-State Laser Engineering*. See `docs/references.md` for the papers
behind specific models.
