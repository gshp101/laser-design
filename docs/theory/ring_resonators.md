# Ring lasers

Classes: {class}`laserdesign.abcd.RingCavity`, used by
{class}`~laserdesign.design.EndPumpedLaser` and
{class}`~laserdesign.design.SidePumpedRodLaser`.
Main references: Siegman, *Lasers*, ch. 11 and 21; Koechner ch. 5.4;
Kane and Byer, Opt. Lett. 10, 65 (1985).

A ring resonator with an optical diode (a Faraday rotator plus a reciprocal
rotator or wave plate, or a non-planar ring) oscillates in one direction
only. There is then no standing wave in the gain medium and no spatial hole
burning, which is the usual route to single-frequency operation. The
geometry also changes threshold, Q-switch and mode-locking results, which the
library handles with one parameter, the number of gain passes per round trip
$p$: 2 for a standing-wave and 1 for a ring resonator.

## Resonator

A {class}`~laserdesign.abcd.RingCavity` is the list of elements met in one
full loop, with the curved mirrors as
{class}`~laserdesign.abcd.CurvedMirror` elements at their angle of incidence.
Its eigenmode, stability and astigmatism follow from the loop matrix as for a
standing-wave resonator (Siegman ch. 21). The round-trip time is $L/c$ and
the longitudinal mode spacing $c/L$, with $L$ the optical loop length.
Absorbers, SESAMs and apertures in a ring are located by element name.

The laser models detect a ring with
{func}`~laserdesign.design.gain_passes` and pass $p = 1$ to every gain
calculation.

## Gain and threshold

In the spatially resolved CW model (see {doc}`gain`) the saturating
intensity is $p P s_0(r)$ and the round-trip gain
$p\int[(\sigma_e+\sigma_a)\bar N_2 - \sigma_a N_0 l]\,s_0\,dA$. With
$p = 1$:

- the threshold inversion is $\delta/(\sigma l)$ instead of
  $\delta/(2\sigma l)$, so the threshold pump power doubles for the same
  mode, pump and losses (quasi-three-level reabsorption counts once instead
  of twice);
- above threshold the extracted power per unit of round-trip gain is
  unchanged, so the slope efficiency is the same;
- the optical diode adds loss (typically 1 to 3 % per round trip), which in
  practice matters more than the doubled threshold.

## Q-switching

With one gain pass the same round-trip gain needs twice the stored
inversion, and each photon round trip extracts half as much. In the analytic
theory the factor $2\sigma$ becomes $p\sigma$ throughout
({func}`~laserdesign.qswitch.q_switch_pulse`,
{func}`~laserdesign.passive_qswitch.passive_q_switch_pulse`), so for the same
inversion ratio $r$ the pulse energy doubles: the ring stores more energy at
threshold. In a passively Q-switched ring the absorber is also crossed once,
$L_{gs} = \ln(1/T_0)$.

## Mode locking

A ring of optical loop length $L$ has repetition rate $c/L$, the same as a
standing-wave cavity with the same round-trip path (one-way length $L/2$). The pulse passes the gain once per round trip, so
the gain saturation energy in the QML condition
({func}`~laserdesign.modelocking.qml_threshold_energy`) is $F_{sat,L}A_L$
instead of $F_{sat,L}A_L/2$, which raises the QML threshold by $\sqrt 2$.
{func}`~laserdesign.modelocking.sesam_design_check` takes `ring=True` for
both.
