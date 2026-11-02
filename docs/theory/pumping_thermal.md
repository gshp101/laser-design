# Pump absorption and thermal effects

Modules: {mod}`laserdesign.pump`, {mod}`laserdesign.thermal`.
Main references: Koechner, *Solid-State Laser Engineering*, ch. 6 and 7;
Innocenzi et al., Appl. Phys. Lett. 56, 1831 (1990); Milonni and Eberly,
*Laser Physics*, sec. 7.2.

## Absorption

Pump power decays as $P(z) = P_0 e^{-\alpha z}$ with
$\alpha = \sigma_{abs} N$. The absorbed fraction for a crystal of length
$l$ is $1 - e^{-\alpha l}$, or $(1 - e^{-\alpha l})(1 + R e^{-\alpha l})$ when
the transmitted pump is reflected back. The database value of $\alpha$ is the
narrow-linewidth peak; diode pumps with a few nm of bandwidth, or a
temperature-tuned diode off the peak, see a lower effective value, which can
be supplied directly with `effective_absorption` in
{class}`~laserdesign.design.EndPumpedLaser`.

## Pump beam size

Focused diode light is treated as an embedded Gaussian of quality $M_p^2$
(fibre-coupled diodes are typically 20 to 200). Inside the crystal its radius
is $w_p(z) = w_{p0}\sqrt{1 + ((z - z_0)/z_R)^2}$ with
$z_R = \pi n w_{p0}^2/(M_p^2\lambda_p)$. Where the pump diverges noticeably,
the threshold and thermal lens depend on the absorption-weighted radius

$$
\bar w_p^2 = \frac{\int_0^l w_p^2(z)\,\alpha e^{-\alpha z}\,dz}{\int_0^l \alpha e^{-\alpha z}\,dz}.
$$

## Heat load

A fraction $\xi$ of the absorbed power becomes heat. The quantum defect
$1 - \lambda_p/\lambda_l$ is the lower bound; Nd media are higher (about 0.32
in Nd:YAG and 0.24 in Nd:YVO4 under 808 nm pumping) because of
concentration quenching and other non-radiative channels. The database stores
measured values where available.

## Temperature profile and thermal lens for end pumping

For a Gaussian heat source in a barrel-cooled rod of radius $r_0$, the heat
equation gives

$$
T(r) - T(r_0) = \frac{P_h}{4\pi K l}\left[F\!\left(\frac{2r_0^2}{w_p^2}\right) - F\!\left(\frac{2r^2}{w_p^2}\right)\right],
\qquad F(x) = \gamma + \ln x + E_1(x).
$$

Near the axis $F(x) \approx x$, the profile is parabolic and the integrated
optical path difference is that of a thin lens with

$$
f_{th} = \frac{\pi K w_p^2}{P_h\,\chi}, \qquad \chi = \frac{dn}{dT} + \ldots
$$

The library uses $\chi = dn/dT$ by default. End-face bulging and the
photo-elastic effect add to $\chi$; their size depends on the crystal mount and
pump geometry, so they are left as an `extra_coefficient` the user can fit to
a measured lens.

Outside the pumped region the profile is logarithmic, not parabolic. This
spherical aberration is what degrades beam quality at high power
({doc}`beam_quality`).

## Uniformly side-pumped rods

For uniform heating the temperature is exactly parabolic,
$\Delta T_{centre} = P_h/(4\pi K l)$, and (Koechner eq. 7.41)

$$
f = \frac{KA}{P_h}\left(\frac12\frac{dn}{dT} + \alpha_T C_{r,\phi} n_0^3 + \frac{\alpha_T r_0(n_0-1)}{l}\right)^{-1}.
$$

The stress term differs for radial and tangential polarisation
($C_r \neq C_\phi$), which is the origin of bifocusing in Nd:YAG rods.

## Fracture limit

A uniformly pumped rod fractures when the heat load per unit length reaches
$P_h/l = 8\pi R_T$, with $R_T$ the thermal shock parameter. Design to a
quarter to a half of this value.
