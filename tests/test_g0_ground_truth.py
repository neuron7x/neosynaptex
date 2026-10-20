"""G0 harness: the instrument is alive, and the committed evidence is what a rerun gives."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXP = REPO_ROOT / "experiments" / "g0_ground_truth"
RUN_PATH = EXP / "run.py"
PREREG_PATH = EXP / "PREREGISTRATION.md"
EVIDENCE_PATH = REPO_ROOT / "results" / "g0_ground_truth" / "run_v1.json"


def _mod():
    name = "g0_ground_truth_run"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, RUN_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _iaaft_p(mod, x: np.ndarray, stat: str, seed: int, m: int = 99) -> float:
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(m):
        out = mod.iaaft_surrogate(x, rng=rng)
        null.append(mod.STAT_FN[stat](np.asarray(out[0] if isinstance(out, tuple) else out, float)))
    return mod.rank_p(mod.STAT_FN[stat](x), np.array(null))


def test_instrument_can_reject_a_known_nonlinear_series() -> None:
    """Liveness: without this, 'no rejection' in the evidence would be uninformative."""
    mod = _mod()
    rng = np.random.default_rng(7)
    # Sawtooth relaxation: slow ramp, fast reset — strongly time-irreversible.
    x = (np.arange(4096) % 37) / 37.0 + 0.05 * rng.standard_normal(4096)
    assert _iaaft_p(mod, x, "trev", seed=1) <= 0.02


def test_instrument_stays_silent_on_white_noise() -> None:
    mod = _mod()
    x = np.random.default_rng(11).standard_normal(4096)
    assert _iaaft_p(mod, x, "trev", seed=2) > 0.02


def test_rank_p_floor_and_symmetry() -> None:
    mod = _mod()
    null = np.arange(99, dtype=float)
    assert mod.rank_p(-1.0, null) == pytest.approx(0.02)
    assert mod.rank_p(1000.0, null) == pytest.approx(0.02)
    assert mod.rank_p(49.0, null) == 1.0


def test_lzc_orders_constant_below_random() -> None:
    mod = _mod()
    periodic = np.tile([0.0, 1.0], 2048)
    noise = np.random.default_rng(3).standard_normal(4096)
    assert mod.stat_lzc(periodic) < 0.1 < mod.stat_lzc(noise)


def test_pilot_cannot_write_evidence() -> None:
    proc = subprocess.run(
        [sys.executable, str(RUN_PATH), "--pilot"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert proc.returncode != 0


def test_evidence_is_bound_to_harness_and_preregistration() -> None:
    ev = json.loads(EVIDENCE_PATH.read_text())
    assert ev["pilot"] is False
    assert ev["source_sha256"] == hashlib.sha256(RUN_PATH.read_bytes()).hexdigest()
    assert ev["preregistration_sha256"] == hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()


def test_verdict_is_recomputed_from_committed_records() -> None:
    mod = _mod()
    ev = json.loads(EVIDENCE_PATH.read_text())
    nan = float("nan")
    records = [
        {
            **r,
            "stats": {k: (nan if v is None else v) for k, v in r["stats"].items()},
            **(
                {"p": {k: (nan if v is None else v) for k, v in r["p"].items()}} if "p" in r else {}
            ),
        }
        for r in ev["records"]
    ]
    again = mod.evaluate(records, ev["config"]["N_SEEDS"])
    assert again["verdict"] == ev["verdict"]
    assert again["passed"] == ev["passed"]
    assert ev["verdict"] in {"G0_PASS", "G0_FAIL", "VOID_METHOD"}


@pytest.mark.slow
def test_fresh_run_reproduces_committed_evidence(tmp_path: pathlib.Path) -> None:
    before = EVIDENCE_PATH.read_bytes()
    out = tmp_path / "run.json"
    proc = subprocess.run(
        [sys.executable, str(RUN_PATH), "--out", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert EVIDENCE_PATH.read_bytes() == before
    assert json.loads(out.read_text()) == json.loads(before)
