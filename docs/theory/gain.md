# Gain, threshold and CW output

Module: {mod}`laserdesign.gain`.
Main references: Milonni and Eberly, *Laser Physics*, ch. 4 and 5; Siegman,
*Lasers*, ch. 12 and 13; Koechner ch. 3; Moulton, IEEE JQE 21, 1582 (1985);
Risk, JOSA B 5, 1412 (1988); Fan and Byer, IEEE JQE 23, 605 (1987).

## Rate equations

For a four-level laser with pump rate $R_p$, the upper-state density obeys

$$
\frac{dN_2}{dt} = R_p - \frac{N_2}{\tau} - \frac{\sigma_e I}{h\nu}N_2 .
$$

Quasi-three-level media (Yb:YAG) also absorb at the laser wavelength from the
thermally populated lower level. Writing $N_1 = N_0 - N_2$, the gain
coefficient becomes $(\sigma_e + \sigma_a)N_2 - \sigma_a N_0$, so threshold
needs extra inversion to overcome the reabsorption $2\sigma_a N_0 l$ per round
trip, and the saturation intensity is $h\nu/((\sigma_e+\sigma_a)\tau)$.

## Threshold with Gaussian beams

For a Gaussian pump of radius $w_p$ and TEM00 mode $w_l$, integrating the
small-signal gain over the mode gives

$$
P_{th} = \frac{\pi h\nu_p (w_l^2 + w_p^2)}{4(\sigma_e+\sigma_a)\tau\eta_q\eta_{abs}}\,(\delta + 2\sigma_a N_0 l).
$$

Low threshold therefore needs small, well-matched beams, a long lifetime and a
large cross section. Nd:YVO4 has a lower threshold than Nd:YAG mainly because
of its larger $\sigma_e\tau$ product.

## Above threshold

{func}`~laserdesign.gain.end_pumped_cw` finds the circulating power $P$ at
which the saturated round-trip gain equals the loss. With the standing-wave
intensity $2Ps_0(r)$ (no spatial hole burning) and pump absorbed within the
crystal, the length-integrated upper-state density per unit area is

$$
\bar N_2(r) = \frac{\eta_q P_{abs}\,r_p(r)\,\tau/h\nu_p + \sigma_a N_0 l\,\tau I(r)/h\nu}{1 + (\sigma_e+\sigma_a)\tau I(r)/h\nu},
$$

and the gain condition is
$2\int[(\sigma_e+\sigma_a)\bar N_2 - \sigma_a N_0 l]s_0\,dA = \delta$, solved by
root finding. Output power is $TP$. This reproduces the threshold formula
exactly and gives the slope efficiency including pump/mode overlap:

- when $w_p \ll w_l$ the slope approaches the ideal
  $\eta_{abs}\eta_q(\lambda_p/\lambda_l)T/\delta$;
- when $w_p > w_l$ pump light in the wings is wasted and the slope drops.

## Plane-wave results (Rigrod)

For uniform beams and low gain, $I_{out} = (T I_{sat}/2)(G_0/(T+L) - 1)$,
which is maximised at $T_{opt} = \sqrt{G_0 L} - L$ (Siegman sec. 12.2). These
are useful for quick estimates and for understanding the trade-off between
output coupling and passive loss.

## Assumptions and limits

- Steady state, no spatial hole burning, no pump saturation or bleaching.
- Pump and mode radii are constant along the crystal (use the
  absorption-weighted pump radius when they are not).
- Quasi-three-level treatment assumes the ground-state population is not
  strongly depleted, which can overestimate reabsorption under very intense
  pumping.
