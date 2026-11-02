# Validation

How each model is checked, and how far to trust it. Every check listed here
is an automated test in `tests/`.

| Model | Checked against | Test file |
|---|---|---|
| Resonator eigenmodes and stability | Siegman's closed-form two-mirror results (eqs. 19.18 to 19.20), the confocal limit, transverse mode spacing (eq. 19.31), ring/linear equivalence | `test_abcd.py` |
| Gaussian beams, pump absorption | Rayleigh range in a medium, Beer-Lambert absorption, published absorption coefficients of Nd:YAG and Nd:YVO4 | `test_gaussian_pump_thermal.py` |
| Thermal lens (end pumping) | Near-axis optical path difference against the thin-lens formula; far-field temperature against the line-source logarithm | `test_gaussian_pump_thermal.py` |
| Thermal lens (side pumping), fracture | Koechner eq. 7.41 and 7.25, bifocusing with Koechner's photo-elastic coefficients | `test_gaussian_pump_thermal.py`, `test_koechner.py` |
| Threshold and CW output | Analytic Moulton/Risk threshold, numerical model consistent with it at threshold, slope tends to the ideal value for a small pump, Rigrod optimum coupling, quasi-three-level reabsorption | `test_gain.py` |
| Q-switching | Extraction efficiency curve (Siegman fig. 26.6, Koechner fig. 8.4), analytic energy and peak power against direct ODE integration, repetitive Q-switching limits | `test_qswitch_modelocking.py`, `test_koechner.py` |
| Mode locking | Haus AM result against the Kuizenga-Siegman form, transform limits, soliton relation inverted, QML threshold formula | `test_qswitch_modelocking.py` |
| Beam quality | Gaussian (M² = 1), invariance under a lens, Laguerre-Gaussian LG₁₀ (M² = 3), caustic fit recovers known parameters | `test_beam_quality.py` |
| Design model and GUI | Example designs stay in sensible ranges; GUI presets reproduce the example scripts; headless GUI walk-throughs | `test_design.py`, `test_examples.py`, `test_gui_*.py` |

## Values still to be checked

Some reference values in `tests/test_koechner.py` and in the Koechner example
(rod dimensions, photo-elastic coefficients, saturation fluence and
intensity of Nd:YAG, the thermal shock parameter) were entered from memory.
They are marked "from memory" in the code. Check them against *Solid-State
Laser Engineering* and correct them if they differ.

## Known limitations

The models are designed for comparing options and finding trends. Compared
with real lasers:

- **Efficiency is optimistic.** Energy-transfer upconversion, excited-state
  absorption, imperfect pump spectra and spatial hole burning are not
  modelled. Expect 70 to 90 % of the predicted output and a higher
  threshold.
- **The thermal lens uses dn/dT only** unless you supply an extra
  coefficient. End-face bulging and stress typically add 20 to 50 % in
  end-pumped crystals.
- **Q-switching** uses instantaneous switching and plane-wave energy
  extraction with an overlap correction. Pulses from slow acousto-optic
  switches are longer.
- **Mode-locking** results are estimates (QML threshold, pulse-width
  scaling), not pulse simulations.
- **M² from thermal aberration** is a single-pass upper bound; resonators
  partly filter the aberration.
