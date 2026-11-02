# laserdesign

`laserdesign` is a Python library for designing diode- and laser-pumped solid
state lasers. It covers the calculations an experienced laser engineer does
when laying out a new oscillator:

- **Resonators:** ABCD matrices, stability, TEM00 eigenmodes, astigmatism of
  folded cavities, mode spacing.
- **Pumping and thermal effects:** pump absorption, pump beam geometry,
  temperature profiles, thermal lensing and fracture limits.
- **Gain and CW output:** threshold, slope efficiency and a spatially resolved
  model of end-pumped lasers (four-level and quasi-three-level).
- **Q-switching:** analytic pulse energy, peak power and width, repetitive
  Q-switching with CW pumping, and a rate-equation simulator.
- **Mode locking:** transform limits, active AM mode locking, soliton mode
  locking, SESAM design and the Q-switched mode-locking limit.
- **Beam quality:** second-moment M² of arbitrary fields, M² degradation from
  thermal aberration, multimode estimates and caustic fitting.

Worked {doc}`example designs <examples/index>` cover a CW, a Q-switched and a
mode-locked laser, and a side-pumped rod laser after Koechner. The Qt
{doc}`GUI <gui>` walks you through building a laser step by step on top of the
same models.

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
conventions
tutorial
gui
examples/index
```

```{toctree}
:maxdepth: 2
:caption: Theory

theory/resonators
theory/pumping_thermal
theory/gain
theory/qswitching
theory/modelocking
theory/beam_quality
```

```{toctree}
:maxdepth: 2
:caption: Reference

api/index
references
```
