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
| Ring resonators (one gain pass) | Threshold exactly twice the standing-wave value; CW model consistent with it; slope tends to the ideal value; ring Q-switch energy doubles and matches the ODE; SESAM repetition rate c/L | `test_advanced.py` |
| Pump and laser profiles | Overlap integrals of Gaussian and top-hat profiles against numerical integration; CW threshold consistent for every combination; flat-top multimode slope scales with the filled area | `test_advanced.py` |
| Passive Q-switching | Degnan's analytic energy, peak power and final inversion against direct integration of the three rate equations (standing wave and ring, within 1 to 2 %); fast-absorber limit equals active Q-switching; bleaching criterion; repetition-rate limits | `test_advanced.py`, `test_examples.py` |
| Kerr lens | Round-beam Kerr lens formula; critical power; zero-power solution equals the cold cavity; converged lenses reproduce the local spot sizes; KLM strength matches a direct small-power difference; astigmatism compensation aligns the tangential and sagittal stability zones | `test_advanced.py` |
| Side-pumped rod | Threshold against the closed form with the top-hat overlap; bifocal lenses and their average; multimode M² from the fill factor | `test_advanced.py` |
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
- **Passive Q-switching** assumes a thin absorber that recovers fully between
  pulses and bleaches uniformly across the beam.
- **KLM strength** describes the onset of the Kerr effect at small power, not
  the mode-locked pulse.
- **Side pumping** assumes a uniform pump across the rod; multimode beams are
  modelled as flat tops.
