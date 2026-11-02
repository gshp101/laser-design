# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.1.0] - 2026-11-02

First release.

### Added

- Physics library `laserdesign`:
  - materials database (Nd:YAG, Nd:YVO4, Yb:YAG, Ti:sapphire) with overrides;
  - ABCD resonators (standing-wave and ring), eigenmodes, stability,
    astigmatism, mode spacing;
  - pump absorption and pump beam geometry;
  - thermal lensing for end-pumped crystals and side-pumped rods, and the
    fracture limit;
  - threshold, slope efficiency and a spatially resolved CW model
    (four-level and quasi-three-level);
  - active Q-switching (analytic, repetitive and rate-equation simulation);
  - mode-locking estimates (transform limit, AM, soliton, SESAM and QML);
  - M² from fields, thermal aberration, multimode estimate and caustic fit;
  - `EndPumpedLaser`, which combines all of the above.
- Example designs: CW Nd:YVO4, Q-switched Nd:YAG, SESAM mode-locked Nd:YVO4
  and a side-pumped Nd:YAG rod after Koechner.
- Qt (PySide6) GUI `laserdesign-gui`: a five-step guided design with live
  plots, example presets and JSON design files.
- Documentation: tutorial, GUI guide, example pages, theory pages, developer
  guide, validation summary and API reference.
- Continuous integration for tests (Python 3.10 to 3.13), the docs and the
  package build.
- Zero-Clause BSD license.
