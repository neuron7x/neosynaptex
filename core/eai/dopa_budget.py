from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from math import exp
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
        if self.envelope < 0:
            raise ValueError("negative_envelope_forbidden")
        self._lock = Lock()

    @classmethod
    def create(
        cls,
        envelope: float,
        probe_tax: float,
        lambda_penalty: float = 0.0,
    ) -> BudgetLedger:
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
        with self._lock:
            penalty = Decimal(str(exp(self.lambda_penalty * self.failure_streak)))
            cost = (Decimal(str(requested_cost)) * penalty) + self.probe_tax
            before = self.remaining
            overspend = cost > self.remaining
            if overspend:
                q = Decimal(str(quarantine_cost)) + self.probe_tax
                cost = min(self.remaining, q)
            self.remaining -= cost
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
