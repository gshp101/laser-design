"""Gain media and their spectroscopic, thermal and optical properties.

A :class:`GainMedium` collects every material number the rest of the
library needs. Four common media are predefined (:data:`ND_YAG`,
:data:`ND_YVO4`, :data:`YB_YAG`, :data:`TI_SAPPHIRE`) and can be looked up
by name with :func:`get_material`. All values are in SI units.

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

    def replace(self, **changes) -> "GainMedium":
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

#: All predefined materials keyed by a short lower-case id.
MATERIALS: dict[str, GainMedium] = {
    "nd:yag": ND_YAG,
    "nd:yvo4": ND_YVO4,
    "yb:yag": YB_YAG,
    "ti:sapphire": TI_SAPPHIRE,
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
