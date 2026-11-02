# Beam quality

Module: {mod}`laserdesign.beam_quality`.
Main references: Siegman, "New developments in laser resonators", Proc. SPIE
1224, 2 (1990); Siegman, Appl. Opt. 32, 5893 (1993); ISO 11146.

## Second-moment definition

For one transverse coordinate, with second moments of intensity in the near
field and of the angular spectrum,

$$
M^2 = 2\sqrt{\langle x^2\rangle\langle k_x^2\rangle - \langle x k_x\rangle^2},
$$

which equals 1 for a Gaussian, $2p + |l| + 1$ for a Laguerre-Gaussian mode and
is unchanged by any ideal lens (the cross term removes pure curvature).
{func}`~laserdesign.beam_quality.m2_radial_field` evaluates this for radially
symmetric fields with one-dimensional integrals.

## Degradation by the thermal lens

The end-pumped temperature profile is parabolic only inside the pumped region
({doc}`pumping_thermal`). A laser mode that extends beyond the pump sees the
logarithmic part as spherical aberration.
{func}`~laserdesign.beam_quality.m2_thermal_aberration` applies the exact
Innocenzi optical path difference to a TEM00 field and computes the resulting
$M^2$. The result grows with heat load, with $dn/dT/K$ and with the ratio of
mode to pump radius, which is why high-power TEM00 designs use a mode slightly
smaller than the pump.

The value is for a single round trip of an ideal Gaussian. The resonator
filters part of the aberration, so measured values for TEM00 lasers are
usually lower; use it to compare designs and as an upper bound.

## Multimode operation

When the pumped region is larger than the TEM00 mode, higher-order transverse
modes reach threshold and the output fills the gain region, so
$M^2 \approx (w_p/w_{00})^2$
({func}`~laserdesign.beam_quality.m2_from_mode_size_ratio`). This rule of thumb
is widely used for multimode end-pumped and side-pumped lasers.

## Combining contributions

{func}`~laserdesign.beam_quality.combine_m2` combines independent
contributions as $M^4_{tot} - 1 = \sum_i (M^4_i - 1)$. This is an engineering
approximation.

## Comparing with measurements

{func}`~laserdesign.beam_quality.fit_m2_caustic` fits measured radii along a
focused beam to $w^2(z) = w_0^2 + (M^2\lambda/\pi w_0)^2(z - z_0)^2$, following
ISO 11146. Use at least ten points, half within one Rayleigh range of the
waist.
