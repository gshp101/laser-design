"""Ray-transfer (ABCD) matrices, resonators and their Gaussian eigenmodes.

Conventions
-----------
* Matrices act on the *reduced* ray vector ``(y, n * y')`` and on the reduced
  complex beam parameter ``q_hat = q / n`` (Siegman, *Lasers*, ch. 15 and 20).
  A slab of length ``L`` and index ``n`` therefore has ``B = L / n`` and the
  vacuum wavelength is used everywhere.
* Mirror radii are positive for concave (focusing) mirrors.
* Each element can return different matrices for the tangential (``"t"``,
  in the plane of incidence) and sagittal (``"s"``) planes, so off-axis
  curved mirrors and Brewster plates produce the correct astigmatism.

A resonator is described by the list of elements met on a single pass.
:class:`StandingWaveCavity` adds the two end mirrors and unfolds the round
trip; :class:`RingCavity` treats the list as a closed loop. Both find the
self-consistent Gaussian mode (Siegman ch. 21) and can sample the spot size
along the beam path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from . import gaussian
from .units import c as _c

Plane = str  # "t" (tangential) or "s" (sagittal)


def _check_plane(plane: Plane) -> None:
    if plane not in ("t", "s"):
        raise ValueError("plane must be 't' (tangential) or 's' (sagittal)")


def propagate_q(q: complex, matrix: np.ndarray) -> complex:
    """Propagate a reduced q parameter through an ABCD matrix.

    ``q2 = (A q1 + B) / (C q1 + D)``.
    """
    (a, b), (cc, d) = matrix
    return (a * q + b) / (cc * q + d)


# ---------------------------------------------------------------------- #
# Elements
# ---------------------------------------------------------------------- #
@dataclass
class Element:
    """Base class for optical elements.

    Subclasses implement :meth:`matrix`. ``length`` is the physical length
    along the beam and ``index`` the refractive index inside the element
    (used for optical path length and for sampling the beam).
    """

    name: str = field(default="", kw_only=True)

    length: float = field(default=0.0, init=False)
    index: float = field(default=1.0, init=False)

    def matrix(self, plane: Plane = "t") -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def partial_matrix(self, fraction: float, plane: Plane = "t") -> np.ndarray:
        """Matrix for the first ``fraction`` of the element's length.

        Only meaningful for elements with a length; thin elements return the
        full matrix for ``fraction > 0`` and the identity for ``fraction = 0``.
        """
        return self.matrix(plane) if fraction > 0 else np.eye(2)

    def reversed(self) -> "Element":
        """The element as seen by a beam travelling the other way."""
        return self

    @property
    def optical_length(self) -> float:
        """Optical path length ``n * L`` [m]."""
        return self.index * self.length


@dataclass
class FreeSpace(Element):
    """Propagation over a physical distance in a homogeneous medium.

    Parameters
    ----------
    distance : float
        Physical length [m].
    n : float
        Refractive index (default 1, air/vacuum).
    """

    distance: float = 0.0
    n: float = 1.0

    def __post_init__(self):
        if self.distance < 0:
            raise ValueError("distance must be non-negative")
        self.length = self.distance
        self.index = self.n

    def matrix(self, plane: Plane = "t") -> np.ndarray:
        _check_plane(plane)
        return np.array([[1.0, self.distance / self.n], [0.0, 1.0]])

    def partial_matrix(self, fraction: float, plane: Plane = "t") -> np.ndarray:
        return np.array([[1.0, fraction * self.distance / self.n], [0.0, 1.0]])


@dataclass
class Medium(FreeSpace):
    """A dielectric block with flat, normal-incidence faces.

    In the reduced-matrix convention flat interfaces are the identity, so this
    is the same as :class:`FreeSpace` with ``n > 1``. It exists to make
    resonator descriptions read naturally, e.g. ``Medium(10*mm, n=1.82,
    name="Nd:YAG")``.
    """


@dataclass
class ThinLens(Element):
    """An ideal thin lens of focal length ``f`` (positive = converging).

    ``f = inf`` gives the identity. Separate ``f_sagittal`` can be supplied
    for an astigmatic (e.g. cylindrical or thermal) lens.
    """

    f: float = np.inf
    f_sagittal: float | None = None

    def matrix(self, plane: Plane = "t") -> np.ndarray:
        _check_plane(plane)
        f = self.f if (plane == "t" or self.f_sagittal is None) else self.f_sagittal
        power = 0.0 if not np.isfinite(f) else 1.0 / f
        return np.array([[1.0, 0.0], [-power, 1.0]])


@dataclass
class CurvedMirror(Element):
    """A spherical mirror used in reflection, unfolded as a lens.

    Parameters
    ----------
    R : float
        Radius of curvature [m]; positive for concave, ``inf`` for flat.
    angle : float
        Angle of incidence [rad]. Off-axis use gives tangential focal length
        ``R cos(angle) / 2`` and sagittal focal length ``R / (2 cos(angle))``.
    """

    R: float = np.inf
    angle: float = 0.0

    def matrix(self, plane: Plane = "t") -> np.ndarray:
        _check_plane(plane)
        if not np.isfinite(self.R):
            return np.eye(2)
        cos = np.cos(self.angle)
        r_eff = self.R * cos if plane == "t" else self.R / cos
        return np.array([[1.0, 0.0], [-2.0 / r_eff, 1.0]])


@dataclass
class FlatMirror(CurvedMirror):
    """A flat fold mirror (identity matrix)."""

    R: float = np.inf


@dataclass
class Interface(Element):
    """Refraction at a spherical interface from index ``n1`` into ``n2``.

    ``R`` is positive when the centre of curvature lies after the surface.
    Use ``R = inf`` for a flat interface (identity in reduced form).
    """

    n1: float = 1.0
    n2: float = 1.0
    R: float = np.inf

    def matrix(self, plane: Plane = "t") -> np.ndarray:
        _check_plane(plane)
        if not np.isfinite(self.R):
            return np.eye(2)
        return np.array([[1.0, 0.0], [-(self.n2 - self.n1) / self.R, 1.0]])

    def reversed(self) -> "Interface":
        return Interface(n1=self.n2, n2=self.n1, R=-self.R, name=self.name)


@dataclass
class BrewsterPlate(Element):
    """A plate of thickness ``t`` and index ``n`` at Brewster's angle.

    The effective reduced propagation lengths are ``t sqrt(n^2+1) / n^2``
    (sagittal) and ``t sqrt(n^2+1) / n^4`` (tangential), from Kogelnik et al.,
    IEEE J. Quantum Electron. 8, 373 (1972). ``length`` is the geometric path
    inside the plate, ``t sqrt(n^2+1) / n``.
    """

    thickness: float = 0.0
    n: float = 1.5

    def __post_init__(self):
        self.length = self.thickness * np.sqrt(self.n**2 + 1) / self.n
        self.index = self.n

    def _reduced(self, plane: Plane) -> float:
        d = self.thickness * np.sqrt(self.n**2 + 1)
        return d / self.n**4 if plane == "t" else d / self.n**2

    def matrix(self, plane: Plane = "t") -> np.ndarray:
        _check_plane(plane)
        return np.array([[1.0, self._reduced(plane)], [0.0, 1.0]])

    def partial_matrix(self, fraction: float, plane: Plane = "t") -> np.ndarray:
        return np.array([[1.0, fraction * self._reduced(plane)], [0.0, 1.0]])


def crystal_with_thermal_lens(length: float, n: float, f_thermal: float,
                              name: str = "crystal",
                              f_thermal_sagittal: float | None = None) -> list[Element]:
    """A gain crystal modelled as two half-lengths with a thin thermal lens.

    This lumped model is accurate when the crystal is short compared with the
    thermal focal length (Koechner sec. 7.1). The lens is named
    ``"<name> thermal lens"``, which is a convenient plane to read the laser
    spot size at the crystal centre.

    Returns
    -------
    list of Element
    """
    half = length / 2
    return [
        Medium(half, n=n, name=f"{name} (first half)"),
        ThinLens(f=f_thermal, f_sagittal=f_thermal_sagittal,
                 name=f"{name} thermal lens"),
        Medium(half, n=n, name=f"{name} (second half)"),
    ]


def system_matrix(elements: Sequence[Element], plane: Plane = "t") -> np.ndarray:
    """Product of element matrices in beam order (first element acts first)."""
    m = np.eye(2)
    for el in elements:
        m = el.matrix(plane) @ m
    return m


# ---------------------------------------------------------------------- #
# Modes and resonators
# ---------------------------------------------------------------------- #
@dataclass
class ModeProfile:
    """Spot size sampled along the beam path inside a resonator.

    Attributes
    ----------
    z : ndarray
        Physical distance from the reference plane [m].
    w : ndarray
        1/e^2 intensity radius [m].
    element_starts : list of float
        Position at which each element begins.
    """

    z: np.ndarray
    w: np.ndarray
    element_starts: list[float]


class _Resonator:
    """Shared machinery for standing-wave and ring resonators."""

    elements: list[Element]
    wavelength: float

    # subclasses provide the round trip as an ordered element list
    def _round_trip_elements(self) -> list[Element]:  # pragma: no cover
        raise NotImplementedError

    def round_trip_matrix(self, plane: Plane = "t") -> np.ndarray:
        """Round-trip ABCD matrix starting at the reference plane."""
        return system_matrix(self._round_trip_elements(), plane)

    def stability_parameter(self, plane: Plane = "t") -> float:
        """``m = (A + D) / 2`` of the round-trip matrix.

        The resonator is stable when ``-1 < m < 1``. For a two-mirror cavity
        ``m = 2 g1 g2 - 1``.
        """
        (a, _), (_, d) = self.round_trip_matrix(plane)
        return float((a + d) / 2)

    def is_stable(self, plane: Plane | None = None) -> bool:
        """True if the resonator is stable (in both planes when ``plane`` is None)."""
        planes = ("t", "s") if plane is None else (plane,)
        return all(abs(self.stability_parameter(p)) < 1 for p in planes)

    def eigen_q(self, plane: Plane = "t") -> complex:
        """Self-consistent reduced q parameter at the reference plane.

        Solves ``q = (A q + B) / (C q + D)`` and keeps the root with
        ``Im(1/q) < 0`` (Siegman eq. 21.7).

        Raises
        ------
        ValueError
            If the resonator is unstable in this plane.
        """
        (a, b), (cc, d) = self.round_trip_matrix(plane)
        m = (a + d) / 2
        if abs(m) >= 1:
            raise ValueError(f"Resonator is unstable in plane {plane!r} (m = {m:.4f})")
        inv_q = (d - a) / (2 * b) - 1j * np.sqrt(1 - m**2) / abs(b)
        return 1.0 / inv_q

    def q_before(self, index: int, plane: Plane = "t") -> complex:
        """Reduced q just before forward element ``index`` (``len`` = end)."""
        q = self.eigen_q(plane)
        for el in self.elements[:index]:
            q = propagate_q(q, el.matrix(plane))
        return q

    def spot_size(self, index: int = 0, plane: Plane = "t") -> float:
        """Mode radius just before forward element ``index`` [m]."""
        return gaussian.spot_size(self.q_before(index, plane), self.wavelength)

    def element_index(self, name: str) -> int:
        """Index of the first element whose name matches ``name``."""
        for i, el in enumerate(self.elements):
            if el.name == name:
                return i
        raise KeyError(f"No element named {name!r}")

    def spot_size_at(self, name: str, plane: Plane = "t") -> float:
        """Mode radius at the input of the element called ``name`` [m]."""
        return self.spot_size(self.element_index(name), plane)

    def mode_profile(self, plane: Plane = "t", points_per_element: int = 50) -> ModeProfile:
        """Sample the mode radius along one forward pass of the element list."""
        q = self.eigen_q(plane)
        zs, ws, starts = [], [], []
        z0 = 0.0
        for el in self.elements:
            starts.append(z0)
            if el.length > 0:
                for frac in np.linspace(0, 1, points_per_element):
                    qq = propagate_q(q, el.partial_matrix(frac, plane))
                    zs.append(z0 + frac * el.length)
                    ws.append(gaussian.spot_size(qq, self.wavelength))
            q = propagate_q(q, el.matrix(plane))
            z0 += el.length
        if not zs:
            zs, ws = [0.0], [gaussian.spot_size(q, self.wavelength)]
        return ModeProfile(np.array(zs), np.array(ws), starts)

    @property
    def physical_length(self) -> float:
        """Sum of element physical lengths for one pass [m]."""
        return float(sum(el.length for el in self.elements))

    @property
    def optical_length(self) -> float:
        """Sum of ``n L`` for one pass [m]."""
        return float(sum(el.optical_length for el in self.elements))

    def round_trip_gouy_phase(self, plane: Plane = "t") -> float:
        """Round-trip Gouy phase ``theta`` with ``cos(theta) = m`` [rad].

        The sign follows ``B`` of the round-trip matrix (Siegman sec. 21.2).
        """
        (_, b), _ = self.round_trip_matrix(plane)
        theta = np.arccos(np.clip(self.stability_parameter(plane), -1, 1))
        return float(theta if b >= 0 else 2 * np.pi - theta)


class StandingWaveCavity(_Resonator):
    """A linear resonator between two end mirrors.

    Parameters
    ----------
    elements : sequence of Element
        Elements met going from end mirror 1 to end mirror 2 (fold mirrors,
        crystals, lenses, gaps...). The end mirrors themselves are *not*
        included.
    R1, R2 : float
        Radii of curvature of the end mirrors [m], positive for concave,
        ``inf`` for flat.
    wavelength : float
        Vacuum laser wavelength [m].

    Notes
    -----
    The reference plane is end mirror 1, so :meth:`eigen_q` and
    ``spot_size(0)`` give the mode on mirror 1 and
    ``spot_size(len(elements))`` the mode on mirror 2.

    Examples
    --------
    A 1 m long two-mirror cavity with R1 = R2 = 2 m (g1 = g2 = 0.5):

    >>> from laserdesign.abcd import StandingWaveCavity, FreeSpace
    >>> cav = StandingWaveCavity([FreeSpace(1.0)], R1=2.0, R2=2.0,
    ...                          wavelength=1064e-9)
    >>> round(cav.stability_parameter(), 3)
    -0.5
    """

    def __init__(self, elements: Sequence[Element], R1: float = np.inf,
                 R2: float = np.inf, wavelength: float = 1064e-9):
        self.elements = list(elements)
        self.R1 = R1
        self.R2 = R2
        self.wavelength = wavelength

    def _round_trip_elements(self) -> list[Element]:
        back = [el.reversed() for el in reversed(self.elements)]
        return [*self.elements, CurvedMirror(self.R2), *back, CurvedMirror(self.R1)]

    def spot_size_on_mirror(self, which: int = 1, plane: Plane = "t") -> float:
        """Mode radius on end mirror 1 or 2 [m]."""
        return self.spot_size(0 if which == 1 else len(self.elements), plane)

    @property
    def free_spectral_range(self) -> float:
        """Longitudinal mode spacing ``c / (2 L_opt)`` [Hz] (phase index)."""
        return _c / (2 * self.optical_length)

    @property
    def round_trip_time(self) -> float:
        """Round-trip time ``2 L_opt / c`` [s]."""
        return 2 * self.optical_length / _c

    def transverse_mode_spacing(self, plane: Plane = "t") -> float:
        """Frequency spacing of adjacent transverse modes [Hz]."""
        return self.free_spectral_range * self.round_trip_gouy_phase(plane) / (2 * np.pi)


class RingCavity(_Resonator):
    """A ring resonator: the element list is one full round trip.

    Curved mirrors are included in ``elements`` as :class:`CurvedMirror`
    entries with their angle of incidence.
    """

    def __init__(self, elements: Sequence[Element], wavelength: float = 1064e-9):
        self.elements = list(elements)
        self.wavelength = wavelength

    def _round_trip_elements(self) -> list[Element]:
        return list(self.elements)

    @property
    def free_spectral_range(self) -> float:
        """Longitudinal mode spacing ``c / L_opt`` [Hz]."""
        return _c / self.optical_length

    @property
    def round_trip_time(self) -> float:
        """Round-trip time ``L_opt / c`` [s]."""
        return self.optical_length / _c


# ---------------------------------------------------------------------- #
# Closed-form two-mirror results (Siegman ch. 19)
# ---------------------------------------------------------------------- #
def g_parameters(L: float, R1: float, R2: float) -> tuple[float, float]:
    """Resonator g-parameters ``g_i = 1 - L / R_i`` of an empty two-mirror cavity."""
    g1 = 1 - (L / R1 if np.isfinite(R1) else 0.0)
    g2 = 1 - (L / R2 if np.isfinite(R2) else 0.0)
    return g1, g2


def two_mirror_mode(L: float, R1: float, R2: float, wavelength: float) -> dict:
    """Analytic TEM00 mode of an empty two-mirror resonator.

    Implements Siegman eqs. 19.18-19.20.

    Returns
    -------
    dict
        ``w1``, ``w2`` (spot sizes on the mirrors), ``w0`` (waist), ``z1``
        (waist distance from mirror 1), ``g1``, ``g2``.
    """
    g1, g2 = g_parameters(L, R1, R2)
    prod = g1 * g2
    if not 0 < prod < 1:
        raise ValueError(f"Unstable or marginal resonator: g1 g2 = {prod:.4f}")
    lam = wavelength
    w1 = np.sqrt(lam * L / np.pi * np.sqrt(g2 / (g1 * (1 - prod))))
    w2 = np.sqrt(lam * L / np.pi * np.sqrt(g1 / (g2 * (1 - prod))))
    w0 = np.sqrt(lam * L / np.pi * np.sqrt(prod * (1 - prod) / (g1 + g2 - 2 * prod) ** 2))
    z1 = g2 * (1 - g1) * L / (g1 + g2 - 2 * prod)
    return {"w1": w1, "w2": w2, "w0": w0, "z1": z1, "g1": g1, "g2": g2}
