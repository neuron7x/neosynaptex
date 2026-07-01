"""Adapter Registry — runtime validation of DomainAdapter contracts.

Provides discovery, registration, validation, and health checking
for all NFI substrate adapters.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "AdapterHealth",
    "AdapterRegistry",
    "ValidationResult",
]

logger = logging.getLogger(__name__)

_MAX_STATE_KEYS = 4


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class AdapterHealth:
    alive: bool
    domain: str
    last_error: str | None = None


class AdapterRegistry:
    """Single registry for DomainAdapter instances with runtime contract checks."""

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, adapter: Any) -> None:
        """Register adapter after verifying Protocol compliance."""
        errors = self._check_protocol(adapter)
        if errors:
            raise TypeError(f"Adapter fails DomainAdapter Protocol: {'; '.join(errors)}")
        domain = adapter.domain
        if domain in self._adapters:
            raise ValueError(f"Domain '{domain}' already registered")
        self._adapters[domain] = adapter

    def validate(self, adapter: Any) -> ValidationResult:
        """Runtime validation of adapter output contracts."""
        errors: list[str] = []

        # Protocol check
        proto_errors = self._check_protocol(adapter)
        errors.extend(proto_errors)
        if proto_errors:
            return ValidationResult(valid=False, errors=tuple(errors))

        # Domain ASCII check
        domain = adapter.domain
        if not all(ord(c) < 128 for c in domain):
            errors.append(f"domain '{domain}' contains non-ASCII characters")

        # State keys count
        keys = adapter.state_keys
        if len(keys) > _MAX_STATE_KEYS:
            errors.append(f"state_keys has {len(keys)} keys, max {_MAX_STATE_KEYS}")

        # State output check
        try:
            state = adapter.state()
            if not isinstance(state, dict):
                errors.append(f"state() returned {type(state).__name__}, expected dict")
            else:
                for k, v in state.items():
                    if not isinstance(k, str):
                        errors.append(f"state key {k!r} is not str")
                    if not isinstance(v, (int, float)):
                        errors.append(f"state['{k}'] is {type(v).__name__}, expected float")
        except Exception as e:
            errors.append(f"state() raised {type(e).__name__}: {e}")

        # Topo check
        try:
            topo = adapter.topo()
            if not isinstance(topo, (int, float)):
                errors.append(f"topo() returned {type(topo).__name__}, expected float")
            elif np.isfinite(topo) and topo <= 0:
                errors.append(f"topo() returned {topo}, must be > 0")
        except Exception as e:
            errors.append(f"topo() raised {type(e).__name__}: {e}")

        # Cost check
        try:
            cost = adapter.thermo_cost()
            if not isinstance(cost, (int, float)):
                errors.append(f"thermo_cost() returned {type(cost).__name__}, expected float")
            elif np.isfinite(cost) and cost <= 0:
                errors.append(f"thermo_cost() returned {cost}, must be > 0")
        except Exception as e:
            errors.append(f"thermo_cost() raised {type(e).__name__}: {e}")

        return ValidationResult(valid=len(errors) == 0, errors=tuple(errors))

    def discover(self) -> list[Any]:
        """Auto-scan substrates/*/adapter.py for DomainAdapter implementations."""
        root = Path(__file__).resolve().parent.parent
        substrates_dir = root / "substrates"
        adapters: list[Any] = []

        if not substrates_dir.exists():
            return adapters

        for adapter_file in sorted(substrates_dir.glob("*/adapter.py")):
            substrate_name = adapter_file.parent.name
            module_path = f"substrates.{substrate_name}.adapter"
            try:
                mod = importlib.import_module(module_path)
                # Look for classes with domain property
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if (
                        isinstance(obj, type)
                        and hasattr(obj, "domain")
                        and hasattr(obj, "state_keys")
                        and hasattr(obj, "state")
                        and hasattr(obj, "topo")
                        and hasattr(obj, "thermo_cost")
                    ):
                        try:
                            instance = obj()
                            adapters.append(instance)
                        except Exception:  # nosec B110  # auto-discovery: skip adapters that fail to instantiate
                            pass
            except Exception as e:
                logger.debug("Failed to import %s: %s", module_path, e)

        return adapters

    def health(self) -> dict[str, AdapterHealth]:
        """Per-adapter liveness check."""
        results: dict[str, AdapterHealth] = {}
        for domain, adapter in self._adapters.items():
            try:
                adapter.state()
                adapter.topo()
                adapter.thermo_cost()
                results[domain] = AdapterHealth(alive=True, domain=domain)
            except Exception as e:
                results[domain] = AdapterHealth(alive=False, domain=domain, last_error=str(e))
        return results

    @property
    def domains(self) -> list[str]:
        return sorted(self._adapters.keys())

    def get(self, domain: str) -> Any:
        return self._adapters[domain]

    def __len__(self) -> int:
        return len(self._adapters)

    @staticmethod
    def _check_protocol(adapter: Any) -> list[str]:
        errors: list[str] = []
        if not hasattr(adapter, "domain"):
            errors.append("missing 'domain' property")
        if not hasattr(adapter, "state_keys"):
            errors.append("missing 'state_keys' property")
        if not hasattr(adapter, "state"):
            errors.append("missing 'state' method")
        if not hasattr(adapter, "topo"):
            errors.append("missing 'topo' method")
        if not hasattr(adapter, "thermo_cost"):
            errors.append("missing 'thermo_cost' method")
        return errors
