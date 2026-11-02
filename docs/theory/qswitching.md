# Q-switching

Module: {mod}`laserdesign.qswitch`.
Main references: Siegman, *Lasers*, ch. 25 and 26; Milonni and Eberly,
*Laser Physics*, sec. 6.7; Koechner ch. 8; Degnan, IEEE JQE 25, 214 (1989).

## Rate equations during the pulse

During the few nanoseconds of a Q-switched pulse, pumping and spontaneous
decay can be neglected. With $n = N/N_{th}$ and the intracavity photon number
$\Phi$:

$$
\frac{d\Phi}{dt} = \frac{\delta(n-1)}{t_{rt}}\Phi,\qquad
\frac{dn}{dt} = -\frac{2\gamma\sigma}{A t_{rt}}\,n\,\Phi,
$$

where $\delta$ is the round-trip loss after switching, $t_{rt}$ the round-trip
time, $A$ the effective mode area and $\gamma$ the inversion reduction factor
(1 for four-level media).

## Analytic solution

Dividing the two equations and integrating gives the classic results:

- final inversion: $N_i - N_f = N_{th}\ln(N_i/N_f)$;
- energy extraction efficiency $\eta = 1 - N_f/N_i$ (0.80 at $r = 2$, 0.99 at
  $r = 5$);
- output energy $E = \dfrac{A h\nu}{2\sigma\gamma}\,\delta_{oc}\ln\dfrac{N_i}{N_f}$;
- peak power $P_{pk} = \dfrac{A h\nu\,\delta\,\delta_{oc}}{2\sigma\gamma\,t_{rt}}(r - 1 - \ln r)$;
- pulse width $\approx E/P_{pk}$.

Short pulses need a short cavity and a high initial inversion ratio. The test
suite checks these expressions against direct integration of the rate
equations ({func}`~laserdesign.qswitch.simulate_q_switch`), which also gives
the pulse shape and build-up time.

## Repetitive Q-switching

With continuous pumping, the inversion recovers between pulses towards the
value $N_\infty$ it would reach without lasing:

$$
N_i = N_\infty - (N_\infty - N_f)e^{-1/(f\tau)}.
$$

{func}`~laserdesign.qswitch.repetitive_q_switch` solves this together with the
extraction condition. At low repetition rates ($f\tau \ll 1$) the pulse energy
is independent of $f$; at high rates the average power approaches the CW
value and the pulses lengthen.

## Use in the design model

{meth}`~laserdesign.design.EndPumpedLaser.q_switched` connects the plane-wave
theory to the end-pumped geometry:

- $N_\infty/N_{th}$ is the pump power over the CW threshold of the same
  cavity;
- the effective area is $\pi(w_l^2 + w_p^2)/2$, which makes the stored
  inversion equal to the absorbed pump rate times the lifetime;
- energy and peak power are multiplied by the CW model's overlap efficiency
  (actual slope over ideal slope), so pump light outside the mode is not
  counted as extractable.

This is a design estimate. It does not include the finite switching time of
the modulator, pre-lasing, or the gradual opening of an acousto-optic switch,
all of which lengthen pulses in practice.

## Not yet included

Passive Q-switching with a saturable absorber (for example Cr:YAG) is planned;
the Degnan theory for it fits the same framework.
