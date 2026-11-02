# Units and conventions

## SI units everywhere

Every function takes and returns SI units: metres, seconds, watts, joules,
kelvin, square metres for cross sections and 1/m for absorption coefficients.
The {mod}`laserdesign.units` module provides multipliers so that inputs read
the way they are usually quoted:

```python
from laserdesign.units import nm, um, mm, cm2, us

wavelength = 1064 * nm         # 1.064e-6 m
sigma = 2.8e-19 * cm2          # 2.8e-23 m^2
tau = 230 * us                 # 2.3e-4 s
```

To display a result in other units, divide by the multiplier:
`w / um` gives a radius in micrometres.

## Beam radii

All beam radii are **1/e² intensity radii** $w$ (for an ideal Gaussian these
equal the second-moment radius $2\sigma$).

## Losses

Losses are **logarithmic round-trip** losses $\delta$, defined so that the
power after one round trip is $e^{-\delta}$ times the power before it. An
output coupler with transmission $T$ contributes $-\ln(1-T)$. Use
{func}`laserdesign.gain.round_trip_loss` to build $\delta$ from the
transmission and the other losses. For small values $\delta \approx T + L$.

## ABCD matrices and the complex beam parameter

Matrices act on the *reduced* ray $(y, n y')$, and Gaussian beams are
described by the reduced complex beam parameter $\hat q = q/n$
(Siegman, *Lasers*, ch. 15 and 20):

$$
\frac{1}{\hat q} = \frac{n}{R} - i\frac{\lambda_0}{\pi w^2}.
$$

The vacuum wavelength $\lambda_0$ is used everywhere, and a crystal of length
$L$ and index $n$ has $B = L/n$. Mirror radii are positive for concave
mirrors.

## Tangential and sagittal planes

Elements accept a `plane` argument: `"t"` (tangential, in the plane of
incidence) or `"s"` (sagittal). For a cavity without off-axis curved mirrors
or Brewster surfaces the two are identical.
