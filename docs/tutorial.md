# Tutorial: designing an end-pumped Nd:YVO4 laser

This tutorial walks through a complete design with the library, in the same
order the GUI wizard will use: gain medium, pump, thermal lens, resonator,
CW performance, beam quality, then Q-switched and mode-locked operation.
Sections 10 to 13 then show passive Q-switching, ring resonators, side-pumped
rods and Kerr-lens mode locking. Each
step uses one module, so it doubles as a tour of the API. All code blocks run
as written, in order, in one Python session.

The target is a compact laser at 1064 nm pumped by a 20 W fibre-coupled diode
at 808 nm, focused to a 200 µm waist radius with M² ≈ 30.

## 1. Choose the gain medium

```python
import numpy as np
from laserdesign import abcd, beam_quality, gain, modelocking, pump, qswitch, thermal
from laserdesign.materials import get_material
from laserdesign.units import mm, um, nm, us, kHz, cm2

yvo4 = get_material("Nd:YVO4")
print(yvo4.name, yvo4.emission_cross_section / cm2, "cm^2")
print("tau =", yvo4.upper_state_lifetime / us, "us")
print("heat fraction =", yvo4.effective_heat_fraction)
```

The materials database holds typical literature values. Override any of them
with your own data with `replace`, for example a measured effective pump
absorption coefficient for your diode's spectrum:

```python
doping = 0.3          # at.%
length = 6 * mm
alpha = yvo4.pump_absorption_coefficient(doping)
print(f"alpha = {alpha / 100:.1f} /cm")
```

## 2. Pump absorption and pump size

```python
eta_abs = pump.absorbed_fraction(alpha, length)
print(f"absorbed fraction: {eta_abs:.3f}")

pump_beam = pump.PumpBeam(power=20.0, waist=200 * um, wavelength=808 * nm,
                          m2=30, waist_position=1 * mm)
w_p = pump_beam.effective_radius(alpha, length, n=yvo4.refractive_index)
print(f"absorption-weighted pump radius: {w_p / um:.0f} um")
```

The effective radius weights the diverging pump by where it is absorbed; it is
the value to use in the threshold and thermal-lens formulas. If you need to
absorb a given fraction, {func}`laserdesign.pump.absorption_length_for` gives
the crystal length.

## 3. Thermal lens

```python
p_abs = 20.0 * eta_abs
f_th = thermal.thermal_lens(yvo4, p_abs, w_p)
print(f"thermal focal length at 20 W: {f_th / mm:.0f} mm")
```

This is the Innocenzi result $f = \pi K w_p^2 / (P_h\, dn/dT)$
({doc}`theory/pumping_thermal`). It ignores end-face bulging, which adds
roughly 20 to 50 % to the lens power in Nd:YVO4; pass an
`extra_coefficient` to include it once you know its size for your mount.

## 4. Build the resonator

A simple plano-concave cavity: flat dichroic coating on the pumped crystal face
(mirror 1), the crystal, an air gap and a curved output coupler (mirror 2).
The resonator is written as a function of the thermal focal length so we can
follow it as the pump power changes.

```python
def cavity(f_thermal):
    return abcd.StandingWaveCavity(
        [*abcd.crystal_with_thermal_lens(length, yvo4.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(40 * mm)],
        R1=np.inf, R2=200 * mm, wavelength=yvo4.laser_wavelength)

cav = cavity(f_th)
print("stable:", cav.is_stable(), " m =", round(cav.stability_parameter(), 3))
w_l = cav.spot_size_at("YVO4 thermal lens")
print(f"laser mode radius in the crystal: {w_l / um:.0f} um")
print(f"FSR: {cav.free_spectral_range / 1e9:.2f} GHz")
```

Plot the mode through the cavity and the stability parameter versus pump
power to see how much margin the design has. `mode_profile()` samples one
pass from mirror 1 to mirror 2; `round_trip_profile()` samples the full
round trip (mirror 1 to mirror 2 and back, or once around a ring) and lists
the mirror positions in `landmarks`:

```python
import matplotlib.pyplot as plt

prof = cav.mode_profile()
powers = np.linspace(0.5, 30, 60)
m = [cavity(thermal.thermal_lens(yvo4, p * eta_abs, w_p)).stability_parameter()
     for p in powers]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.5))
a1.plot(prof.z / mm, prof.w / um)
a1.set(xlabel="position from mirror 1 [mm]", ylabel="w [um]", title="TEM00 mode at 20 W")
a2.plot(powers, m)
a2.axhline(1, ls="--", c="k"); a2.axhline(-1, ls="--", c="k")
a2.set(xlabel="pump power [W]", ylabel="m = (A + D) / 2", title="stability")
fig.tight_layout()
```

The cavity is stable while $-1 < m < 1$. Here the thermal lens pushes the
cavity towards the edge of stability as the pump power rises, where the mode in
the crystal grows quickly. A good TEM00 design puts the operating point where
the mode radius in the crystal is close to the pump radius, and far enough from
the stability edge that small changes in pump power do not change it much.

## 5. Threshold and CW output

```python
T, L = 0.10, 0.01                  # output coupler and other round-trip losses
delta = gain.round_trip_loss(T, L)
p_th = gain.threshold_pump_power(yvo4, w_l, w_p, delta, eta_abs)
cw = gain.end_pumped_cw(yvo4, 20.0, w_l, w_p, T, L, eta_abs)
print(f"threshold: {p_th:.2f} W   output at 20 W: {cw.output_power:.2f} W")
```

{func}`laserdesign.gain.end_pumped_cw` solves the spatially resolved rate
equations, so pump/mode overlap is included automatically. Try changing
`T`: the optimum output coupling for this design is where the output peaks.

```python
for t in [0.03, 0.05, 0.1, 0.2, 0.3]:
    out = gain.end_pumped_cw(yvo4, 20.0, w_l, w_p, t, L, eta_abs).output_power
    print(f"T = {t:.2f}: {out:.2f} W")
```

## 6. Beam quality

```python
p_heat = p_abs * yvo4.effective_heat_fraction
m2_ab = beam_quality.m2_thermal_aberration(w_l, w_p, p_heat, yvo4.thermal_conductivity,
                                           yvo4.dn_dT, yvo4.laser_wavelength)
m2_mm = beam_quality.m2_from_mode_size_ratio(w_p, w_l)
print(f"M^2 from thermal aberration: {m2_ab:.2f}")
print(f"M^2 from pump/mode size ratio: {m2_mm:.2f}")
print(f"combined estimate: {beam_quality.combine_m2(m2_ab, m2_mm):.2f}")
```

The aberration value is for one round trip of an ideal Gaussian through the
non-parabolic part of the thermal lens, so it is an upper bound for a TEM00
laser. The size-ratio value predicts multimode operation when the pump is
larger than the mode. Try a 250 µm pump waist in step 2 to see both the
efficiency and the beam quality change.

## 7. The same thing in one object

{class}`laserdesign.design.EndPumpedLaser` bundles steps 2 to 6:

```python
from laserdesign import EndPumpedLaser

laser = EndPumpedLaser(material=yvo4, doping=doping, crystal_length=length,
                       pump_beam=pump_beam, cavity=cavity,
                       crystal_element="YVO4 thermal lens",
                       output_coupling=T, passive_loss=L)
for op in laser.scan([5, 10, 15, 20]):
    print(f"{op.pump_power:4.0f} W pump -> {op.output_power:5.2f} W,"
          f" w_l = {op.laser_radius / um:4.0f} um, M^2 ~ {op.m2_estimate:.2f}")
```

## 8. Q-switched operation

Add an acousto-optic Q-switch to the cavity and run it at 50 kHz:

```python
qs = laser.q_switched(20.0, 50 * kHz)
print(f"N_i/N_th = {qs['initial_ratio']:.1f}")
print(f"pulse energy {qs['energy'] * 1e6:.0f} uJ, width {qs['pulse_width'] * 1e9:.1f} ns,"
      f" peak {qs['peak_power'] / 1e3:.1f} kW, average {qs['average_power']:.2f} W")
```

To look at the pulse shape and build-up time, integrate the rate equations:

```python
sim = qswitch.simulate_q_switch(
    qs["initial_ratio"], np.pi * (w_l**2 + w_p**2) / 2,
    yvo4.emission_cross_section, yvo4.laser_photon_energy, delta,
    gain.output_coupling_loss(T), cav.round_trip_time)
print(f"FWHM {sim.fwhm * 1e9:.1f} ns, build-up {sim.buildup_time * 1e9:.0f} ns")
```

Nd:YVO4's short lifetime means the energy per pulse saturates once the
repetition period exceeds about one lifetime (100 µs); Nd:YAG (230 µs) stores
more energy at low repetition rates. Swap `get_material("Nd:YAG")` into step 1
to compare.

## 9. SESAM mode locking

Replace the output coupler with a SESAM end mirror (and couple out through a
fold mirror). The key design questions are the repetition rate, whether the
pulse energy clears the Q-switched mode-locking threshold, and how strongly the
SESAM is saturated:

```python
ml = laser.sesam_mode_locked(20.0, absorber_saturation_fluence=70e-6 / cm2,
                             modulation_depth=0.01)
chk = ml["check"]
print(f"repetition rate {chk.repetition_rate / 1e9:.2f} GHz")
print(f"pulse energy {chk.pulse_energy * 1e9:.1f} nJ, QML threshold {chk.qml_threshold * 1e9:.1f} nJ")
print("CW mode locked:", chk.cw_mode_locked, f" (E_p/E_sat,A = {chk.absorber_saturation:.1f})")
print(f"pulse width estimate {chk.pulse_width_estimate * 1e12:.1f} ps")
```

With this short cavity the margin is below 1, so the laser would Q-switch mode lock. Lengthen the cavity (more energy per pulse),
make the mode on the SESAM smaller, or choose a SESAM with lower modulation
depth or saturation fluence. The theory behind each check is in
{doc}`theory/modelocking`.

## 10. Passive Q-switching with Cr:YAG

Put a Cr⁴⁺:YAG absorber next to the output coupler instead of an active
switch. Nd:YVO4's large emission cross section makes a passive switch harder
to bleach than in Nd:YAG, so check the bleaching criterion before trusting
the pulse numbers:

```python
pq = laser.passively_q_switched(20.0, initial_transmission=0.9, absorber="cr:yag",
                                absorber_location=2)
print(f"bleaching criterion {pq['pulse'].bleaching_criterion:.2f} (needs > 1)")
print(f"absorber spot {pq['absorber_radius'] / um:.0f} um,"
      f" energy {pq['energy'] * 1e6:.0f} uJ, width {pq['pulse_width'] * 1e9:.1f} ns,"
      f" rate {pq['rep_rate'] / 1e3:.0f} kHz")
print("absorber recovers between pulses:", pq["absorber_recovered"])
```

The criterion compares how fast the absorber bleaches with how fast the gain
saturates. It passes here because the mode at the output coupler is smaller
than the effective gain area, which includes the 200 µm pump. Unlike active
Q-switching, the pulse energy is fixed by T₀ and the cavity; the pump power
only sets the repetition rate. Here that rate is so high that the period is
shorter than three Cr:YAG recovery times (`absorber_recovered` is False):
the absorber cannot recover fully, so a lower T₀ (more stored energy, lower
rate) is the better choice. The theory is in
{doc}`theory/passive_qswitching`, and {doc}`examples/passive_qswitch_nd_yag_cr_yag`
designs a Nd:YAG/Cr:YAG laser.

## 11. A ring resonator

A ring uses the same `EndPumpedLaser`; only the cavity function changes. The
element list is one full loop, with the curved mirrors at their angle of
incidence and names for the mirrors you want to refer to:

```python
fold = np.radians(6)

def ring(f_thermal):
    return abcd.RingCavity(
        [abcd.FreeSpace(200 * mm),
         *abcd.crystal_with_thermal_lens(length, yvo4.refractive_index, f_thermal,
                                         name="YVO4"),
         abcd.FreeSpace(200 * mm),
         abcd.CurvedMirror(R=300 * mm, angle=fold, name="M1"), abcd.FreeSpace(200 * mm),
         abcd.FlatMirror(angle=fold, name="M2"), abcd.FreeSpace(200 * mm),
         abcd.FlatMirror(angle=fold, name="M3"), abcd.FreeSpace(200 * mm),
         abcd.CurvedMirror(R=300 * mm, angle=fold, name="M4")],
        wavelength=yvo4.laser_wavelength)

ring_laser = EndPumpedLaser(material=yvo4, doping=doping, crystal_length=length,
                            pump_beam=pump_beam, cavity=ring,
                            crystal_element="YVO4 thermal lens",
                            output_coupling=T, passive_loss=L + 0.02)
op_ring = ring_laser.analyze(20.0)
print(f"ring: {op_ring.gain_passes} gain pass, threshold {op_ring.threshold:.2f} W,"
      f" output {op_ring.output_power:.2f} W, FSR {ring(f_th).free_spectral_range / 1e6:.0f} MHz")
```

Every result (threshold, Q-switching, SESAM checks) now uses one gain pass
per round trip and a repetition rate of c/L; see
{doc}`theory/ring_resonators`.

## 12. A side-pumped rod

{class}`laserdesign.design.SidePumpedRodLaser` replaces the pump beam by a
uniformly pumped rod. Its thermal lens includes stress bifocusing, and a
multimode beam can be modelled as filling part of the rod:

```python
from laserdesign import SidePumpedRodLaser

yag = get_material("Nd:YAG")

def rod_cavity(f_thermal):
    return abcd.StandingWaveCavity(
        [abcd.FreeSpace(300 * mm),
         *abcd.crystal_with_thermal_lens(65 * mm, yag.refractive_index, f_thermal,
                                         name="rod"),
         abcd.FreeSpace(300 * mm)],
        R1=np.inf, R2=np.inf, wavelength=yag.laser_wavelength)

rod = SidePumpedRodLaser(material=yag, doping=1.0, rod_radius=2 * mm, rod_length=65 * mm,
                         cavity=rod_cavity, crystal_element="rod thermal lens",
                         output_coupling=0.2, passive_loss=0.04,
                         absorption_efficiency=0.7, multimode_fill=0.8)
op_rod = rod.analyze(400.0)
f_rod = rod.thermal_focal_lengths(400.0 * 0.7)
print(f"rod lens radial {f_rod['radial'] / mm:.0f} mm, tangential {f_rod['tangential'] / mm:.0f} mm")
print(f"multimode output {op_rod.output_power:.0f} W, M^2 ~ {op_rod.m2_estimate:.0f}")
```

See {doc}`theory/side_pumping` and {doc}`examples/side_pumped_nd_yag`.

## 13. Kerr-lens mode locking

{class}`laserdesign.kerr.KerrLensModel` slices a Kerr medium into thin
nonlinear lenses and solves the resonator self-consistently. You give it the
resonator as a function of the crystal's element list. For a Ti:sapphire
X-cavity with a Brewster-cut crystal, first find the fold angle that cancels
the crystal's astigmatism:

```python
from laserdesign import kerr

tis = get_material("Ti:sapphire")
n_tis = tis.refractive_index
path = 4 * mm
theta = abcd.astigmatism_compensation_angle(100 * mm, path * n_tis / np.sqrt(n_tis**2 + 1),
                                            n_tis)

def x_cavity(crystal):
    return abcd.StandingWaveCavity(
        [abcd.FreeSpace(800 * mm), abcd.CurvedMirror(R=100 * mm, angle=theta),
         abcd.FreeSpace(51.85 * mm), *crystal, abcd.FreeSpace(51.85 * mm),
         abcd.CurvedMirror(R=100 * mm, angle=theta), abcd.FreeSpace(600 * mm)],
        R1=np.inf, R2=np.inf, wavelength=tis.laser_wavelength)

klm = kerr.KerrLensModel(x_cavity, path, n_tis, tis.nonlinear_index,
                         tis.laser_wavelength, brewster=True, slices=6)
print(f"fold angle {np.degrees(theta):.1f} deg, P_cr = {klm.critical_power / 1e6:.2f} MW")
print(f"KLM strength at the output coupler {klm.klm_strength(1):.2f},"
      f" in the crystal {klm.klm_strength('crystal'):.2f}")
```

Negative values mean the Kerr lens shrinks the mode there, which favours
pulses at a hard aperture (output coupler) or with a small pump spot (crystal).
{doc}`examples/klm_ti_sapphire` scans the mirror separation; the theory is in
{doc}`theory/kerr_lens`.

## Where to go next

- The {doc}`theory pages <theory/resonators>` derive each model and list its
  assumptions.
- The {doc}`API reference <api/index>` documents every function.
