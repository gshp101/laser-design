"""Unit helpers and physical constants.

The whole library works in SI units: metres, seconds, watts, joules,
kelvin and square metres for cross sections. These helpers make it easy to
write values in the units laser engineers usually quote, for example
``1064 * nm`` or ``2.8e-19 * cm2``.

Examples
--------
>>> from laserdesign.units import nm, mm, cm2
>>> wavelength = 1064 * nm
>>> sigma = 2.8e-19 * cm2
"""

from scipy import constants as _c

#: Speed of light in vacuum [m/s].
c = _c.c
#: Planck constant [J s].
h = _c.h
#: Boltzmann constant [J/K].
k_B = _c.k

# Length
m = 1.0
cm = 1e-2
mm = 1e-3
um = 1e-6
nm = 1e-9

# Area
cm2 = 1e-4
mm2 = 1e-6

# Volume
cm3 = 1e-6

# Time
s = 1.0
ms = 1e-3
us = 1e-6
ns = 1e-9
ps = 1e-12
fs = 1e-15

# Frequency
Hz = 1.0
kHz = 1e3
MHz = 1e6
GHz = 1e9
THz = 1e12

# Power and energy
W = 1.0
mW = 1e-3
kW = 1e3
J = 1.0
mJ = 1e-3
uJ = 1e-6
nJ = 1e-9


def photon_energy(wavelength: float) -> float:
    """Return the photon energy ``h c / lambda`` in joules.

    Parameters
    ----------
    wavelength : float
        Vacuum wavelength [m].
    """
    return h * c / wavelength


def bandwidth_nm_to_hz(delta_lambda: float, wavelength: float) -> float:
    """Convert a wavelength bandwidth to a frequency bandwidth.

    Uses ``delta_nu = c * delta_lambda / lambda**2``, valid when the
    bandwidth is small compared with the centre wavelength.

    Parameters
    ----------
    delta_lambda : float
        Bandwidth [m].
    wavelength : float
        Centre wavelength [m].

    Returns
    -------
    float
        Bandwidth [Hz].
    """
    return c * delta_lambda / wavelength**2
