"""Symbolic dimensional homogeneity (S2 / GAP-P-01 option b).

Floats carry no units, so we check *equation-level* dimensional homogeneity
symbolically: every additive term in a governing equation must reduce to the
same dimension. Dimensions are exponent vectors over SI base units; terms are
multiplied/divided by adding/subtracting exponent vectors.

This is real dimensional analysis (not a runtime range guard) and runs once,
not per simulation step.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = ("kg", "m", "s", "A")  # mass, length, time, current (enough for our models)


@dataclass(frozen=True)
class Dim:
    """A physical dimension as exponents over (kg, m, s, A)."""

    exps: tuple[float, ...] = (0, 0, 0, 0)

    def __mul__(self, other: Dim) -> Dim:
        return Dim(tuple(a + b for a, b in zip(self.exps, other.exps, strict=True)))

    def __truediv__(self, other: Dim) -> Dim:
        return Dim(tuple(a - b for a, b in zip(self.exps, other.exps, strict=True)))

    def __pow__(self, p: float) -> Dim:
        return Dim(tuple(a * p for a in self.exps))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dim):
            return NotImplemented
        return all(abs(a - b) < 1e-9 for a, b in zip(self.exps, other.exps, strict=True))

    def __hash__(self) -> int:
        return hash(self.exps)


DIMENSIONLESS = Dim()
KG = Dim((1, 0, 0, 0))
M = Dim((0, 1, 0, 0))
S = Dim((0, 0, 1, 0))
A = Dim((0, 0, 0, 1))  # ampere (current)
V = KG * M**2 / (A * S**3)  # volt
FARAD = A**2 * S**4 / (KG * M**2)
SIEMENS = A**2 * S**3 / (KG * M**2)
WATT = KG * M**2 / S**3


@dataclass(frozen=True)
class HomogeneityReport:
    """Per-equation dimensional verdict."""

    equation: str
    target: Dim
    term_dims: dict[str, Dim]
    homogeneous: bool


def _check(equation: str, target: Dim, terms: dict[str, Dim]) -> HomogeneityReport:
    ok = all(d == target for d in terms.values())
    return HomogeneityReport(equation, target, terms, ok)


def check_adex_voltage() -> HomogeneityReport:
    """C dV/dt = -g_L(V-E_L) + g_L Delta_T exp(.) - w + I  : every term is current (A)."""
    terms = {
        "C dV/dt": FARAD * (V / S),
        "g_L (V-E_L)": SIEMENS * V,
        "g_L Delta_T exp": SIEMENS * V,  # exp() is dimensionless
        "w": A,
        "I_ext": A,
    }
    return _check("AdEx voltage", A, terms)


def check_kuramoto() -> HomogeneityReport:
    """dtheta/dt = omega + (K/N) sum sin(.)  : every term is angular rate (1/s)."""
    rate = DIMENSIONLESS / S  # rad is dimensionless -> 1/s
    terms = {
        "dtheta/dt": rate,
        "omega": rate,
        "(K/N) sin": rate,  # K carries 1/s, sin() dimensionless
    }
    return _check("Kuramoto phase", rate, terms)


def check_reaction_diffusion() -> HomogeneityReport:
    """du/dt = D_u Laplacian(u) + f(u,v) : every term is [u]/s. Use [u]=mol/m^3."""
    conc = Dim((0, -3, 0, 0)) * Dim((0, 0, 0, 0))  # placeholder length^-3 concentration
    rate = conc / S
    terms = {
        "du/dt": rate,
        "D_u Laplacian": (M**2 / S) * (conc / M**2),  # D[m^2/s] * d2u/dx2 [conc/m^2]
        "f(u,v)": rate,
    }
    return _check("Reaction-diffusion", rate, terms)


def check_energy_power() -> HomogeneityReport:
    """dE/dt = P_input - P_diss : every term is power (W)."""
    terms = {
        "dE/dt": (FARAD * V**2) / S,  # (1/2 C V^2)/s
        "P_input": A * V,
        "P_diss": SIEMENS * V**2,
    }
    return _check("Energy balance", WATT, terms)


def all_checks() -> list[HomogeneityReport]:
    """Run every equation-level dimensional check."""
    return [
        check_kuramoto(),
        check_adex_voltage(),
        check_reaction_diffusion(),
        check_energy_power(),
    ]
