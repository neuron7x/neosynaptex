from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import numpy as np
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SpectralScaling(BaseModel):
    symbol: str
    target_value: float
    tolerance: float = Field(gt=0)
    description: str
    falsification_condition: str


class PhysicsInvariants(BaseModel):
    spectral_scaling: SpectralScaling


class EnergyDissipationRate(BaseModel):
    max_threshold: str
    fail_state: str


class ThermodynamicBounds(BaseModel):
    energy_dissipation_rate: EnergyDissipationRate


class ArchitectureRules(BaseModel):
    fail_closed: bool
    allow_silent_exceptions: bool


class InvariantsContract(BaseModel):
    version: str
    scope: str
    physics_invariants: PhysicsInvariants
    thermodynamic_bounds: ThermodynamicBounds
    architecture_rules: ArchitectureRules


EQ_RE = re.compile(r"\b((?:EQ|INV)-[A-Z0-9\-]+)\b")


def collect_equations(doc_roots: list[Path]) -> set[str]:
    eq_ids: set[str] = set()
    for root in doc_roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() in {".md", ".tex"}:
            eq_ids.update(EQ_RE.findall(root.read_text(encoding="utf-8", errors="ignore")))
            continue
        if root.is_dir():
            for path in root.rglob("*"):
                if path.suffix.lower() in {".md", ".tex"}:
                    eq_ids.update(EQ_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return eq_ids


def collect_test_traces(test_root: Path) -> set[str]:
    ids: set[str] = set()
    if not test_root.exists():
        return ids
    for test_file in test_root.rglob("test_*.py"):
        tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Name)
                    and dec.func.id == "traces_equation"
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)
                ):
                    ids.add(dec.args[0].value)
    return ids


def find_untraced_tests(module_path: Path) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    missing: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            has_trace = any(
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Name)
                and dec.func.id == "traces_equation"
                for dec in node.decorator_list
            )
            if not has_trace:
                missing.append(node.name)
    return missing


def find_untraced_tests_in_tree(test_root: Path) -> list[str]:
    missing_all: list[str] = []
    for test_file in test_root.rglob("test_*.py"):
        text = test_file.read_text(encoding="utf-8", errors="ignore")
        if "traces_equation" not in text:
            continue
        for fn in find_untraced_tests(test_file):
            missing_all.append(f"{test_file}:{fn}")
    return missing_all


def validate_dynamic_gamma_state(contract: InvariantsContract) -> tuple[bool, str]:
    """Fail-closed runtime audit on current γ topology, not only syntax."""
    from core.axioms import SUBSTRATE_GAMMA

    gammas = np.array([g for g, _ in SUBSTRATE_GAMMA.values() if g is not None], dtype=np.float64)
    if gammas.size == 0:
        return False, "FAIL: dynamic gamma audit found zero γ-emitting substrates"

    target = contract.physics_invariants.spectral_scaling.target_value
    tolerance = contract.physics_invariants.spectral_scaling.tolerance
    abs_dev = np.abs(gammas - target)
    violations = int(np.sum(abs_dev > tolerance))
    # Real-time spectral-entropy proxy over |γ-target| distribution.
    hist, _ = np.histogram(abs_dev, bins=min(8, gammas.size), density=False)
    p = hist.astype(np.float64) / max(1.0, float(hist.sum()))
    p = p[p > 0]
    entropy = float(-np.sum(p * np.log2(p)))
    if violations > 3:
        return (
            False,
            "FAIL: dynamic gamma audit violated falsification condition: "
            f"violations={violations} tolerance={tolerance}",
        )
    return (
        True,
        "PASS: dynamic gamma audit | "
        f"n={gammas.size} mean={float(np.mean(gammas)):.4f} "
        f"violations={violations} spectral_entropy={entropy:.4f}",
    )


def main() -> int:
    contract_path = Path("invariants.yaml")
    if not contract_path.exists():
        print("FAIL: invariants.yaml is missing")
        return 1

    try:
        raw = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        contract = InvariantsContract.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        print(f"FAIL: invariant contract validation error: {exc}")
        return 1

    if contract.architecture_rules.allow_silent_exceptions:
        print("FAIL: allow_silent_exceptions must be false (fail-closed)")
        return 1

    equations = collect_equations([Path("docs/TRACEABILITY.md")])
    test_traces = collect_test_traces(Path("tests"))

    missing_in_tests = sorted(eq for eq in equations if eq not in test_traces)
    extra_in_tests = sorted(eq for eq in test_traces if eq not in equations)
    if missing_in_tests:
        print("FAIL: equations documented but not traced in tests:")
        for eq in missing_in_tests:
            print(f"  - {eq}")
        return 1
    if extra_in_tests:
        print("FAIL: equation IDs traced in tests but missing in docs:")
        for eq in extra_in_tests:
            print(f"  - {eq}")
        return 1

    untraced = find_untraced_tests_in_tree(Path("tests"))
    if untraced:
        print("FAIL: untraced tests in tests tree:")
        for fn in untraced:
            print(f"  - {fn}")
        return 1

    dyn_ok, dyn_msg = validate_dynamic_gamma_state(contract)
    if not dyn_ok:
        print(dyn_msg)
        return 1

    print(dyn_msg)
    print(
        "PASS: invariants contract valid | "
        f"equations={len(equations)} traces={len(test_traces)} "
        f"traced_tests={len(test_traces)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
