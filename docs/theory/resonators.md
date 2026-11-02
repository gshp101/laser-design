# Resonators and Gaussian modes

Module: {mod}`laserdesign.abcd`, {mod}`laserdesign.gaussian`.
Main references: Siegman, *Lasers*, chapters 15 to 21; Kogelnik and Li,
Appl. Opt. 5, 1550 (1966).

## Ray matrices

A paraxial ray at a plane is described by its height $y$ and reduced slope
$n y'$. Each optical element maps this vector with a $2\times 2$ matrix:

| Element                      | Matrix                                        | Class                    |
|------------------------------|-----------------------------------------------|--------------------------|
| Distance $d$ in index $n$    | $\begin{pmatrix}1 & d/n\\0 & 1\end{pmatrix}$  | `FreeSpace`, `Medium`    |
| Thin lens $f$                | $\begin{pmatrix}1 & 0\\-1/f & 1\end{pmatrix}$ | `ThinLens`               |
| Mirror $R$ at angle $\theta$ | lens with $f_t = R\cos\theta/2$, $f_s = R/(2\cos\theta)$ | `CurvedMirror` |
| Curved interface $n_1\to n_2$| $\begin{pmatrix}1 & 0\\-(n_2-n_1)/R & 1\end{pmatrix}$ | `Interface`      |
| Brewster plate $t$, $n$      | $B_t = t\sqrt{n^2+1}/n^4$, $B_s = t\sqrt{n^2+1}/n^2$ | `BrewsterPlate`   |

A system matrix is the product in reverse order of travel
({func}`~laserdesign.abcd.system_matrix` handles the ordering).

## Gaussian beams

The complex beam parameter transforms as

$$
\hat q_2 = \frac{A\hat q_1 + B}{C\hat q_1 + D},
\qquad
\frac{1}{\hat q} = \frac{n}{R} - i\frac{\lambda_0}{\pi w^2}.
$$

A beam with beam quality $M^2$ follows the same law with $\lambda_0$ replaced
by $M^2\lambda_0$ (the embedded Gaussian), with Rayleigh range
$z_R = \pi n w_0^2 / (M^2\lambda_0)$.

## Resonator eigenmodes

For a round-trip matrix $(A, B, C, D)$ with unit determinant, a Gaussian mode
reproduces itself when $\hat q = (A\hat q + B)/(C\hat q + D)$. The confined
solution is (Siegman eq. 21.7)

$$
\frac{1}{\hat q} = \frac{D - A}{2B} - i\frac{\sqrt{1 - m^2}}{|B|},
\qquad m = \frac{A + D}{2}.
$$

It exists only when $-1 < m < 1$; this is the **stability condition**. For a
two-mirror cavity $m = 2g_1g_2 - 1$ with $g_i = 1 - L/R_i$, so stability is the
familiar $0 < g_1 g_2 < 1$.

{class}`~laserdesign.abcd.StandingWaveCavity` unfolds a linear resonator:
starting at end mirror 1 it traverses the element list, reflects from mirror
2, traverses the list backwards and reflects from mirror 1.
{class}`~laserdesign.abcd.RingCavity` uses the list as one round trip.

## Closed-form two-mirror results

{func}`~laserdesign.abcd.two_mirror_mode` implements Siegman eqs. 19.18 to
19.20:

$$
w_1^2 = \frac{\lambda L}{\pi}\sqrt{\frac{g_2}{g_1(1 - g_1g_2)}},\qquad
w_0^2 = \frac{\lambda L}{\pi}\sqrt{\frac{g_1g_2(1-g_1g_2)}{(g_1+g_2-2g_1g_2)^2}},
$$

and the test suite checks the general solver against these.

## Mode spacing

Longitudinal modes are spaced by the free spectral range $c/(2L_{opt})$ for a
standing-wave and $c/L_{opt}$ for a ring cavity, with
$L_{opt} = \sum n_i L_i$ (phase index; use group indices for pulse repetition
rates if dispersion matters). Transverse modes are spaced by
$\Delta\nu_T = \mathrm{FSR}\,\theta/2\pi$ where $\cos\theta = m$ is the
round-trip Gouy phase.

## Thermal lenses in resonators

{func}`~laserdesign.abcd.crystal_with_thermal_lens` represents a pumped crystal
as two half-length slabs with a thin lens between them. This is accurate when
the crystal is short compared with the thermal focal length; for very strong
lenses split the crystal into more slices. Because the resonator is usually
built as a function of the thermal focal length, the stability parameter and
mode size can be followed as the pump power changes (see the
{doc}`tutorial <../tutorial>`).

## Assumptions and limits

- Paraxial, aberration-free optics (aberrations are treated separately in
  {doc}`beam_quality`).
- Off-axis elements are handled as separate tangential and sagittal problems;
  general astigmatism (twisted beams) is not modelled.
- Gain guiding and aperture losses are not included.
