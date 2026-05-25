"""Shared contract constants for Machine Thinking pipeline."""

from __future__ import annotations

SECTION_WEIGHTS: dict[str, float] = {
    "PRE-WORK": 1.2,
    "MATH": 1.2,
    "IMPLEMENTATION": 1.0,
    "VALIDATION": 1.3,
    "FALSIFICATION": 1.4,
    "ARTIFACT": 0.8,
    "GOVERNANCE": 1.1,
    "FINAL TEST": 1.0,
}

CANONICAL_SECTIONS: list[str] = list(SECTION_WEIGHTS.keys())
