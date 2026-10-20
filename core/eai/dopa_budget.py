from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from math import exp, isfinite
from threading import Lock

getcontext().prec = 28
_SCALE = Decimal("0.000001")


@dataclass(frozen=True)
class BudgetStep:
    before: float
    action_cost: float
    after: float
    overspend: bool


@dataclass
class BudgetLedger:
    envelope: Decimal
    probe_tax: Decimal
    remaining: Decimal
    failure_streak: int
    lambda_penalty: float

    def __post_init__(self) -> None:
        if not self.envelope.is_finite() or self.envelope < 0:
            raise ValueError("invalid_budget_envelope")
        if not self.probe_tax.is_finite() or self.probe_tax < 0:
            raise ValueError("invalid_probe_tax")
        if not self.remaining.is_finite() or not 0 <= self.remaining <= self.envelope:
            raise ValueError("invalid_remaining_balance")
        if not isfinite(self.lambda_penalty) or self.lambda_penalty < 0:
            raise ValueError("invalid_burn_rate")
        if type(self.failure_streak) is not int or self.failure_streak < 0:
            raise ValueError("invalid_failure_streak")
        self._lock = Lock()

    @classmethod
    def create(
        cls,
        envelope: float,
        probe_tax: float,
        lambda_penalty: float = 0.0,
    ) -> BudgetLedger:
        for name, value in (
            ("envelope", envelope),
            ("probe_tax", probe_tax),
            ("lambda_penalty", lambda_penalty),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"invalid_{name}_type")
            if not isfinite(value) or value < 0:
                raise ValueError(f"invalid_{name}_value")
        e = Decimal(str(envelope))
        p = Decimal(str(probe_tax))
        return cls(
            envelope=e,
            probe_tax=p,
            remaining=e,
            failure_streak=0,
            lambda_penalty=lambda_penalty,
        )

    def apply(self, requested_cost: float, quarantine_cost: float) -> BudgetStep:
        """Reserve nonnegative finite costs and fail closed under extreme penalties."""
        for name, value in (
            ("requested_cost", requested_cost),
            ("quarantine_cost", quarantine_cost),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"invalid_{name}_type")
            if not isfinite(value) or value < 0:
                raise ValueError(f"invalid_{name}_value")
        with self._lock:
            before = self.remaining
            exponent = self.lambda_penalty * self.failure_streak
            if not isfinite(exponent) or exponent >= 700:
                # The exponential is already far beyond ordinary budget scales.
                # Treat the proposed action as unaffordable; never crash or
                # accidentally authorize action under numerical overflow.
                cost = before + Decimal(1)
            else:
                penalty = Decimal(str(exp(exponent)))
                cost = Decimal(str(requested_cost)) * penalty + self.probe_tax
            overspend = cost > before
            if overspend:
                q = Decimal(str(quarantine_cost)) + self.probe_tax
                cost = min(before, q)
            self.remaining = before - cost
            return BudgetStep(float(before), float(cost), float(self.remaining), overspend)

    def register_failure(self, failed: bool) -> None:
        with self._lock:
            self.failure_streak = self.failure_streak + 1 if failed else 0

    def snapshot(self) -> dict[str, float | bool | int]:
        with self._lock:
            spent = self.envelope - self.remaining
            eq = (spent + self.remaining).quantize(_SCALE) == self.envelope.quantize(_SCALE)
            return {
                "envelope": float(self.envelope),
                "probe_tax": float(self.probe_tax),
                "spent": float(spent),
                "remaining": float(self.remaining),
                "failure_streak": self.failure_streak,
                "conserved": eq,
            }
