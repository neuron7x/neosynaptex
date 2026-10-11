"""γ specificity probe — does γ ≈ 1 require criticality?

Feeds the repository's own estimators with generators that are **non-critical by
construction** (linear Gaussian processes, an algebraic identity) and records
where γ̂ lands relative to the METASTABLE band ``|γ − 1| < 0.15`` of
``core.gamma.compute_gamma``.

Hypothesis under test (H_spec): "γ̂ inside the METASTABLE band is specific to
critical / metastable dynamics."

Falsifier: any non-critical generator whose mean γ̂ over the locked seeds lies
inside the band. One such generator suffices.

Synthetic input only. No substrate data is read; no substrate claim is made or
supported by this output.

Estimators exercised (unchanged, imported from the tree):
  * ``substrates.physionet_hrv.hrv_gamma_fit.fit_hrv_gamma`` — Welch PSD,
    VLF band, Theil–Sen on log–log.
  * ``core.gamma.compute_gamma`` — Theil–Sen on log(topo) vs log(cost).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.gamma import compute_gamma  # noqa: E402
from substrates.physionet_hrv.hrv_gamma_fit import fit_hrv_gamma  # noqa: E402

EVIDENCE_PATH = REPO_ROOT / "results" / "gamma_specificity" / "run_v1.json"
THIS_FILE = Path(__file__).resolve()

# Pre-registered constants — do NOT change after observing outputs.
SEED = 20261011
N_SEEDS = 10
N_BEATS = 20000  # matches the rr_truncate used by the HRV replications
BAND_HALF_WIDTH = 0.15  # METASTABLE band of core.gamma.compute_gamma
AR1_PHIS = (0.5, 0.8, 0.9, 0.95, 0.98)
POWERLAW_BETAS = (0.0, 0.5, 1.0, 1.5, 2.0)
N_PAIRS = 400


def hash_self() -> str:
    return hashlib.sha256(THIS_FILE.read_bytes()).hexdigest()


def ar1(phi: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Stationary AR(1): exponential correlations, finite correlation time."""
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def powerlaw_noise(beta: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Linear Gaussian noise with S(f) ∝ f^(−β): random phases, no dynamics."""
    f = np.fft.rfftfreq(n)
    f[0] = f[1]
    spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * f ** (-beta / 2)
    return np.fft.irfft(spec, n)


def as_rr(x: np.ndarray) -> np.ndarray:
    """Map a zero-mean series onto a plausible RR scale (0.8 s ± 0.04 s)."""
    z = (x - x.mean()) / x.std()
    return 0.8 + 0.04 * z


def in_band(gamma: float) -> bool:
    return bool(np.isfinite(gamma) and abs(gamma - 1.0) < BAND_HALF_WIDTH)


def spectral_cases() -> list[dict]:
    cases = [(f"ar1_phi_{p}", "ar1", p) for p in AR1_PHIS]
    cases += [(f"powerlaw_beta_{b}", "powerlaw", b) for b in POWERLAW_BETAS]
    out = []
    for idx, (name, kind, param) in enumerate(cases):
        gammas = []
        for s in range(N_SEEDS):
            rng = np.random.default_rng([SEED, idx, s])
            x = ar1(param, N_BEATS, rng) if kind == "ar1" else powerlaw_noise(param, N_BEATS, rng)
            gammas.append(float(fit_hrv_gamma(as_rr(x), bootstrap_n=0).gamma))
        mean = float(np.mean(gammas))
        out.append(
            {
                "name": name,
                "generator": kind,
                "parameter": param,
                "critical_by_construction": False,
                "estimator": "fit_hrv_gamma",
                "gammas": [round(g, 6) for g in gammas],
                "gamma_mean": round(mean, 6),
                "gamma_sd": round(float(np.std(gammas)), 6),
                "n_seeds_in_band": int(sum(in_band(g) for g in gammas)),
                "mean_in_metastable_band": in_band(mean),
            }
        )
    return out


def pair_cases() -> list[dict]:
    out = []
    rng = np.random.default_rng([SEED, 1000])
    topo = rng.normal(1.0, 0.15, N_PAIRS).clip(0.3)
    specs = [
        ("cost_is_reciprocal_of_topo", topo, 1.0 / topo, "cost := 1/topo — algebraic identity"),
        (
            "cost_is_reciprocal_of_shuffled_topo",
            topo,
            1.0 / rng.permutation(topo),
            "same marginals, pairing destroyed",
        ),
        (
            "independent_lognormal",
            np.exp(rng.uniform(0, 2, N_PAIRS)),
            np.exp(rng.standard_normal(N_PAIRS)),
            "independent draws",
        ),
    ]
    for name, t, c, note in specs:
        r = compute_gamma(t, c)
        gamma = float(r.gamma)
        out.append(
            {
                "name": name,
                "note": note,
                "critical_by_construction": False,
                "estimator": "core.gamma.compute_gamma",
                "gamma": None if not np.isfinite(gamma) else round(gamma, 6),
                "r2": None if not np.isfinite(r.r2) else round(float(r.r2), 6),
                "verdict": r.verdict,
                "mean_in_metastable_band": r.verdict == "METASTABLE",
            }
        )
    return out


def decide(spectral: list[dict], pairs: list[dict]) -> tuple[str, str]:
    hits = [c["name"] for c in spectral + pairs if c["mean_in_metastable_band"]]
    if hits:
        return (
            "NOT_SPECIFIC",
            f"{len(hits)} non-critical generator(s) land in the METASTABLE band: " + ", ".join(hits),
        )
    return "NO_COUNTEREXAMPLE_FOUND", "no tested non-critical generator reached the band"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=EVIDENCE_PATH)
    ns = ap.parse_args(argv)

    spectral = spectral_cases()
    pairs = pair_cases()
    verdict, reason = decide(spectral, pairs)
    payload = {
        "schema": "gamma_specificity_v1",
        "source_sha256": hash_self(),
        "claim_status": "measured",
        "scope": "synthetic non-critical generators only; no substrate data, no substrate claim",
        "hypothesis": "gamma in the METASTABLE band is specific to critical dynamics",
        "falsifier": "any non-critical generator with mean gamma inside the band",
        "config": {
            "SEED": SEED,
            "N_SEEDS": N_SEEDS,
            "N_BEATS": N_BEATS,
            "BAND_HALF_WIDTH": BAND_HALF_WIDTH,
            "AR1_PHIS": list(AR1_PHIS),
            "POWERLAW_BETAS": list(POWERLAW_BETAS),
            "N_PAIRS": N_PAIRS,
        },
        "spectral_cases": spectral,
        "pair_cases": pairs,
        "specificity_verdict": verdict,
        "specificity_reason": reason,
    }
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(payload, indent=2) + "\n")
    for c in spectral:
        print(f"{c['name']:24s} γ̂ = {c['gamma_mean']:+.3f} ± {c['gamma_sd']:.3f}  "
              f"in-band seeds {c['n_seeds_in_band']}/{N_SEEDS}")
    for c in pairs:
        print(f"{c['name']:38s} γ̂ = {c['gamma']}  {c['verdict']}")
    print(f">>> {verdict}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
