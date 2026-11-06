# Materials database

`laserdesign.materials.MATERIALS` holds twenty common solid state gain media.
The Qt wizard and the browser version list all of them on the **Gain medium**
step, and the library looks them up by key with
`get_material("Nd:GdVO4")` (case-insensitive).

The numbers are typical room-temperature literature values for the polarisation
and pump line named. Crystals from different growers, glasses of different
composition and different doping levels vary, often by tens of percent, and
diode pump absorption depends on the diode spectrum. Treat the entries as
starting points: edit them on the Gain medium step, or use
`GainMedium.replace(...)` in Python, with the values from your crystal's data
sheet.

## Summary

| Key | Material | λ laser [nm] | λ pump [nm] | σ<sub>e</sub> [10⁻²⁰ cm²] | τ [µs] | n | dn/dT [10⁻⁶/K] | k [W/(m·K)] | Doping unit |
|---|---|---|---|---|---|---|---|---|---|
| `nd:yag` | Nd:YAG | 1064 | 809 | 28 | 230 | 1.82 | +7.3 | 14 | at.% |
| `nd:yvo4` | Nd:YVO4 (a-cut, pi-pol.) | 1064 | 809 | 156 | 100 | 2.17 | +3 | 5.23 | at.% |
| `nd:gdvo4` | Nd:GdVO4 (a-cut, pi-pol.) | 1063 | 808 | 76 | 95 | 2.19 | +4.7 | 11.7 | at.% |
| `nd:ylf 1047` | Nd:YLF 1047 nm (pi-pol.) | 1047 | 806 | 18 | 485 | 1.47 | -4.3 | 6.3 | at.% |
| `nd:ylf 1053` | Nd:YLF 1053 nm (sigma-pol.) | 1053 | 806 | 12 | 485 | 1.45 | -2 | 6.3 | at.% |
| `nd:glass` | Nd:phosphate glass (LHG-8 type) | 1054 | 802 | 3.6 | 365 | 1.52 | -5.3 | 0.58 | 1e20/cm³ |
| `yb:yag` | Yb:YAG | 1030 | 940 | 2.1 | 951 | 1.82 | +7.3 | 11 | at.% |
| `yb:kgw` | Yb:KGW (E || Nm) | 1030 | 981 | 2.2 | 600 | 2.03 | -11.8 | 3.3 | at.% |
| `yb:kyw` | Yb:KYW (E || Nm) | 1030 | 981 | 2.5 | 700 | 2.04 | -11.8 | 3.3 | at.% |
| `yb:glass` | Yb:phosphate glass | 1030 | 975 | 0.5 | 1.6e+03 | 1.53 | -4 | 0.85 | 1e20/cm³ |
| `yb:caf2` | Yb:CaF2 | 1030 | 980 | 0.25 | 2.4e+03 | 1.43 | -11.3 | 6.5 | at.% |
| `yb:lu2o3` | Yb:Lu2O3 | 1034 | 976 | 1.26 | 820 | 1.91 | +9.1 | 11 | at.% |
| `ti:sapphire` | Ti:sapphire | 800 | 532 | 30 | 3.2 | 1.76 | +12 | 33 | wt.% |
| `cr:lisaf` | Cr:LiSAF (pi-pol.) | 850 | 670 | 4.8 | 67 | 1.41 | -4 | 3.1 | mol.% |
| `cr:forsterite` | Cr:forsterite | 1250 | 1064 | 14.4 | 2.7 | 1.63 | +9 | 8 | 1e18/cm³ |
| `alexandrite` | Alexandrite (Cr:BeAl2O4, E || b) | 755 | 680 | 0.7 | 260 | 1.74 | +8.3 | 23 | at.% |
| `cr:znse` | Cr:ZnSe | 2400 | 1908 | 130 | 5.4 | 2.44 | +70 | 18 | 1e18/cm³ |
| `er:yag` | Er:YAG 1645 nm (in-band pumped) | 1645 | 1532 | 0.3 | 6.8e+03 | 1.8 | +8 | 13 | at.% |
| `tm:yag` | Tm:YAG | 2013 | 785 | 0.22 | 1e+04 | 1.8 | +7.3 | 11 | at.% |
| `ho:yag` | Ho:YAG (Tm-fibre pumped) | 2090 | 1908 | 1.1 | 7.8e+03 | 1.8 | +7.3 | 13 | at.% |

Quasi-three-level media (all Yb media, Er:YAG, Tm:YAG and Ho:YAG) also carry a
ground-state absorption cross section at the laser wavelength, which the
threshold and output models use for reabsorption. Every entry also has the
pump absorption cross section, ion density per unit doping, gain bandwidth,
thermal expansion, and where known the heat fraction, n₂ and GVD; see
{doc}`api/materials` for the full list of fields.

## Modelling notes

- **Doping units.** Crystals use at.% (mol.% for Cr:LiSAF). Glasses use the
  Nd or Yb density in units of 10²⁰ cm⁻³, and Cr:forsterite and Cr:ZnSe the
  Cr density in units of 10¹⁸ cm⁻³, because their doping is usually quoted
  that way or as an absorption coefficient. To use a measured absorption
  coefficient instead, enter it on the Pump step.
- **Negative dn/dT.** Nd:YLF, the glasses, Yb:KGW, Yb:KYW, Yb:CaF2 and
  Cr:LiSAF have dn/dT < 0. The end-pumped thermal lens model uses the dn/dT
  term only, so it predicts a diverging lens for them. In practice end-face
  bulging and stress often make the net lens weak or even positive (Nd:YLF is
  the classic case). If you have a measured thermal lens, enter an effective
  dn/dT that reproduces it. The side-pumped rod model includes the stress and
  bulging terms (Koechner eq. 7.41).
- **Two-for-one pumping.** Tm:YAG has a quantum efficiency of 1.8 from
  cross-relaxation at 4 to 6 at.% doping, and an explicit heat fraction of
  0.30. Use a quantum efficiency near 1 for low doping.
- **Temperature-dependent media.** Cr:LiSAF and alexandrite change strongly
  with temperature (thermal quenching of the lifetime, and in alexandrite a
  rising cross section). The entries are room-temperature values.
- **Not included.** Sensitised media such as Er,Yb:glass, where one ion
  absorbs the pump and another lases, do not fit the single-ion
  `GainMedium` model; nor do flashlamp-pumped media whose absorption is a
  broadband spectrum, such as Cr,Nd:GSGG.

## Sources and remarks

- **Nd:YAG:** Koechner (2006) Table 2.2; heat fraction from Fan (1993).
- **Nd:YVO4 (a-cut, pi-pol.):** Koechner (2006) Table 2.10. Emission cross section values in the literature range from 15e-19 to 25e-19 cm^2.
- **Nd:GdVO4 (a-cut, pi-pol.):** Jensen et al., Appl. Phys. B 58, 373 (1994); Zagumennyi et al. (1992); Koechner (2006) sec. 2.3. k is the <110> value; the lifetime falls above 1 at.%.
- **Nd:YLF 1047 nm (pi-pol.):** Koechner (2006) Table 2.8; Harmer et al., J. Phys. Chem. Solids 30, 1483 (1969). Uniaxial: e-ray values. Negative dn/dT is largely cancelled by end-face bulging, so the net lens is weak.
- **Nd:YLF 1053 nm (sigma-pol.):** Koechner (2006) Table 2.8. Uniaxial: o-ray values. 1053 nm matches Nd:phosphate glass amplifiers.
- **Nd:phosphate glass (LHG-8 type):** Hoya LHG-8 data; Koechner (2006) Table 2.6; Campbell & Suratwala, J. Non-Cryst. Solids 263, 318 (2000). Lifetime is the low-doping value; it shortens by concentration quenching. Low k: thermal limits come early in CW.
- **Yb:YAG:** Quasi-three-level. Cross sections after Koechner (2006) Table 2.9 and Fan & Byer; laser_absorption_cross_section is the effective room-temperature reabsorption at 1030 nm.
- **Yb:KGW (E || Nm):** Kuleshov et al., Opt. Lett. 22, 1317 (1997); Major et al. (2003) for n2. Biaxial: values for E || Nm. The 981 nm zero-phonon line is only ~3.5 nm wide, so a wavelength-stabilised diode is needed.
- **Yb:KYW (E || Nm):** Kuleshov et al., Opt. Lett. 22, 1317 (1997); Klopp et al. (2002). Thermal and Kerr values taken equal to KGW; KYW accepts 100 % Yb.
- **Yb:phosphate glass:** Kigre QX/Yb data; Hönninger et al., Opt. Lett. 20, 2402 (1995). Glass composition changes these values by tens of percent.
- **Yb:CaF2:** Petit et al., Opt. Lett. 33, 1145 (2008); Siebold et al., Appl. Phys. B 97, 327 (2009). k is for ~3 at.% (9.7 undoped).
- **Yb:Lu2O3:** Peters et al., Opt. Express 15, 7075 (2007); Petermann et al. (2000). k is for ~3 at.% (12.5 undoped). 976 nm line is ~3 nm wide.
- **Ti:sapphire:** Moulton (1986); Koechner (2006) Table 2.13.
- **Cr:LiSAF (pi-pol.):** Payne et al., IEEE JQE 24, 2243 (1988) and JQE 28, 1188 (1992); Koechner (2006) sec. 2.4. The lifetime drops steeply above ~50 °C (thermal quenching), which caps the pump power.
- **Cr:forsterite:** Petričević et al., Appl. Phys. Lett. 52, 1040 (1988); Sennaroglu (ed.), Solid-State Lasers and Applications (2007) ch. 4. Usually specified by its 1064 nm absorption; enter that on the pump step.
- **Alexandrite (Cr:BeAl2O4, E || b):** Walling et al., IEEE JQE 16, 1302 (1980); Koechner (2006) sec. 2.4. Effective room-temperature values: sigma_e rises and tau falls as the crystal is heated.
- **Cr:ZnSe:** Page et al., IEEE JQE 33, 609 (1997); Mirov et al., IEEE JSTQE 21, 1601719 (2015). The very large dn/dT gives a strong thermal lens.
- **Er:YAG 1645 nm (in-band pumped):** Eichhorn, Appl. Phys. B 93, 773 (2008); Setzler et al., IEEE JSTQE 11, 645 (2005). Small quantum defect (~7 %); upconversion grows above ~0.5 at.%.
- **Tm:YAG:** Fan et al., IEEE JQE 24, 924 (1988); Koechner (2006) sec. 2.3. Quantum efficiency 1.8 assumes cross-relaxation at ~4-6 at.%; use ~1 at low doping.
- **Ho:YAG (Tm-fibre pumped):** Budni et al., JOSA B 17, 723 (2000); Payne et al., IEEE JQE 28, 2619 (1992). In-band pumped at 1908 nm; quantum defect ~9 %.

The values for the media added after version 0.2.0 were entered from the cited
literature without the papers at hand. Check them against the source, or your
crystal supplier's data sheet, before relying on them in a design.
