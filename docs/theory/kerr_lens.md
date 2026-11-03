# Kerr-lens mode locking

Module: {mod}`laserdesign.kerr`.
Main references: Magni, Cerullo and De Silvestri, Opt. Commun. 96, 348 (1993)
and 101, 365 (1993); Cerullo et al., Opt. Lett. 19, 807 (1994); Spence, Kean
and Sibbett, Opt. Lett. 16, 42 (1991); Kogelnik et al., IEEE JQE 8, 373
(1972); Siegman, *Lasers*, ch. 21 and 27.

In a Kerr-lens mode-locked (KLM) laser the intensity-dependent index of the
gain crystal forms a lens that is strong only for the high peak power of a
pulse. If the resonator is set up so that this lens lowers the loss (a hard
aperture) or raises the gain (a soft aperture formed by a small pump spot),
the laser favours pulsed operation. The library models the Kerr lens inside
the resonator self-consistently and quantifies how strongly the mode responds.

## The Kerr lens

A Gaussian beam with peak power $P$ and radii $w_x$, $w_y$ has peak intensity
$I_0 = 2P/(\pi w_x w_y)$. Expanding $n = n_0 + n_2 I$ to second order across
the beam gives, for a slice of length $L$, a thin lens of power

$$
\frac{1}{f_x} = \frac{4 n_2 I_0 L}{w_x^2},\qquad
\frac{1}{f_y} = \frac{4 n_2 I_0 L}{w_y^2},
$$

which for a round beam is $1/f = 8n_2PL/(\pi w^4)$
({func}`~laserdesign.kerr.kerr_lens_power`). The natural power scale is the
self-focusing critical power

$$
P_{cr} = \frac{\lambda^2}{2\pi n_0 n_2},
$$

about 1.8 MW for Ti:sapphire at 800 nm ({func}`~laserdesign.kerr.critical_power`).

In a counter-propagating standing-wave cavity the two directions of a short
pulse meet only near the end mirrors, so each pass through the crystal sees
the one-way peak power $P$.

## Self-consistent solution

The mode size changes inside a tightly focused crystal and the Kerr lens
changes the mode, so {class}`~laserdesign.kerr.KerrLensModel` cuts the crystal
into `slices` pieces with a thin Kerr lens in the middle of each, computes the
resonator eigenmode, updates every lens from the local spot sizes and repeats
(with damping) until the lens powers converge. The user supplies the
resonator as a function of the crystal's element list, so any standing-wave
or ring layout works. An optional thermal lens sits at the crystal centre.

### Brewster-cut crystals

The reduced ABCD model of a Brewster plate (Kogelnik et al.) works with an
equivalent beam whose tangential size equals the size outside the crystal;
the physical tangential size inside is larger by $n$. The model computes the
intensity from the physical size and applies the lens in the reduced frame,
where the lens power has the same form.

### Astigmatism compensation

A Brewster plate of thickness $t$ makes the sagittal reduced length longer
than the tangential one by $Nt$ with $N = \sqrt{n^2+1}(n^2-1)/n^4$. Folding
mirrors of radius $R$ at incidence $\theta$ shorten the tangential focal
length by $(R/2)\sin\theta\tan\theta$ each, so with $m$ folding mirrors the
two planes see the same resonator when

$$
m\,\frac{R}{2}\sin\theta\tan\theta = N t
$$

({func}`~laserdesign.abcd.astigmatism_compensation_angle`; $m = 1$ gives
Kogelnik's $R\sin\theta\tan\theta = 2Nt$).

## KLM strength

The usual figure of merit is the relative change of the spot size at some
plane per unit normalised power $p = P/P_{cr}$, at small power:

$$
\delta = \frac{1}{w}\frac{dw}{dp}\bigg|_{p\to 0}
$$

({meth}`~laserdesign.kerr.KerrLensModel.klm_strength`, computed from
self-consistent solutions at $p = 0.01$ and $0.02$ with Richardson
extrapolation). It can be evaluated

- at a **hard aperture** (an end mirror or a named element such as a slit):
  $\delta < 0$ means the pulse is smaller there than CW light, so a slit
  passes it with less loss;
- in the **crystal** (soft aperture): $\delta < 0$ means the pulse overlaps a
  small pump spot better and sees more gain.

$|\delta|$ of order 1 is useful. It grows without bound near the edges of the
stability zones, which is why KLM lasers are aligned close to a zone edge,
and why they then become sensitive to everything else, including the
thermal lens (the GUI plots $\delta$ against pump power for this reason).
Use {meth}`~laserdesign.kerr.KerrLensModel.spot_vs_power` to follow the mode
to larger powers; the thin-slice model stays reasonable while each slice's
Kerr lens is weak, but at $p \gtrsim 1$ in long crystals it only indicates
trends.

## Dispersion

Femtosecond KLM lasers run as solitons. With the self-phase modulation
coefficient $\delta_{SPM}$ of the crystal (from the mode area in it) and the
intracavity pulse energy $E$, the net round-trip GDD for a sech² pulse of
FWHM $\tau$ is given by
{func}`~laserdesign.modelocking.soliton_required_gdd`; the crystal's own GDD
must be over-compensated by prisms or chirped mirrors. See
{doc}`modelocking`.

## What is not modelled

Spatio-temporal coupling (the Kerr lens varies across the pulse), gain
guiding by the pump profile beyond the soft-aperture figure of merit,
self-starting, and the pulse spectrum. The KLM strength tells you whether and
where a resonator discriminates in favour of pulses; it does not predict the
pulse.
