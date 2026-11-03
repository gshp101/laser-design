# Passive Q-switching

Module: {mod}`laserdesign.passive_qswitch`.
Main references: Degnan, IEEE JQE 31, 1890 (1995); Siegman, *Lasers*,
sec. 26.4; Koechner ch. 8.6; Zayhowski and Dill, Opt. Lett. 19, 1427 (1994).

A saturable absorber such as Cr⁴⁺:YAG in the resonator holds the loss high
while the gain builds up. When the gain reaches the unbleached loss, the
growing intracavity field bleaches the absorber, the loss drops and a giant
pulse forms. No driver is needed, but the pulse energy is fixed by the
absorber and the cavity, and only the repetition rate follows the pump.

## Rate equations

With the intracavity photon number $\Phi$, the gain inversion density $N$ and
the fraction $g$ of absorber ions in the ground state:

$$
\frac{d\Phi}{dt} = \frac{\Phi}{t_{rt}}\Big[p\sigma N l - \delta - L_{es}
    - (L_{gs} - L_{es})\,g\Big],\qquad
\frac{dN}{dt} = -\frac{\gamma p \sigma}{A t_{rt}} N\Phi,\qquad
\frac{dg}{dt} = -\frac{p_s\sigma_{gs}}{A_s t_{rt}}\,g\,\Phi .
$$

| Symbol | Meaning |
|---|---|
| $p$, $p_s$ | passes per round trip through gain and absorber (2 in a standing-wave cavity, 1 in a ring) |
| $A$, $A_s$ | effective mode areas in gain and absorber ($\pi w^2/2$ for TEM00) |
| $\delta$ | all other logarithmic round-trip losses, including the output coupler |
| $L_{gs} = p_s\ln(1/T_0)$ | unbleached absorber loss for small-signal single-pass transmission $T_0$ |
| $L_{es} = (\sigma_{es}/\sigma_{gs})L_{gs}$ | residual loss of the fully bleached absorber (excited-state absorption) |

Pumping, spontaneous decay and absorber recovery are slow compared with the
pulse and are neglected during it.

## Analytic solution

Dividing the absorber and gain equations gives $g = x^\alpha$, where
$x = N/N_i$ and

$$
\alpha = \frac{p_s\,\sigma_{gs}\,A}{\gamma\,p\,\sigma\,A_s}
$$

measures how much faster the absorber saturates than the gain. Lasing starts
at $p\sigma N_i l = \delta + L_{gs}$, and integrating $d\Phi/dx$ gives

$$
\Phi(x) = \frac{A}{\gamma p\sigma}\left[(\delta + L_{gs})(1-x)
  - (\delta + L_{es})\ln\frac{1}{x} - (L_{gs} - L_{es})\frac{1 - x^\alpha}{\alpha}\right].
$$

{func}`~laserdesign.passive_qswitch.passive_q_switch_pulse` finds

- the final inversion $x_f$ from $\Phi(x_f) = 0$;
- the photon peak at $x_p$, where
  $(\delta+L_{gs})x_p = \delta + L_{es} + (L_{gs}-L_{es})x_p^\alpha$;
- the output energy $E = \dfrac{h\nu A}{\gamma p\sigma}\,\delta_{oc}\ln\dfrac{1}{x_f}$;
- the peak power $P_{pk} = h\nu\,\delta_{oc}\,\Phi(x_p)/t_{rt}$;
- and the width estimate $E/P_{pk}$.

In the limit $\alpha\to\infty$ the absorber bleaches instantly and the results
reduce to active Q-switching with initial ratio
$r = (\delta + L_{gs})/(\delta + L_{es})$; the test suite checks this.

## The bleaching criterion

Expanding $\Phi(x)$ about $x = 1$ shows that the photon number grows after
threshold only if

$$
\alpha\,(L_{gs} - L_{es}) > \delta + L_{gs}.
$$

The library reports the ratio of the two sides as
`bleaching_criterion`; it must exceed 1, and Degnan recommends a comfortable
margin. Below it the absorber saturates too slowly, the laser runs CW or in
weak, irregular spikes, and no giant pulse is predicted. For Cr:YAG in
Nd:YAG, $\sigma_{gs}/\sigma \approx 3$, so equal mode areas usually work; in
Nd:YVO4 ($\sigma \approx 15\times10^{-19}$ cm²) the ratio is below 1 and the
mode must be focused into the absorber ($A_s \ll A$).

## Repetition rate

After a pulse the inversion recovers from $N_f$ towards its unsaturated value
$N_\infty$ with the upper-state lifetime $\tau$. The next pulse fires at
$N_i$, so

$$
T_{rep} = \tau\ln\frac{r - x_f}{r - 1},\qquad r = \frac{N_\infty}{N_i} =
\frac{P_{pump}}{P_{th}(\delta + L_{gs})},
$$

with $P_{th}(\delta + L_{gs})$ the CW threshold of the cavity with the
unbleached absorber ({func}`~laserdesign.passive_qswitch.passive_repetition_rate`).
This assumes the absorber recovers fully between pulses (Cr:YAG recovers in
about 4 µs); {meth}`~laserdesign.design.EndPumpedLaser.passively_q_switched`
flags designs whose period is shorter than three recovery times.

## In the laser models

{meth}`EndPumpedLaser.passively_q_switched <laserdesign.design.EndPumpedLaser.passively_q_switched>`
(also on {class}`~laserdesign.design.SidePumpedRodLaser`) takes the absorber,
$T_0$ and where the absorber sits (an end mirror or an element name). It uses
the same effective gain area and pump-overlap efficiency as active
Q-switching, reads the absorber spot size from the resonator, and treats the
absorber as thin.

## Rate-equation check

{func}`~laserdesign.passive_qswitch.simulate_passive_q_switch` integrates the
three equations in $\ln\Phi$, $n$ and $g$, starting just above the unbleached
threshold. Energy and peak power agree with the analytic theory to better
than 1 % in the example and the tests; the simulation also gives the pulse
shape and the absorber's bleaching history.

## What is not modelled

Absorber recovery during the pulse, transverse variation of the bleaching
(which narrows the effective mode and can raise M²), thermal effects in the
absorber, and the pulse-to-pulse jitter set by spontaneous emission.
