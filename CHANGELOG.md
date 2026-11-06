# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Results step, desktop and browser: plot any numeric result against one
  of the inputs that set it (the inputs in its hover note). Pick the
  result and the input, edit the range if you like, and the input is swept
  with everything else as designed; the current design is marked and
  unstable points leave gaps. Air gaps, fold mirrors and lenses can be
  swept one by one, and material constants as overrides. New Qt-free
  module `laserdesign.gui.sweep`; the browser report gains a `sweeps` list
  alongside `rows`, and `laserdesign.web.api.sweep()` draws one.
- Resonator round-trip plot now also works for unstable resonators: it
  follows a trial beam (pumped radius, wavefront matched to mirror 1) for
  one round trip, so you can see where the beam runs away. Every cavity
  element is marked on the plot. Library: `launch_q()` on both resonator
  types and a `q_start` argument to `round_trip_profile()`; landmarks now
  cover every element except air gaps.
- Sixteen more gain media in the materials database, for twenty in all:
  Nd:GdVO4, Nd:YLF (1047 and 1053 nm), Nd:phosphate glass, Yb:KGW, Yb:KYW,
  Yb:phosphate glass, Yb:CaF2, Yb:Lu2O3, Cr:LiSAF, Cr:forsterite,
  alexandrite, Cr:ZnSe, Er:YAG (1645 nm), Tm:YAG and Ho:YAG, each with its
  sources. They appear in the Qt wizard and the browser version. The Gain
  medium step shows each material's sources. New page `docs/materials.md`
  with a summary table and modelling notes, and `tests/test_materials.py`,
  which runs every material through every wizard step.
- Results step, desktop and browser: hovering over a row shows how the
  quantity is found and the principal inputs that set it, grouped by wizard
  step with their current values. The dependencies are written once, in the
  new Qt-free module `laserdesign.gui.influences`, and follow the design (end
  or side pumping, standing-wave or ring resonator, operating mode). The
  browser report gains a `tips` list alongside `rows`.
- Beam radius over one round trip on the resonator step of the Qt wizard and
  the web version: a standing-wave resonator is traced from end mirror 1 to
  end mirror 2 and back to mirror 1, a ring once around the loop, with the
  mirrors and crystal marked. New `round_trip_profile()` on
  `StandingWaveCavity` and `RingCavity` (with `ModeProfile.landmarks`) and the
  shared `laserdesign.gui.spec.round_trip_mode()` that both front ends plot.
- Browser version of the design wizard (`web/`), with the app icon on its loading screen: the five steps of the Qt
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

### Fixed

- Qt wizard: dn/dT can be edited to a negative value, and a database value
  that the spin box has to round (such as a gain bandwidth in GHz) is no
  longer stored as a user override.

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
