"""Gain media and their spectroscopic, thermal and optical properties.

A :class:`GainMedium` collects every material number the rest of the
library needs. Twenty common media are predefined (Nd, Yb, Ti, Cr, Er, Tm
and Ho doped crystals and glasses, see :data:`MATERIALS` and
``docs/materials.md``) and can be looked up by name with
:func:`get_material`. All values are in SI units.

The predefined values are typical room-temperature literature values
(Koechner, *Solid-State Laser Engineering*, 6th ed.; Siegman, *Lasers*;
manufacturer data sheets). Real crystals vary, and pump absorption in
particular depends strongly on the diode linewidth and wavelength, so treat
them as starting points and override them with measured data where you have
it, for example with :meth:`GainMedium.replace`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from . import units as u


@dataclass(frozen=True)
class GainMedium:
    """Material parameters of a solid state gain medium.

    Parameters
    ----------
    name : str
        Human-readable name.
    laser_wavelength : float
        Vacuum laser wavelength [m].
    pump_wavelength : float
        Vacuum pump wavelength [m].
    emission_cross_section : float
        Stimulated emission cross section at the laser wavelength [m^2].
    upper_state_lifetime : float
        Fluorescence lifetime of the upper laser level [s].
    refractive_index : float
        Refractive index at the laser wavelength.
    dn_dT : float
        Thermo-optic coefficient [1/K] for the laser polarisation.
    thermal_conductivity : float
        Thermal conductivity [W/(m K)].
    thermal_expansion : float
        Linear thermal expansion coefficient [1/K].
    pump_absorption_cross_section : float
        Absorption cross section at the pump wavelength [m^2].
    ion_density_per_unit_doping : float
        Active-ion density per unit of ``doping_unit`` [1/m^3].
    doping_unit : str
        Unit the doping level is quoted in, e.g. ``"at.%"`` or ``"wt.%"``.
    gain_bandwidth : float
        FWHM gain bandwidth [Hz].
    laser_absorption_cross_section : float
        Ground-state absorption cross section at the laser wavelength [m^2].
        Zero for a true four-level system; non-zero for quasi-three-level
        media such as Yb:YAG.
    pump_emission_cross_section : float
        Stimulated emission cross section at the pump wavelength [m^2]
        (quasi-three-level media only).
    quantum_efficiency : float
        Fluorescence quantum efficiency of the pump-to-upper-level process.
    heat_fraction : float or None
        Fraction of absorbed pump power converted to heat. ``None`` means
        use the quantum defect ``1 - lambda_p / lambda_l``.
    nonlinear_index : float
        Kerr coefficient n2 [m^2/W].
    gvd : float or None
        Group velocity dispersion at the laser wavelength [s^2/m]
        (``1 fs^2/mm = 1e-27 s^2/m``), or ``None`` if not tabulated.
    poisson_ratio : float
        Poisson's ratio (used for thermal stress estimates).
    thermal_shock_parameter : float or None
        Thermal shock resistance R_T [W/m] used for the fracture limit.
    notes : str
        Free-form remarks on where the numbers come from.
    """

    name: str
    laser_wavelength: float
    pump_wavelength: float
    emission_cross_section: float
    upper_state_lifetime: float
    refractive_index: float
    dn_dT: float
    thermal_conductivity: float
    thermal_expansion: float
    pump_absorption_cross_section: float
    ion_density_per_unit_doping: float
    doping_unit: str = "at.%"
    gain_bandwidth: float = 0.0
    laser_absorption_cross_section: float = 0.0
    pump_emission_cross_section: float = 0.0
    quantum_efficiency: float = 1.0
    heat_fraction: float | None = None
    nonlinear_index: float = 0.0
    gvd: float | None = None
    poisson_ratio: float = 0.25
    thermal_shock_parameter: float | None = None
    notes: str = field(default="", compare=False)

    # ------------------------------------------------------------------ #
    # Derived quantities
    # ------------------------------------------------------------------ #
    @property
    def laser_photon_energy(self) -> float:
        """Photon energy at the laser wavelength [J]."""
        return u.photon_energy(self.laser_wavelength)

    @property
    def pump_photon_energy(self) -> float:
        """Photon energy at the pump wavelength [J]."""
        return u.photon_energy(self.pump_wavelength)

    @property
    def quantum_defect(self) -> float:
        """Stokes efficiency ``lambda_p / lambda_l``."""
        return self.pump_wavelength / self.laser_wavelength

    @property
    def effective_heat_fraction(self) -> float:
        """Fraction of absorbed pump power deposited as heat.

        Returns :attr:`heat_fraction` if set, otherwise the quantum-defect
        value ``1 - lambda_p / lambda_l``.
        """
        if self.heat_fraction is not None:
            return self.heat_fraction
        return 1.0 - self.quantum_defect

    @property
    def is_quasi_three_level(self) -> bool:
        """True when the laser transition has ground-state reabsorption."""
        return self.laser_absorption_cross_section > 0.0

    @property
    def saturation_fluence(self) -> float:
        """Gain saturation fluence ``h nu / (sigma_e + sigma_a)`` [J/m^2]."""
        return self.laser_photon_energy / (
            self.emission_cross_section + self.laser_absorption_cross_section
        )

    @property
    def saturation_intensity(self) -> float:
        """Gain saturation intensity ``h nu / ((sigma_e + sigma_a) tau)`` [W/m^2]."""
        return self.saturation_fluence / self.upper_state_lifetime

    def ion_density(self, doping: float) -> float:
        """Active-ion density for a given doping level [1/m^3].

        Parameters
        ----------
        doping : float
            Doping in :attr:`doping_unit`.
        """
        return doping * self.ion_density_per_unit_doping

    def pump_absorption_coefficient(self, doping: float) -> float:
        """Small-signal pump absorption coefficient ``alpha = sigma_a N`` [1/m].

        This is the unsaturated, narrow-linewidth value. Diode pumps with a
        broad spectrum usually see a lower effective value.

        Parameters
        ----------
        doping : float
            Doping in :attr:`doping_unit`.
        """
        return self.pump_absorption_cross_section * self.ion_density(doping)

    def replace(self, **changes) -> GainMedium:
        """Return a copy with some parameters changed.

        Examples
        --------
        >>> from laserdesign.materials import ND_YAG
        >>> my_yag = ND_YAG.replace(thermal_conductivity=13.0)
        """
        return dataclasses.replace(self, **changes)


ND_YAG = GainMedium(
    name="Nd:YAG",
    laser_wavelength=1064.2 * u.nm,
    pump_wavelength=808.5 * u.nm,
    emission_cross_section=2.8e-19 * u.cm2,
    upper_state_lifetime=230 * u.us,
    refractive_index=1.82,
    dn_dT=7.3e-6,
    thermal_conductivity=14.0,
    thermal_expansion=7.5e-6,
    # ~7.1 /cm per at.% at the 808.5 nm peak for a narrow-band pump.
    pump_absorption_cross_section=5.1e-20 * u.cm2,
    ion_density_per_unit_doping=1.38e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=120 * u.GHz,
    heat_fraction=0.32,
    nonlinear_index=6.2e-20,
    gvd=73e-27,
    poisson_ratio=0.25,
    thermal_shock_parameter=790.0,
    notes="Koechner (2006) Table 2.2; heat fraction from Fan (1993).",
)

ND_YVO4 = GainMedium(
    name="Nd:YVO4 (a-cut, pi-pol.)",
    laser_wavelength=1064.3 * u.nm,
    pump_wavelength=808.5 * u.nm,
    emission_cross_section=15.6e-19 * u.cm2,
    upper_state_lifetime=100 * u.us,
    refractive_index=2.165,
    dn_dT=3.0e-6,
    thermal_conductivity=5.23,
    thermal_expansion=4.43e-6,
    # ~31 /cm per at.% for pi-polarised pump at 808.5 nm.
    pump_absorption_cross_section=2.5e-19 * u.cm2,
    ion_density_per_unit_doping=1.26e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=257 * u.GHz,
    heat_fraction=0.24,
    nonlinear_index=15e-20,
    gvd=None,
    poisson_ratio=0.33,
    thermal_shock_parameter=None,
    notes=(
        "Koechner (2006) Table 2.10. Emission cross section values in the "
        "literature range from 15e-19 to 25e-19 cm^2."
    ),
)

YB_YAG = GainMedium(
    name="Yb:YAG",
    laser_wavelength=1030 * u.nm,
    pump_wavelength=940 * u.nm,
    emission_cross_section=2.1e-20 * u.cm2,
    upper_state_lifetime=951 * u.us,
    refractive_index=1.82,
    dn_dT=7.3e-6,
    thermal_conductivity=11.0,
    thermal_expansion=7.5e-6,
    pump_absorption_cross_section=0.8e-20 * u.cm2,
    ion_density_per_unit_doping=1.38e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=1.8 * u.THz,
    laser_absorption_cross_section=0.12e-20 * u.cm2,
    pump_emission_cross_section=0.16e-20 * u.cm2,
    heat_fraction=None,
    nonlinear_index=6.2e-20,
    gvd=76e-27,
    poisson_ratio=0.25,
    thermal_shock_parameter=790.0,
    notes=(
        "Quasi-three-level. Cross sections after Koechner (2006) Table 2.9 "
        "and Fan & Byer; laser_absorption_cross_section is the effective "
        "room-temperature reabsorption at 1030 nm."
    ),
)

TI_SAPPHIRE = GainMedium(
    name="Ti:sapphire",
    laser_wavelength=800 * u.nm,
    pump_wavelength=532 * u.nm,
    emission_cross_section=3.0e-19 * u.cm2,
    upper_state_lifetime=3.2 * u.us,
    refractive_index=1.76,
    dn_dT=12e-6,
    thermal_conductivity=33.0,
    thermal_expansion=5.0e-6,
    pump_absorption_cross_section=6.4e-20 * u.cm2,
    # 0.1 wt.% Ti2O3 is about 3.3e19 /cm^3.
    ion_density_per_unit_doping=3.3e20 / u.cm3,
    doping_unit="wt.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(230 * u.nm, 800 * u.nm),
    heat_fraction=None,
    nonlinear_index=3.2e-20,
    gvd=58e-27,
    poisson_ratio=0.25,
    thermal_shock_parameter=None,
    notes="Moulton (1986); Koechner (2006) Table 2.13.",
)

# ---------------------------------------------------------------------- #
# Further neodymium media
# ---------------------------------------------------------------------- #
ND_GDVO4 = GainMedium(
    name="Nd:GdVO4 (a-cut, pi-pol.)",
    laser_wavelength=1063.1 * u.nm,
    pump_wavelength=808.4 * u.nm,
    emission_cross_section=7.6e-19 * u.cm2,
    upper_state_lifetime=95 * u.us,
    refractive_index=2.19,
    dn_dT=4.7e-6,
    thermal_conductivity=11.7,
    thermal_expansion=1.5e-6,
    # ~57 /cm per at.% for pi-polarised narrow-band pump at 808 nm.
    pump_absorption_cross_section=4.7e-19 * u.cm2,
    ion_density_per_unit_doping=1.21e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(1.0 * u.nm, 1063.1 * u.nm),
    poisson_ratio=0.33,
    notes=(
        "Jensen et al., Appl. Phys. B 58, 373 (1994); Zagumennyi et al. (1992); "
        "Koechner (2006) sec. 2.3. k is the <110> value; the lifetime falls "
        "above 1 at.%."
    ),
)

ND_YLF_1047 = GainMedium(
    name="Nd:YLF 1047 nm (pi-pol.)",
    laser_wavelength=1047 * u.nm,
    pump_wavelength=806 * u.nm,
    emission_cross_section=1.8e-19 * u.cm2,
    upper_state_lifetime=485 * u.us,
    refractive_index=1.470,
    dn_dT=-4.3e-6,
    thermal_conductivity=6.3,
    thermal_expansion=13e-6,
    # ~6 /cm per at.% at 806 nm (pi); 797 nm absorbs about twice as strongly.
    pump_absorption_cross_section=0.43e-19 * u.cm2,
    ion_density_per_unit_doping=1.40e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(1.35 * u.nm, 1047 * u.nm),
    poisson_ratio=0.33,
    notes=(
        "Koechner (2006) Table 2.8; Harmer et al., J. Phys. Chem. Solids 30, "
        "1483 (1969). Uniaxial: e-ray values. Negative dn/dT is largely "
        "cancelled by end-face bulging, so the net lens is weak."
    ),
)

ND_YLF_1053 = ND_YLF_1047.replace(
    name="Nd:YLF 1053 nm (sigma-pol.)",
    laser_wavelength=1053 * u.nm,
    emission_cross_section=1.2e-19 * u.cm2,
    refractive_index=1.448,
    dn_dT=-2.0e-6,
    gain_bandwidth=u.bandwidth_nm_to_hz(1.3 * u.nm, 1053 * u.nm),
    notes=(
        "Koechner (2006) Table 2.8. Uniaxial: o-ray values. 1053 nm matches "
        "Nd:phosphate glass amplifiers."
    ),
)

ND_GLASS = GainMedium(
    name="Nd:phosphate glass (LHG-8 type)",
    laser_wavelength=1054 * u.nm,
    pump_wavelength=802 * u.nm,
    emission_cross_section=3.6e-20 * u.cm2,
    upper_state_lifetime=365 * u.us,
    refractive_index=1.52,
    dn_dT=-5.3e-6,
    thermal_conductivity=0.58,
    thermal_expansion=11.2e-6,
    pump_absorption_cross_section=1.2e-20 * u.cm2,
    # Doping given directly as Nd density in units of 1e20 /cm^3.
    ion_density_per_unit_doping=1e20 / u.cm3,
    doping_unit="1e20/cm³",
    gain_bandwidth=u.bandwidth_nm_to_hz(22 * u.nm, 1054 * u.nm),
    nonlinear_index=3.0e-20,
    poisson_ratio=0.24,
    notes=(
        "Hoya LHG-8 data; Koechner (2006) Table 2.6; Campbell & Suratwala, "
        "J. Non-Cryst. Solids 263, 318 (2000). Lifetime is the low-doping "
        "value; it shortens by concentration quenching. Low k: thermal limits "
        "come early in CW."
    ),
)

# ---------------------------------------------------------------------- #
# Ytterbium media (quasi-three-level)
# ---------------------------------------------------------------------- #
YB_KGW = GainMedium(
    name="Yb:KGW (E || Nm)",
    laser_wavelength=1030 * u.nm,
    pump_wavelength=981 * u.nm,
    emission_cross_section=2.2e-20 * u.cm2,
    upper_state_lifetime=600 * u.us,
    refractive_index=2.03,
    dn_dT=-11.8e-6,
    thermal_conductivity=3.3,
    thermal_expansion=4.0e-6,
    pump_absorption_cross_section=12e-20 * u.cm2,
    ion_density_per_unit_doping=0.63e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(20 * u.nm, 1030 * u.nm),
    laser_absorption_cross_section=0.2e-20 * u.cm2,
    pump_emission_cross_section=12e-20 * u.cm2,
    nonlinear_index=15e-20,
    notes=(
        "Kuleshov et al., Opt. Lett. 22, 1317 (1997); Major et al. (2003) for "
        "n2. Biaxial: values for E || Nm. The 981 nm zero-phonon line is only "
        "~3.5 nm wide, so a wavelength-stabilised diode is needed."
    ),
)

YB_KYW = YB_KGW.replace(
    name="Yb:KYW (E || Nm)",
    emission_cross_section=2.5e-20 * u.cm2,
    upper_state_lifetime=700 * u.us,
    refractive_index=2.04,
    pump_absorption_cross_section=13.3e-20 * u.cm2,
    pump_emission_cross_section=13.3e-20 * u.cm2,
    ion_density_per_unit_doping=0.64e20 / u.cm3,
    gain_bandwidth=u.bandwidth_nm_to_hz(24 * u.nm, 1030 * u.nm),
    notes=(
        "Kuleshov et al., Opt. Lett. 22, 1317 (1997); Klopp et al. (2002). "
        "Thermal and Kerr values taken equal to KGW; KYW accepts 100 % Yb."
    ),
)

YB_GLASS = GainMedium(
    name="Yb:phosphate glass",
    laser_wavelength=1030 * u.nm,
    pump_wavelength=975 * u.nm,
    emission_cross_section=0.5e-20 * u.cm2,
    upper_state_lifetime=1.6 * u.ms,
    refractive_index=1.53,
    dn_dT=-4.0e-6,
    thermal_conductivity=0.85,
    thermal_expansion=10e-6,
    pump_absorption_cross_section=1.1e-20 * u.cm2,
    ion_density_per_unit_doping=1e20 / u.cm3,
    doping_unit="1e20/cm³",
    gain_bandwidth=u.bandwidth_nm_to_hz(35 * u.nm, 1030 * u.nm),
    laser_absorption_cross_section=0.05e-20 * u.cm2,
    pump_emission_cross_section=1.1e-20 * u.cm2,
    nonlinear_index=3.0e-20,
    poisson_ratio=0.25,
    notes=(
        "Kigre QX/Yb data; Hönninger et al., Opt. Lett. 20, 2402 (1995). "
        "Glass composition changes these values by tens of percent."
    ),
)

YB_CAF2 = GainMedium(
    name="Yb:CaF2",
    laser_wavelength=1030 * u.nm,
    pump_wavelength=980 * u.nm,
    emission_cross_section=0.25e-20 * u.cm2,
    upper_state_lifetime=2.4 * u.ms,
    refractive_index=1.43,
    dn_dT=-11.3e-6,
    thermal_conductivity=6.5,
    thermal_expansion=18.9e-6,
    pump_absorption_cross_section=0.54e-20 * u.cm2,
    ion_density_per_unit_doping=2.45e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(30 * u.nm, 1030 * u.nm),
    laser_absorption_cross_section=0.02e-20 * u.cm2,
    pump_emission_cross_section=0.3e-20 * u.cm2,
    nonlinear_index=1.9e-20,
    gvd=18e-27,
    poisson_ratio=0.26,
    notes=(
        "Petit et al., Opt. Lett. 33, 1145 (2008); Siebold et al., Appl. "
        "Phys. B 97, 327 (2009). k is for ~3 at.% (9.7 undoped)."
    ),
)

YB_LU2O3 = GainMedium(
    name="Yb:Lu2O3",
    laser_wavelength=1034 * u.nm,
    pump_wavelength=976 * u.nm,
    emission_cross_section=1.26e-20 * u.cm2,
    upper_state_lifetime=820 * u.us,
    refractive_index=1.91,
    dn_dT=9.1e-6,
    thermal_conductivity=11.0,
    thermal_expansion=6.6e-6,
    pump_absorption_cross_section=3.1e-20 * u.cm2,
    ion_density_per_unit_doping=2.85e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(13 * u.nm, 1034 * u.nm),
    laser_absorption_cross_section=0.05e-20 * u.cm2,
    pump_emission_cross_section=3.1e-20 * u.cm2,
    poisson_ratio=0.3,
    notes=(
        "Peters et al., Opt. Express 15, 7075 (2007); Petermann et al. "
        "(2000). k is for ~3 at.% (12.5 undoped). 976 nm line is ~3 nm wide."
    ),
)

# ---------------------------------------------------------------------- #
# Chromium (vibronic, tunable) media
# ---------------------------------------------------------------------- #
CR_LISAF = GainMedium(
    name="Cr:LiSAF (pi-pol.)",
    laser_wavelength=850 * u.nm,
    pump_wavelength=670 * u.nm,
    emission_cross_section=4.8e-20 * u.cm2,
    upper_state_lifetime=67 * u.us,
    refractive_index=1.41,
    dn_dT=-4.0e-6,
    thermal_conductivity=3.1,
    thermal_expansion=3.6e-6,
    pump_absorption_cross_section=4.5e-20 * u.cm2,
    # Cr3+ on Al sites: 8.5e21 formula units per cm^3.
    ion_density_per_unit_doping=0.85e20 / u.cm3,
    doping_unit="mol.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(180 * u.nm, 850 * u.nm),
    nonlinear_index=0.8e-20,
    notes=(
        "Payne et al., IEEE JQE 24, 2243 (1988) and JQE 28, 1188 (1992); "
        "Koechner (2006) sec. 2.4. The lifetime drops steeply above ~50 °C "
        "(thermal quenching), which caps the pump power."
    ),
)

CR_FORSTERITE = GainMedium(
    name="Cr:forsterite",
    laser_wavelength=1250 * u.nm,
    pump_wavelength=1064 * u.nm,
    emission_cross_section=1.44e-19 * u.cm2,
    upper_state_lifetime=2.7 * u.us,
    refractive_index=1.63,
    dn_dT=9.0e-6,
    thermal_conductivity=8.0,
    thermal_expansion=9.5e-6,
    pump_absorption_cross_section=2.0e-19 * u.cm2,
    # Doping given as Cr4+ density in units of 1e18 /cm^3.
    ion_density_per_unit_doping=1e18 / u.cm3,
    doping_unit="1e18/cm³",
    gain_bandwidth=u.bandwidth_nm_to_hz(170 * u.nm, 1250 * u.nm),
    notes=(
        "Petričević et al., Appl. Phys. Lett. 52, 1040 (1988); Sennaroglu "
        "(ed.), Solid-State Lasers and Applications (2007) ch. 4. Usually "
        "specified by its 1064 nm absorption; enter that on the pump step."
    ),
)

ALEXANDRITE = GainMedium(
    name="Alexandrite (Cr:BeAl2O4, E || b)",
    laser_wavelength=755 * u.nm,
    pump_wavelength=680 * u.nm,
    emission_cross_section=0.7e-20 * u.cm2,
    upper_state_lifetime=260 * u.us,
    refractive_index=1.74,
    dn_dT=8.3e-6,
    thermal_conductivity=23.0,
    thermal_expansion=6.0e-6,
    pump_absorption_cross_section=5.0e-20 * u.cm2,
    # 0.1 at.% Cr (on Al sites) is 3.5e19 /cm^3.
    ion_density_per_unit_doping=3.5e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(100 * u.nm, 755 * u.nm),
    notes=(
        "Walling et al., IEEE JQE 16, 1302 (1980); Koechner (2006) sec. "
        "2.4. Effective room-temperature values: sigma_e rises and tau falls "
        "as the crystal is heated."
    ),
)

CR_ZNSE = GainMedium(
    name="Cr:ZnSe",
    laser_wavelength=2400 * u.nm,
    pump_wavelength=1908 * u.nm,
    emission_cross_section=1.3e-18 * u.cm2,
    upper_state_lifetime=5.4 * u.us,
    refractive_index=2.44,
    dn_dT=70e-6,
    thermal_conductivity=18.0,
    thermal_expansion=7.1e-6,
    pump_absorption_cross_section=0.9e-18 * u.cm2,
    ion_density_per_unit_doping=1e18 / u.cm3,
    doping_unit="1e18/cm³",
    gain_bandwidth=u.bandwidth_nm_to_hz(800 * u.nm, 2400 * u.nm),
    notes=(
        "Page et al., IEEE JQE 33, 609 (1997); Mirov et al., IEEE JSTQE 21, "
        "1601719 (2015). The very large dn/dT gives a strong thermal lens."
    ),
)

# ---------------------------------------------------------------------- #
# Eye-safe and 2 um media
# ---------------------------------------------------------------------- #
ER_YAG = GainMedium(
    name="Er:YAG 1645 nm (in-band pumped)",
    laser_wavelength=1645 * u.nm,
    pump_wavelength=1532 * u.nm,
    emission_cross_section=0.30e-20 * u.cm2,
    upper_state_lifetime=6.8 * u.ms,
    refractive_index=1.80,
    dn_dT=8.0e-6,
    thermal_conductivity=13.0,
    thermal_expansion=7.5e-6,
    pump_absorption_cross_section=0.5e-20 * u.cm2,
    ion_density_per_unit_doping=1.38e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(1.5 * u.nm, 1645 * u.nm),
    laser_absorption_cross_section=0.045e-20 * u.cm2,
    pump_emission_cross_section=0.1e-20 * u.cm2,
    poisson_ratio=0.25,
    notes=(
        "Eichhorn, Appl. Phys. B 93, 773 (2008); Setzler et al., IEEE JSTQE "
        "11, 645 (2005). Small quantum defect (~7 %); upconversion grows "
        "above ~0.5 at.%."
    ),
)

TM_YAG = GainMedium(
    name="Tm:YAG",
    laser_wavelength=2013 * u.nm,
    pump_wavelength=785 * u.nm,
    emission_cross_section=0.22e-20 * u.cm2,
    upper_state_lifetime=10 * u.ms,
    refractive_index=1.80,
    dn_dT=7.3e-6,
    thermal_conductivity=11.0,
    thermal_expansion=7.5e-6,
    pump_absorption_cross_section=0.6e-20 * u.cm2,
    ion_density_per_unit_doping=1.38e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(40 * u.nm, 2013 * u.nm),
    laser_absorption_cross_section=0.02e-20 * u.cm2,
    # Two-for-one cross-relaxation at 4-6 at.% doping.
    quantum_efficiency=1.8,
    heat_fraction=0.30,
    poisson_ratio=0.25,
    notes=(
        "Fan et al., IEEE JQE 24, 924 (1988); Koechner (2006) sec. 2.3. "
        "Quantum efficiency 1.8 assumes cross-relaxation at ~4-6 at.%; use "
        "~1 at low doping."
    ),
)

HO_YAG = GainMedium(
    name="Ho:YAG (Tm-fibre pumped)",
    laser_wavelength=2090 * u.nm,
    pump_wavelength=1908 * u.nm,
    emission_cross_section=1.1e-20 * u.cm2,
    upper_state_lifetime=7.8 * u.ms,
    refractive_index=1.80,
    dn_dT=7.3e-6,
    thermal_conductivity=13.0,
    thermal_expansion=7.5e-6,
    pump_absorption_cross_section=1.0e-20 * u.cm2,
    ion_density_per_unit_doping=1.38e20 / u.cm3,
    doping_unit="at.%",
    gain_bandwidth=u.bandwidth_nm_to_hz(5 * u.nm, 2090 * u.nm),
    laser_absorption_cross_section=0.14e-20 * u.cm2,
    pump_emission_cross_section=0.25e-20 * u.cm2,
    poisson_ratio=0.25,
    notes=(
        "Budni et al., JOSA B 17, 723 (2000); Payne et al., IEEE JQE 28, "
        "2619 (1992). In-band pumped at 1908 nm; quantum defect ~9 %."
    ),
)

#: All predefined materials keyed by a short lower-case id, grouped by
#: active ion.
MATERIALS: dict[str, GainMedium] = {
    "nd:yag": ND_YAG,
    "nd:yvo4": ND_YVO4,
    "nd:gdvo4": ND_GDVO4,
    "nd:ylf 1047": ND_YLF_1047,
    "nd:ylf 1053": ND_YLF_1053,
    "nd:glass": ND_GLASS,
    "yb:yag": YB_YAG,
    "yb:kgw": YB_KGW,
    "yb:kyw": YB_KYW,
    "yb:glass": YB_GLASS,
    "yb:caf2": YB_CAF2,
    "yb:lu2o3": YB_LU2O3,
    "ti:sapphire": TI_SAPPHIRE,
    "cr:lisaf": CR_LISAF,
    "cr:forsterite": CR_FORSTERITE,
    "alexandrite": ALEXANDRITE,
    "cr:znse": CR_ZNSE,
    "er:yag": ER_YAG,
    "tm:yag": TM_YAG,
    "ho:yag": HO_YAG,
}


def get_material(name: str) -> GainMedium:
    """Look up a predefined gain medium by name (case-insensitive).

    Parameters
    ----------
    name : str
        One of the keys of :data:`MATERIALS`, e.g. ``"Nd:YAG"``.

    Raises
    ------
    KeyError
        If the name is unknown.
    """
    key = name.strip().lower()
    if key not in MATERIALS:
        raise KeyError(f"Unknown material {name!r}; known: {sorted(MATERIALS)}")
    return MATERIALS[key]
