# Mode locking

Module: {mod}`laserdesign.modelocking`.
Main references: Siegman, *Lasers*, ch. 27 and 28; Haus, IEEE JSTQE 6, 1173
(2000); Kärtner et al., IEEE JSTQE 2, 540 (1996); Hönninger et al., JOSA B 16,
46 (1999); Paschotta and Keller, Appl. Phys. B 73, 653 (2001).

## Limits set by the gain bandwidth

A transform-limited pulse satisfies $\tau\Delta\nu = K$, with $K = 0.315$
for sech² and $0.441$ for Gaussian pulses. The gain bandwidth therefore sets
a floor: about 1 ps for Nd:YVO4, 2.6 ps for Nd:YAG, 0.2 ps for Yb:YAG and a
few fs for Ti:sapphire.

## Active AM mode locking

In Haus's master-equation treatment the gain filter
($D_g = g/\Omega_g^2$, with $g$ the saturated round-trip amplitude gain and
$\Omega_g = \pi\Delta\nu_g$) balances the pulse shortening by a modulator of
depth $M$ at $\omega_m = 2\pi f_m$, giving a Gaussian pulse with

$$
\tau_a^4 = \frac{D_g}{M\omega_m^2/2}, \qquad \tau_{FWHM} = 1.665\,\tau_a.
$$

This is the Kuizenga-Siegman result
$\tau = (\sqrt{2\ln2}/\pi)(g/\delta_m)^{1/4}(f_m\Delta\nu)^{-1/2}$, and the
quarter-power dependence on modulation depth is why active mode locking
rarely gives pulses much below 10 to 100 ps in Nd lasers.

## Soliton mode locking

With negative net group delay dispersion and self-phase modulation in the
crystal, a sech² soliton forms whose width is set by the dispersion and the
pulse energy,

$$
\tau_{FWHM} = 1.763\,\frac{2|GDD|}{\delta_{SPM}E_p}, \qquad
\delta_{SPM} = 2\cdot\frac{2\pi}{\lambda}\frac{n_2 l}{\pi w^2}.
$$

{func}`~laserdesign.modelocking.soliton_required_gdd` inverts this to give the
dispersion compensation needed for a target pulse width.

## SESAM mode locking and the QML limit

A semiconductor saturable absorber mirror starts and stabilises mode locking.
Because solid state gain media store energy for a long time, the laser can
instead Q-switch while mode locking (QML). CW mode locking is stable when the
intracavity pulse energy exceeds

$$
E_{p,c} = \sqrt{E_{sat,L}\,E_{sat,A}\,\Delta R},
$$

with $E_{sat,L} = (h\nu/(m\sigma))\pi w_L^2$ ($m = 2$ gain passes per round
trip in a standing-wave cavity), $E_{sat,A} = F_{sat,A}\pi w_A^2$ and $\Delta R$
the modulation depth. The design levers are a longer cavity (more energy per
pulse), a smaller mode on the SESAM and a smaller mode in the gain, and a
SESAM with lower saturation fluence or modulation depth. The SESAM should be
saturated three to five times ($E_p/E_{sat,A} \approx 3$ to 5) for good
performance without damage.

Without soliton shaping the pulse width is roughly
$\tau \approx (1.07/\Delta\nu_g)\sqrt{g/\Delta R}$ (Paschotta and Keller
2001). This is an order-of-magnitude guide.

{func}`~laserdesign.modelocking.sesam_design_check` evaluates all of these at
once for a standing-wave cavity with the SESAM as an end mirror.

## Not yet included

Kerr-lens mode locking (which needs the intensity-dependent lens in the
resonator model), FM mode locking and full pulse simulations.
