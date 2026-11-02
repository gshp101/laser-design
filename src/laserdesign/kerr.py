"""Kerr-lens mode locking (KLM): self-focusing in the resonator.

Kerr lens
---------
A Gaussian beam of peak power ``P`` and radii ``w_x``, ``w_y`` raises the
index of a Kerr medium by ``n2 I`` with peak intensity
``I_0 = 2 P / (pi w_x w_y)``. Expanding the profile to second order gives a
thin lens of power

.. math:: \\frac{1}{f_x} = \\frac{4 n_2 I_0 L}{w_x^2}

for a slice of length ``L``, and likewise in ``y``. For a round beam this is
``1/f = 8 n2 P L / (pi w^4)`` (Magni, Cerullo & De Silvestri, Opt. Commun.
96, 348 (1993)). The self-focusing critical power is

.. math:: P_{cr} = \\frac{\\lambda^2}{2\\pi n_0 n_2},

about 2 MW in Ti:sapphire at 800 nm, so a KLM laser runs at a few tenths of
``P_cr`` up to a few ``P_cr`` of intracavity peak power.

Because the beam size changes inside a tightly focused crystal, the crystal
is cut into ``slices`` pieces with a thin Kerr lens in the middle of each,
and the lens powers and mode are iterated to self-consistency
(:class:`KerrLensModel`). In a Brewster-cut crystal the tangential beam is
wider by ``n`` inside the crystal than the equivalent beam the reduced ABCD
model uses; the intensity is computed from the physical size and the lens is
applied in the model's reduced frame.

KLM strength
------------
The usual figure of merit (Magni et al. 1993; Cerullo et al., Opt. Lett. 19,
807 (1994)) is the relative change of the spot size at some plane per unit
normalised power ``p = P / P_cr``, for small ``p``:

.. math:: \\delta = \\frac{1}{w}\\frac{dw}{dp}\\bigg|_{p=0}.

A negative ``delta`` at a hard aperture (a slit near an end mirror) means the
pulse sees less loss than CW light. For soft-aperture (gain-guided) KLM, a
negative ``delta`` in the crystal means the pulse overlaps a small pump spot
better. Values of ``|delta|`` around 1 are useful; they grow without bound
near the edges of the stability zones, where the laser also becomes
sensitive to everything else.

Real KLM lasers are usually operated near the inner edge of a stability zone
and with negative net GDD for soliton shaping
(:func:`laserdesign.modelocking.soliton_required_gdd`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from . import gaussian
from .abcd import BrewsterPlate, Element, Medium, StandingWaveCavity, ThinLens, propagate_q


def critical_power(wavelength: float, n0: float, n2: float) -> float:
    """Self-focusing critical power ``lambda^2 / (2 pi n0 n2)`` [W]."""
    return float(wavelength**2 / (2 * np.pi * n0 * n2))


def kerr_lens_power(power: float, w_x: float, w_y: float, n2: float, length: float,
                    expansion_x: float = 1.0) -> tuple[float, float]:
    """Kerr lens powers ``(1/f_x, 1/f_y)`` of a thin slice [1/m].

    Parameters
    ----------
    power : float
        Peak power of the pulse [W].
    w_x, w_y : float
        Spot sizes in the frame of the ABCD model [m].
    n2 : float
        Nonlinear index [m^2/W].
    length : float
        Physical length of the slice along the beam [m].
    expansion_x : float
        Ratio of the physical to the model spot size in ``x``; ``n`` for the
        tangential plane of a Brewster-cut crystal, otherwise 1.
    """
    i0 = 2 * power / (np.pi * expansion_x * w_x * w_y)
    return float(4 * n2 * i0 * length / w_x**2), float(4 * n2 * i0 * length / w_y**2)


@dataclass
class KerrSolution:
    """Self-consistent cavity at one intracavity peak power.

    Attributes
    ----------
    power : float
        Intracavity peak power [W].
    cavity : resonator or None
        The resonator including the Kerr lenses (``None`` if it went
        unstable).
    stable : bool
    focal_lengths_t, focal_lengths_s : ndarray
        Kerr focal length of each slice [m].
    spot_t, spot_s : ndarray
        Spot sizes at each slice [m].
    iterations : int
    """

    power: float
    cavity: object
    stable: bool
    focal_lengths_t: np.ndarray = field(default_factory=lambda: np.array([]))
    focal_lengths_s: np.ndarray = field(default_factory=lambda: np.array([]))
    spot_t: np.ndarray = field(default_factory=lambda: np.array([]))
    spot_s: np.ndarray = field(default_factory=lambda: np.array([]))
    iterations: int = 0


@dataclass
class KerrLensModel:
    """A resonator with a Kerr medium, solved self-consistently.

    Parameters
    ----------
    cavity : callable
        ``cavity(crystal_elements) -> StandingWaveCavity or RingCavity``.
        Insert the list it is given where the Kerr crystal sits.
    crystal_length : float
        Physical path length in the crystal [m]. For a Brewster-cut crystal
        this is the path inside it, ``thickness * sqrt(n^2+1) / n``.
    n : float
        Linear refractive index.
    n2 : float
        Nonlinear index [m^2/W].
    wavelength : float
        Vacuum wavelength [m].
    brewster : bool
        True for a Brewster-cut (or Brewster-angled) crystal.
    slices : int
        Number of thin Kerr lenses.
    name : str
        Prefix of the slice names; the Kerr lenses are called
        ``"<name> kerr <i>"``.
    """

    cavity: Callable[[list[Element]], object]
    crystal_length: float
    n: float
    n2: float
    wavelength: float
    brewster: bool = False
    slices: int = 8
    name: str = "Kerr medium"

    @property
    def critical_power(self) -> float:
        """``P_cr`` of the crystal [W]."""
        return critical_power(self.wavelength, self.n, self.n2)

    @property
    def lens_names(self) -> list[str]:
        return [f"{self.name} kerr {i}" for i in range(self.slices)]

    def crystal_elements(self, powers_t: Sequence[float] | None = None,
                         powers_s: Sequence[float] | None = None) -> list[Element]:
        """Crystal as ``slices`` pieces with a thin lens in the middle of each.

        ``powers_t`` and ``powers_s`` are the lens powers ``1/f`` [1/m]
        (zero by default, i.e. the cold cavity).
        """
        k = self.slices
        pt = np.zeros(k) if powers_t is None else np.asarray(powers_t, float)
        ps = np.zeros(k) if powers_s is None else np.asarray(powers_s, float)
        els: list[Element] = []
        for i in range(k):
            if self.brewster:
                thickness = self.crystal_length * self.n / np.sqrt(self.n**2 + 1)
                half = lambda j: BrewsterPlate(thickness=thickness / (2 * k), n=self.n,  # noqa: E731
                                               name=f"{self.name} slice {i}{j}")
            else:
                half = lambda j: Medium(self.crystal_length / (2 * k), n=self.n,  # noqa: E731
                                        name=f"{self.name} slice {i}{j}")
            ft = 1 / pt[i] if pt[i] != 0 else np.inf
            fs = 1 / ps[i] if ps[i] != 0 else np.inf
            els += [half("a"), ThinLens(f=ft, f_sagittal=fs, name=self.lens_names[i]), half("b")]
        return els

    def cold_cavity(self):
        """The resonator without Kerr lensing."""
        return self.cavity(self.crystal_elements())

    def _spots(self, cav) -> tuple[np.ndarray, np.ndarray]:
        """Spot sizes at the input of each Kerr lens, in one pass per plane."""
        names = set(self.lens_names)
        out = []
        for plane in ("t", "s"):
            q = cav.eigen_q(plane)
            found = {}
            for el in cav.elements:
                if el.name in names and el.name not in found:
                    found[el.name] = gaussian.spot_size(q, cav.wavelength)
                q = propagate_q(q, el.matrix(plane))
            out.append(np.array([found[nm] for nm in self.lens_names]))
        return out[0], out[1]

    def solve(self, power: float, tol: float = 1e-10, max_iter: int = 500,
              damping: float = 0.5) -> KerrSolution:
        """Self-consistent Kerr lenses and mode at an intracavity peak power [W]."""
        slice_len = self.crystal_length / self.slices
        exp_t = self.n if self.brewster else 1.0
        pt = np.zeros(self.slices)
        ps = np.zeros(self.slices)
        for it in range(1, max_iter + 1):
            cav = self.cavity(self.crystal_elements(pt, ps))
            if not cav.is_stable():
                return KerrSolution(power, None, False, iterations=it)
            wt, ws = self._spots(cav)
            new = np.array([kerr_lens_power(power, a, b, self.n2, slice_len, exp_t)
                            for a, b in zip(wt, ws)])
            nt, ns = new[:, 0], new[:, 1]
            scale = max(np.max(np.abs(nt)), np.max(np.abs(ns)), 1e-30)
            change = max(np.max(np.abs(nt - pt)), np.max(np.abs(ns - ps))) / scale
            pt = (1 - damping) * pt + damping * nt
            ps = (1 - damping) * ps + damping * ns
            if power == 0 or change < tol:
                break
        cav = self.cavity(self.crystal_elements(pt, ps))
        if not cav.is_stable():
            return KerrSolution(power, None, False, iterations=it)
        wt, ws = self._spots(cav)
        with np.errstate(divide="ignore"):
            ft = np.where(pt != 0, 1 / np.where(pt != 0, pt, 1), np.inf)
            fs = np.where(ps != 0, 1 / np.where(ps != 0, ps, 1), np.inf)
        return KerrSolution(power, cav, True, ft, fs, wt, ws, it)

    # ------------------------------------------------------------------ #
    def spot_size(self, solution: KerrSolution, location: str | int = "crystal",
                  plane: str = "t") -> float:
        """Spot size [m] of a solved cavity at ``location``.

        ``location`` is ``"crystal"`` (mean over the Kerr slices), ``1`` or
        ``2`` (an end mirror of a standing-wave cavity) or an element name.
        """
        cav = solution.cavity
        if location == "crystal":
            return float(np.mean(solution.spot_t if plane == "t" else solution.spot_s))
        if isinstance(location, int):
            if not isinstance(cav, StandingWaveCavity):
                raise ValueError("End mirrors exist only in standing-wave cavities")
            return cav.spot_size_on_mirror(location, plane)
        return cav.spot_size_at(location, plane)

    def klm_strength(self, location: str | int = 1, plane: str = "t",
                     dp: float = 0.01) -> float:
        """``delta = (1/w) dw/dp`` at ``p -> 0`` (see module docstring).

        Uses Richardson extrapolation of forward differences at ``dp`` and
        ``2 dp`` (``p = P / P_cr``). Returns ``nan`` if the cavity is unstable.
        """
        p_cr = self.critical_power
        s0 = self.solve(0.0)
        s1 = self.solve(dp * p_cr)
        s2 = self.solve(2 * dp * p_cr)
        if not (s0.stable and s1.stable and s2.stable):
            return float("nan")
        w0 = self.spot_size(s0, location, plane)
        d1 = (self.spot_size(s1, location, plane) - w0) / dp
        d2 = (self.spot_size(s2, location, plane) - w0) / (2 * dp)
        return float((2 * d1 - d2) / w0)

    def spot_vs_power(self, normalized_powers, location: str | int = 1,
                      plane: str = "t") -> np.ndarray:
        """Spot size [m] at ``location`` for each ``p = P / P_cr`` (``nan`` if unstable)."""
        out = []
        for p in np.atleast_1d(normalized_powers):
            sol = self.solve(float(p) * self.critical_power)
            out.append(self.spot_size(sol, location, plane) if sol.stable else np.nan)
        return np.array(out)
