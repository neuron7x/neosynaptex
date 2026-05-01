"""Tests for the M-bridge claim status registry and lint tool."""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "contracts" / "M_BRIDGE_CLAIM_STATUS.yaml"
LINT_PATH = REPO_ROOT / "tools" / "audit" / "m_bridge_claim_lint.py"
STATUS_DOC_PATH = REPO_ROOT / "docs" / "reports" / "M_INVARIANT_BRIDGE_STATUS.md"
ROADMAP_DOC_PATH = REPO_ROOT / "docs" / "roadmap" / "M_INVARIANT_M2_ROADMAP.md"


def _load_lint_module():
    if "m_bridge_claim_lint" in sys.modules:
        return sys.modules["m_bridge_claim_lint"]
    spec = importlib.util.spec_from_file_location("m_bridge_claim_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["m_bridge_claim_lint"] = mod  # required for @dataclass module lookup on Py>=3.12
    spec.loader.exec_module(mod)
    return mod


def test_registry_file_exists() -> None:
    assert REGISTRY_PATH.exists(), f"missing {REGISTRY_PATH}"


def test_registry_parses_and_has_required_keys() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    assert isinstance(data, dict)
    for key in (
        "claim_family",
        "current_status",
        "last_experiment",
        "allowed_claims",
        "forbidden_claims",
        "next_candidate_paths",
        "forbidden_post_hoc_actions",
    ):
        assert key in data, f"registry missing key: {key}"
    assert data["claim_family"] == "m_invariant_bridge"
    assert data["current_status"] == "OPEN_NARROWED"
    assert str(data["last_experiment"]["pr"]) == "171"
    assert data["last_experiment"]["verdict"] == "INVALID_HWI"


def test_registry_has_required_forbidden_claims() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    expected = {
        "M is universal",
        "Turing Gap closed",
        "MFN and BN-Syn share M invariant",
        "M=1.0 proves convergence",
        "INVALID_HWI supports the bridge",
    }
    assert expected.issubset(set(data["forbidden_claims"])), (
        "forbidden_claims missing one or more required entries"
    )


def test_registry_has_two_candidate_paths() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    paths = data["next_candidate_paths"]
    assert "spatial_embedding_2d" in paths
    assert "scale_invariant_operator" in paths
    for key, sub in paths.items():
        assert sub.get("status") == "candidate", f"{key} must be candidate"
        assert sub.get("required_before_measurement"), f"{key} missing preconditions"


def test_status_doc_exists_and_states_invalid_hwi() -> None:
    assert STATUS_DOC_PATH.exists(), f"missing {STATUS_DOC_PATH}"
    text = STATUS_DOC_PATH.read_text()
    assert "INVALID_HWI" in text
    assert "OPEN_NARROWED" in text or "OPEN_NARROWED" in REGISTRY_PATH.read_text()
    # explicit anti-claims must be present (under disavowal context)
    assert "M is universal" in text
    assert "Turing Gap closed" in text


def test_lint_passes_on_current_repo() -> None:
    mod = _load_lint_module()
    rc = subprocess.run(
        [sys.executable, str(LINT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0, f"lint should pass on current repo state (rc={rc})"
    _ = mod  # ensure module importable too


def test_lint_rejects_synthetic_bad_doc(tmp_path: pathlib.Path) -> None:
    """A synthetic doc that asserts a forbidden claim positively must fail lint."""
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "contracts").mkdir()
    (sandbox / "docs").mkdir()
    (sandbox / "tools" / "audit").mkdir(parents=True)
    shutil.copy(REGISTRY_PATH, sandbox / "contracts" / REGISTRY_PATH.name)
    shutil.copy(LINT_PATH, sandbox / "tools" / "audit" / LINT_PATH.name)
    bad = sandbox / "docs" / "BAD.md"
    bad.write_text(
        textwrap.dedent(
            """\
            # Results

            We have shown that M is universal across all substrates.
            The Turing Gap closed last week.
            """
        )
    )
    rc = subprocess.run(
        [sys.executable, str(sandbox / "tools" / "audit" / LINT_PATH.name)],
        cwd=sandbox,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 2, f"lint should reject positive forbidden claims (rc={rc})"


def test_lint_allows_forbidden_claim_in_disavowal_context(tmp_path: pathlib.Path) -> None:
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "contracts").mkdir()
    (sandbox / "docs").mkdir()
    (sandbox / "tools" / "audit").mkdir(parents=True)
    shutil.copy(REGISTRY_PATH, sandbox / "contracts" / REGISTRY_PATH.name)
    shutil.copy(LINT_PATH, sandbox / "tools" / "audit" / LINT_PATH.name)
    good = sandbox / "docs" / "REJECTIONS.md"
    good.write_text(
        textwrap.dedent(
            """\
            # Forbidden claims

            The following are rejected:

            - M is universal
            - Turing Gap closed
            """
        )
    )
    rc = subprocess.run(
        [sys.executable, str(sandbox / "tools" / "audit" / LINT_PATH.name)],
        cwd=sandbox,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0, f"lint should allow forbidden claims under disavowal heading (rc={rc})"


def test_lint_rejects_missing_registry(tmp_path: pathlib.Path) -> None:
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "tools" / "audit").mkdir(parents=True)
    shutil.copy(LINT_PATH, sandbox / "tools" / "audit" / LINT_PATH.name)
    rc = subprocess.run(
        [sys.executable, str(sandbox / "tools" / "audit" / LINT_PATH.name)],
        cwd=sandbox,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 3, f"lint should fail with rc=3 on missing registry (rc={rc})"


def test_lint_rejects_status_other_than_open_narrowed(tmp_path: pathlib.Path) -> None:
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "contracts").mkdir()
    (sandbox / "tools" / "audit").mkdir(parents=True)
    shutil.copy(LINT_PATH, sandbox / "tools" / "audit" / LINT_PATH.name)
    bad_registry = yaml.safe_load(REGISTRY_PATH.read_text())
    bad_registry["current_status"] = "CLOSED_PASS"
    (sandbox / "contracts" / REGISTRY_PATH.name).write_text(yaml.safe_dump(bad_registry))
    rc = subprocess.run(
        [sys.executable, str(sandbox / "tools" / "audit" / LINT_PATH.name)],
        cwd=sandbox,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 3, "lint should reject any status other than OPEN_NARROWED until evidence flips it"


def test_roadmap_doc_exists_and_lists_pr_split() -> None:
    assert ROADMAP_DOC_PATH.exists(), f"missing {ROADMAP_DOC_PATH}"
    text = ROADMAP_DOC_PATH.read_text()
    for marker in ("M2.1", "M2.2", "M2.3", "M2.4", "M2.5", "M2.6", "M2.7"):
        assert marker in text, f"roadmap missing {marker}"
    assert "INVALID_HWI" in text
    assert "171" in text


@pytest.mark.parametrize(
    "phrase",
    [
        "M is universal",
        "Turing Gap closed",
        "MFN BN-Syn bridge confirmed",
        "M=1.0 proves convergence",
    ],
)
def test_no_positive_forbidden_phrase_anywhere_in_repo_docs(phrase: str) -> None:
    """Walk docs/ and confirm no positive assertion of common forbidden phrases."""
    mod = _load_lint_module()
    violations = mod.scan_docs([phrase])
    assert violations == [], (
        f"forbidden phrase {phrase!r} appears positively in docs:\n"
        + "\n".join(f"  {v.path}:{v.line_number}: {v.line}" for v in violations)
    )
