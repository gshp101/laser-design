# laserdesign

`laserdesign` is a Python library for designing diode- and laser-pumped solid
state lasers. It covers the calculations an experienced laser engineer does
when laying out a new oscillator:

- **Resonators:** ABCD matrices, standing-wave and ring resonators,
  stability, TEM00 eigenmodes, astigmatism of folded cavities and its
  compensation, mode spacing.
- **Pumping and thermal effects:** pump absorption, pump beam geometry,
  temperature profiles, thermal lensing and fracture limits.
- **Gain and CW output:** threshold, slope efficiency and a spatially resolved
  model of end-pumped and side-pumped lasers (four-level and
  quasi-three-level, TEM00 or multimode).
- **Q-switching:** active and passive (saturable absorber) Q-switching:
  analytic pulse energy, peak power and width, repetition rate with CW
  pumping, and rate-equation simulators.
- **Mode locking:** transform limits, active AM mode locking, soliton mode
  locking, SESAM design and the Q-switched mode-locking limit, and
  Kerr-lens mode locking with a self-consistent Kerr lens.
- **Beam quality:** second-moment M² of arbitrary fields, M² degradation from
  thermal aberration, multimode estimates and caustic fitting.

Worked {doc}`example designs <examples/index>` cover CW, actively and
passively Q-switched, SESAM and Kerr-lens mode-locked, side-pumped and ring
lasers, including a side-pumped rod after Koechner. The Qt
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
theory/passive_qswitching
theory/modelocking
theory/kerr_lens
theory/beam_quality
theory/side_pumping
theory/ring_resonators
```

```{toctree}
:maxdepth: 2
:caption: Reference

api/index
validation
developer
references
```
