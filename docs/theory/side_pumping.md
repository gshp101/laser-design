# Side-pumped rod lasers

Class: {class}`laserdesign.design.SidePumpedRodLaser`.
Main references: Koechner, *Solid-State Laser Engineering*, ch. 3, 6 and 7;
Hanna, Sawyers and Yuratich, Opt. Quantum Electron. 13, 493 (1981); Magni,
J. Opt. Soc. Am. A 4, 1962 (1987).

Diode bars (or flashlamps) around a rod pump it from the side. With three or
more pump directions and a diffuse reflector the absorbed power density is
close to uniform over the cross section, and the barrel is cooled. The model
uses that idealisation.

## Pump and gain

The pump is a top-hat of radius $a$ (the rod radius), and the absorbed
fraction is the product of transfer and absorption efficiencies
$\eta_t\eta_a$ (Koechner ch. 6), given directly as `absorption_efficiency`.
The spatially resolved CW model ({func}`laserdesign.gain.end_pumped_cw`) is
the same as for end pumping with `pump_profile="tophat"`. Its threshold is

$$
P_{th} = \frac{h\nu_p\,(\delta + p\,\sigma_a N_0 l)}
              {p\,\sigma\,\tau\,\eta_q\,\eta_{abs}\int s_0\,r_p\,dA},
$$

and for a TEM00 mode much smaller than the rod the overlap integral is
$1/(\pi a^2)$: the whole pumped cross section must reach threshold even though
only the mode extracts it. This is why TEM00 side-pumped lasers are
inefficient.

## Multimode operation

Without an aperture a side-pumped rod lases on many transverse modes that
together fill most of the rod. Setting `multimode_fill` models the beam as a
flat top of radius $f a$ (the `laser_profile="tophat"` option). The slope
efficiency then scales with $f^2$, the fraction of the pumped area that is
extracted, and the beam quality follows from the embedded-Gaussian rule

$$
M^2 \approx \left(\frac{f a}{w_{00}}\right)^2,
$$

with $w_{00}$ the TEM00 radius of the resonator at that pump power. $M^2$ is
largest in the middle of a stability range, where $w_{00}$ is smallest, and
falls towards the edges, where the TEM00 mode grows.

## TEM00 operation and rod clipping

For TEM00 operation the rod is the limiting aperture. The model adds the
clipping loss $1 - (1 - e^{-2a^2/w_{00}^2})^p$ per round trip to the passive
loss, so a mode that grows near a stability edge does not extract more than
the rod allows (`OperatingPoint.aperture_loss`). Large-mode TEM00 designs
that sit near such an edge on purpose (dynamically stable resonators, Magni
1987) show up as a steep rise of output near the edge; the operating window
is narrow.

## Thermal lens and bifocusing

The thermal lens of a uniformly pumped, barrel-cooled rod is (Koechner
eq. 7.41)

$$
f = \frac{K A}{P_h}\left(\frac{1}{2}\frac{dn}{dT} + \alpha C_{r,\phi} n_0^3
    + \frac{\alpha r_0 (n_0 - 1)}{l}\right)^{-1},
$$

with the photo-elastic coefficients $C_r$ and $C_\phi$ for radially and
tangentially polarised light (Nd:YAG [111]: 0.017 and −0.0025). Stress
birefringence therefore gives two focal lengths that differ by about 20 % in
Nd:YAG. `thermal_lens` chooses which one the resonator uses: the
`"average"` optical power (an unpolarised laser), `"radial"` or
`"tangential"` (check both: each polarisation leaves the stable zone at a
different pump power), or `"dn_dT"` (no stress or end-face bulging).

Because the temperature profile of a uniformly heated rod is parabolic, the
model takes the thermal lens as aberration-free ($M^2_{ab} = 1$).
{meth}`~laserdesign.design.SidePumpedRodLaser.stress_fracture_pump` gives the
pump power at the fracture limit $P_h/l = 8\pi R_T$ (Koechner eq. 7.25).

## Q-switching

Active and passive Q-switching use the same effective area,
$1/\int s_0 r_p\,dA$ ($\pi a^2$ for a flat-top beam inside the rod), and the
same overlap efficiency as end-pumped lasers. For a multimode beam the
absorber spot area is taken as $\pi w_s^2 M^2$, the area of the multimode beam
at the absorber.

## What is not modelled

Non-uniform pump distributions (the model has no radial pump profile beyond
the top-hat), depolarisation loss from stress birefringence, gain
non-uniformity along the rod, and amplified spontaneous emission in large
rods.
