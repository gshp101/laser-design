# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Browser version of the design wizard (`web/`): the five steps of the Qt
  GUI as a static web page that runs `laserdesign`, NumPy and SciPy in the
  browser with Pyodide, in a Web Worker. Examples, open/save of the same JSON
  design files, shareable links, light and dark mode, phone layout.
  `laserdesign.web.report` computes each step's summary, results table and
  plot data without Qt or matplotlib; `laserdesign.web.api` is the JSON
  interface the page calls. `tools/build_web.py` builds the static site
  (optionally with Pyodide copied in for offline use) and the new `pages`
  workflow publishes it to GitHub Pages. Guide in `docs/web.md`.
- GUI icons: one for each wizard step (step list and page headers), for the
  pump geometry, resonator type and operating-mode choices, and an app icon
  for the window and taskbar. They are original SVGs in
  `laserdesign/gui/icons/`, drawn in the palette's text colour so they follow
  light and dark mode. `app-icon.png` (512 × 512) in the repository root is
  rendered from the same SVG by `tools/render_app_icon.py`.

## [0.2.0] - 2026-11-02

### Added

- Passive Q-switching (`laserdesign.passive_qswitch`): saturable absorber
  data (Cr⁴⁺:YAG), Degnan's analytic theory with the bleaching criterion,
  repetition rate with CW pumping, and a three-equation rate simulator.
  `EndPumpedLaser.passively_q_switched`.
- Kerr-lens mode locking (`laserdesign.kerr`): Kerr lens of a Gaussian beam,
  critical power, a self-consistent sliced-crystal resonator model
  (`KerrLensModel`) for normal and Brewster-cut crystals, KLM strength at hard
  and soft apertures. `abcd.astigmatism_compensation_angle` and
  `abcd.brewster_astigmatism`.
- Side-pumped rods: `SidePumpedRodLaser` with a uniform pump, bifocal thermal
  lens, rod clipping loss, multimode (flat-top) operation with an M²
  estimate, and the fracture limit.
- Ring lasers: every gain, Q-switch and mode-locking calculation takes the
  number of gain passes per round trip; `EndPumpedLaser` and
  `SidePumpedRodLaser` detect a `RingCavity`. Absorbers and SESAMs can be
  located by element name.
- `gain.mode_overlap`, `gain.effective_mode_area` and top-hat pump and laser
  profiles in the CW model.
- Examples: passively Q-switched Nd:YAG/Cr:YAG, KLM Ti:sapphire X-cavity,
  400 W side-pumped Nd:YAG rod, unidirectional bow-tie ring Nd:YVO4.
- GUI: side-pumped rods, ring resonators, Brewster-cut crystals, passive
  Q-switch and KLM operating modes, choosable SESAM/absorber/aperture
  location, and four new presets.
- Documentation: theory pages for passive Q-switching, Kerr-lens mode
  locking, side pumping and ring lasers; four example pages; tutorial
  sections 10 to 13; GUI guide sections.

### Changed

- `OperatingPoint` gained `gain_passes`, `tem00_radius`, `laser_profile`,
  `round_trip_loss` and `aperture_loss`; the Q-switch and SESAM methods use the
  operating point's loss.
- `sesam_mode_locked(absorber_mirror=...)` also accepts an element name.

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
