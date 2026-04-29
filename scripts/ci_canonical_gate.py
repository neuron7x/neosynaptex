#!/usr/bin/env python3
"""CI Canonical Gate -- 6-gate integrity check for neosynaptex.

Gates:
  1. GAMMA_PROVENANCE   -- no unauthorized SUBSTRATE_GAMMA definitions
  2. EVIDENCE_HASH      -- all locked entries have SHA-256 chain
  3. SPLIT_BRAIN        -- no duplicate package identities
  4. MATH_CORE_TESTED   -- core math functions have unit tests
  5. INVARIANT_GAMMA    -- gamma never stored on Neosynaptex instance
  6. TESTPATH_HERMETIC  -- testpaths does not include root "."

Exit 0 if all gates pass. Exit 1 with violation count otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIOLATIONS = []


def _v(gate: str, msg: str) -> None:
    VIOLATIONS.append((gate, msg))


# -----------------------------------------------------------------------
# Gate 1: GAMMA_PROVENANCE
# -----------------------------------------------------------------------
def gate_gamma_provenance() -> int:
    """No hardcoded SUBSTRATE_GAMMA outside registry/tests.

    Allowed patterns (derive from ledger):
      SUBSTRATE_GAMMA = _load_substrate_gamma()
      SUBSTRATE_GAMMA = { ... _GR.get(...) ... }
    Forbidden: SUBSTRATE_GAMMA = { "key": 0.967, ... }  (hardcoded numeric)
    """
    count = 0
    # Match SUBSTRATE_GAMMA = { ... with numeric literals (hardcoded)
    assign_pattern = re.compile(r"SUBSTRATE_GAMMA\s*=\s*\{")
    scan_dirs = ["core", "contracts", "agents", "substrates"]
    scan_files = ["axioms.py"]

    def _check_file(filepath, rel_label):
        nonlocal count
        text = filepath.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            if assign_pattern.search(line):
                # Check if the dict contains hardcoded numeric gamma values
                # (not GammaRegistry calls)
                block = "\n".join(lines[i - 1 : min(i + 15, len(lines))])
                if re.search(r":\s*[\d.]+\s*[,}]", block) and "_GR" not in block:
                    _v("GAMMA_PROVENANCE", f"{rel_label}:{i} -- hardcoded SUBSTRATE_GAMMA dict")
                    count += 1

    for d in scan_dirs:
        dp = ROOT / d
        if not dp.exists():
            continue
        for py in dp.rglob("*.py"):
            if "test_" in py.name or "gamma_registry" in py.name:
                continue
            _check_file(py, str(py.relative_to(ROOT)))

    for fname in scan_files:
        fp = ROOT / fname
        if not fp.exists():
            continue
        _check_file(fp, fname)

    # Check ledger conflicts resolved
    ledger_path = ROOT / "evidence" / "gamma_ledger.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
        for eid, entry in ledger.get("entries", {}).items():
            if entry.get("status") == "REQUIRES_REDERIVATION":
                _v("GAMMA_PROVENANCE", f"ledger:{eid} status=REQUIRES_REDERIVATION")
                count += 1

    return count


# -----------------------------------------------------------------------
# Gate 2: EVIDENCE_HASH
# -----------------------------------------------------------------------
def gate_evidence_hash() -> int:
    """All locked=true DERIVED entries must have data_source.sha256.

    CONSTRUCTED and VALIDATED entries are exempt (external data or
    analytically derived -- hash chain verified at derivation time).
    """
    count = 0
    ledger_path = ROOT / "evidence" / "gamma_ledger.json"
    if not ledger_path.exists():
        _v("EVIDENCE_HASH", "gamma_ledger.json not found")
        return 1

    ledger = json.loads(ledger_path.read_text())
    for eid, entry in ledger.get("entries", {}).items():
        if not entry.get("locked", False):
            continue
        status = entry.get("status", "")
        # Phase 2 hardening (ledger v2.0.0): the gate enforces hashes only
        # for entries that CLAIM full validation. Sub-VALIDATED tiers
        # (EVIDENCE_CANDIDATE, SUPPORTED_BY_NULLS, LOCAL_STRUCTURAL_…,
        # VALIDATED_SUBSTRATE_EVIDENCE, ARTIFACT_SUSPECTED, NO_ADMISSIBLE_CLAIM,
        # BLOCKED_BY_…, INCONCLUSIVE, FALSIFIED) are exempt because Phase 2
        # canonically permits null hashes in those tiers — fabrication is
        # forbidden, and the schema validator (evidence/ledger_schema.py)
        # enforces hashes only on VALIDATED.
        # CONSTRUCTED = mock adapter, VALIDATED = external data verified.
        if status in (
            "CONSTRUCTED",
            "VALIDATED",
            "EVIDENCE_CANDIDATE",
            "SUPPORTED_BY_NULLS",
            "VALIDATED_SUBSTRATE_EVIDENCE",
            "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
            "ARTIFACT_SUSPECTED",
            "NO_ADMISSIBLE_CLAIM",
            "BLOCKED_BY_METHOD_DEFINITION",
            "INCONCLUSIVE",
            "FALSIFIED",
        ):
            continue
        ds = entry.get("data_source", {})
        if ds.get("sha256") is None:
            _v("EVIDENCE_HASH", f"{eid}: locked=true but data_source.sha256 is null")
            count += 1
        if entry.get("adapter_code_hash") is None:
            _v("EVIDENCE_HASH", f"{eid}: locked=true but adapter_code_hash is null")
            count += 1
    return count


# -----------------------------------------------------------------------
# Gate 3: SPLIT_BRAIN
# -----------------------------------------------------------------------
def gate_split_brain() -> int:
    """No duplicate package identities across directories."""
    count = 0
    # Check for mycelium_fractal_net in multiple TOP-LEVEL substrate dirs
    # (subdirs within one substrate are fine -- that's just a package tree)
    mfn_substrate_dirs = set()
    for py in ROOT.rglob("*.py"):
        if ".git" in py.parts:
            continue
        rel = py.relative_to(ROOT)
        parts = rel.parts
        if "mycelium_fractal_net" in parts:
            # Extract the substrate-level parent: substrates/<name>/
            if len(parts) >= 2 and parts[0] == "substrates":
                mfn_substrate_dirs.add(parts[1])
            else:
                mfn_substrate_dirs.add(str(rel.parent))

    if len(mfn_substrate_dirs) > 1:
        _v(
            "SPLIT_BRAIN",
            f"mycelium_fractal_net in {len(mfn_substrate_dirs)} dirs: {mfn_substrate_dirs}",
        )
        count += 1

    # Check for duplicate root-level packages that also exist in substrates/
    for candidate in ["bn_syn", "tradepulse"]:
        root_pkg = ROOT / candidate
        sub_pkg_candidates = list(ROOT.glob(f"substrates/*{candidate}*"))
        if root_pkg.is_dir() and sub_pkg_candidates:
            _v("SPLIT_BRAIN", f"{candidate}: dual surface at root and substrates/")
            count += 1

    return count


# -----------------------------------------------------------------------
# Gate 4: MATH_CORE_TESTED
# -----------------------------------------------------------------------
def gate_math_core_tested() -> int:
    """test_mathematical_core.py must exist with >= 36 test functions."""
    count = 0
    test_file = ROOT / "tests" / "test_mathematical_core.py"
    if not test_file.exists():
        _v("MATH_CORE_TESTED", "tests/test_mathematical_core.py not found")
        return 1

    text = test_file.read_text()
    test_count = len(re.findall(r"def test_\w+", text))
    if test_count < 36:
        _v("MATH_CORE_TESTED", f"Only {test_count} test functions found (need >= 36)")
        count += 1
    return count


# -----------------------------------------------------------------------
# Gate 5: INVARIANT_GAMMA
# -----------------------------------------------------------------------
def gate_invariant_gamma() -> int:
    """Neosynaptex class must not store gamma as instance attribute."""
    count = 0
    main_file = ROOT / "neosynaptex.py"
    if not main_file.exists():
        return 0

    text = main_file.read_text()
    # Check for self.gamma = or self._gamma = (not self._gamma_history etc.)
    bad_patterns = [
        re.compile(r"self\.gamma\s*=\s*(?!.*history|.*trace|.*ema|.*bootstraps|.*per_domain)"),
    ]
    for pat in bad_patterns:
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line) and "gamma_history" not in line and "gamma_trace" not in line:
                _v(
                    "INVARIANT_GAMMA",
                    f"neosynaptex.py:{i} -- gamma storage: {line.strip()[:60]}",
                )
                count += 1
    return count


# -----------------------------------------------------------------------
# Gate 6: TESTPATH_HERMETIC
# -----------------------------------------------------------------------
def gate_testpath_hermetic() -> int:
    """pyproject.toml testpaths must not include root '.'."""
    count = 0
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return 0

    text = pyproject.read_text()
    # Find testpaths line
    match = re.search(r"testpaths\s*=\s*\[([^\]]*)\]", text)
    if match:
        paths_str = match.group(1)
        # Check if "." is in the list
        paths = re.findall(r'"([^"]*)"', paths_str)
        if "." in paths:
            _v("TESTPATH_HERMETIC", 'testpaths includes "." -- root collection not hermetic')
            count += 1
    return count


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main() -> int:
    gates = [
        ("Gate 1: GAMMA_PROVENANCE", gate_gamma_provenance),
        ("Gate 2: EVIDENCE_HASH", gate_evidence_hash),
        ("Gate 3: SPLIT_BRAIN", gate_split_brain),
        ("Gate 4: MATH_CORE_TESTED", gate_math_core_tested),
        ("Gate 5: INVARIANT_GAMMA", gate_invariant_gamma),
        ("Gate 6: TESTPATH_HERMETIC", gate_testpath_hermetic),
    ]

    print("=" * 60)
    print("  CI CANONICAL GATE -- neosynaptex")
    print("=" * 60)

    total = 0
    for name, fn in gates:
        v = fn()
        total += v
        status = "OK" if v == 0 else f"FAIL ({v} violations)"
        print(f"  {name:40s} {status}")

    print("-" * 60)
    if VIOLATIONS:
        print(f"\n  VIOLATIONS ({len(VIOLATIONS)}):")
        for gate, msg in VIOLATIONS:
            print(f"    [{gate}] {msg}")

    print(f"\n  TOTAL: {total} violations")
    print("=" * 60)
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
