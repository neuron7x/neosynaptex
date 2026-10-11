"""G0 — instrument on ground truth. Implements PREREGISTRATION.md, nothing more.

Every constant below restates the pre-registration (commit aa9b3455). Two
implementation details the pre-registration left open were fixed here before
the first evidential run and do not depend on any output:

* surrogate RNG stream: ``default_rng([MASTER, sim, grid, seed, 1])``;
* linear generators take simulator indices 2 (AR1) and 3 (power-law), grid 0.

Synthetic data only. No substrate claim is made or supported by this output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.iaaft import iaaft_surrogate  # noqa: E402
from substrates.physionet_hrv.hrv_gamma_fit import fit_hrv_gamma  # noqa: E402

EVIDENCE_PATH = REPO_ROOT / "results" / "g0_ground_truth" / "run_v1.json"
THIS_FILE = Path(__file__).resolve()
PREREG_FILE = THIS_FILE.with_name("PREREGISTRATION.md")

# --- pre-registered constants -------------------------------------------------
MASTER_SEED = 20261012
N_SEEDS = 10
N_SURROGATES = 99
N_SAMPLES = 4096
GRID = (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.98)
NEAR, FAR = 0.98, 0.50
KUR_N, KUR_D, KUR_DT, KUR_STRIDE = 500, 0.5, 0.05, 4
BR_H = 1.0
BURN_IN = 2000
AR1_PHI, POWERLAW_BETA = 0.9, 1.0
TRACK_MEDIAN_ABS_RHO = 0.90
P_REJECT = 0.02
B_MIN_REJECTS = 8
C_MAX_REJECTS = 1
CANDIDATES = ("trev", "pe", "lzc")
CONTROL = "gamma"
STATS = CANDIDATES + (CONTROL,)
SIMULATORS = ("kuramoto", "branching")
LINEAR = ("ar1_phi_0.9", "powerlaw_beta_1.0")


# --- generators ---------------------------------------------------------------
def sim_kuramoto(ratio: float, rng: np.random.Generator) -> np.ndarray:
    k = ratio * 2.0 * KUR_D
    theta = rng.uniform(0.0, 2.0 * np.pi, KUR_N)
    noise = np.sqrt(2.0 * KUR_D * KUR_DT)
    out = np.empty(N_SAMPLES)
    total = BURN_IN + N_SAMPLES * KUR_STRIDE
    j = 0
    for step in range(total):
        z = np.exp(1j * theta).mean()
        r, psi = np.abs(z), np.angle(z)
        if step >= BURN_IN and (step - BURN_IN) % KUR_STRIDE == 0:
            out[j] = r
            j += 1
        theta = theta + k * r * np.sin(psi - theta) * KUR_DT + noise * rng.standard_normal(KUR_N)
    return out


def sim_branching(ratio: float, rng: np.random.Generator) -> np.ndarray:
    a = round(BR_H / (1.0 - ratio))
    out = np.empty(N_SAMPLES)
    for step in range(BURN_IN + N_SAMPLES):
        a = rng.poisson(ratio * a + BR_H)
        if step >= BURN_IN:
            out[step - BURN_IN] = a
    return out


def gen_ar1(rng: np.random.Generator) -> np.ndarray:
    e = rng.standard_normal(N_SAMPLES)
    x = np.empty(N_SAMPLES)
    x[0] = e[0]
    for i in range(1, N_SAMPLES):
        x[i] = AR1_PHI * x[i - 1] + e[i]
    return x


def gen_powerlaw(rng: np.random.Generator) -> np.ndarray:
    f = np.fft.rfftfreq(N_SAMPLES)
    f[0] = f[1]
    spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * f ** (
        -POWERLAW_BETA / 2
    )
    return np.fft.irfft(spec, N_SAMPLES)


# --- statistics ---------------------------------------------------------------
def stat_trev(x: np.ndarray) -> float:
    d = np.diff(x)
    den = np.mean(d**2) ** 1.5
    return float(np.mean(d**3) / den) if den > 0 else float("nan")


def stat_pe(x: np.ndarray, order: int = 4) -> float:
    win = np.lib.stride_tricks.sliding_window_view(x, order)
    ranks = np.argsort(win, axis=1, kind="stable")
    codes = (ranks * (order ** np.arange(order))).sum(axis=1)
    _, counts = np.unique(codes, return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum() / np.log2(24))


def stat_lzc(x: np.ndarray) -> float:
    s = (x > np.median(x)).astype(np.uint8).tobytes()
    n = len(s)
    i, c = 0, 0
    while i < n:
        k = 1
        while i + k <= n and s.find(s[i : i + k], 0, i + k - 1) != -1:
            k += 1
        c += 1
        i += k
    return float(c * np.log2(n) / n)


def stat_gamma(x: np.ndarray) -> float:
    sd = x.std()
    if not sd > 0:
        return float("nan")
    rr = 0.8 + 0.04 * (x - x.mean()) / sd
    try:
        return float(fit_hrv_gamma(rr, bootstrap_n=0).gamma)
    except Exception:  # noqa: BLE001 — recorded as NaN, counted as non-rejection
        return float("nan")


STAT_FN = {"trev": stat_trev, "pe": stat_pe, "lzc": stat_lzc, "gamma": stat_gamma}


def all_stats(x: np.ndarray) -> dict[str, float]:
    return {name: STAT_FN[name](x) for name in STATS}


def rank_p(orig: float, null: np.ndarray) -> float:
    null = null[np.isfinite(null)]
    if not np.isfinite(orig) or len(null) == 0:
        return float("nan")
    lo = 1 + int(np.sum(null <= orig))
    hi = 1 + int(np.sum(null >= orig))
    return min(1.0, 2.0 * min(lo, hi) / (len(null) + 1))


# --- one unit of work ---------------------------------------------------------
def make_series(sim: int, grid: int, seed: int, master: int) -> np.ndarray:
    rng = np.random.default_rng([master, sim, grid, seed])
    if sim == 0:
        return sim_kuramoto(GRID[grid], rng)
    if sim == 1:
        return sim_branching(GRID[grid], rng)
    return gen_ar1(rng) if sim == 2 else gen_powerlaw(rng)


def work(task: tuple[int, int, int, int, int, bool]) -> dict:
    sim, grid, seed, master, n_surr, with_surrogates = task
    x = make_series(sim, grid, seed, master)
    rec: dict = {"sim": sim, "grid": grid, "seed": seed, "stats": all_stats(x)}
    if with_surrogates:
        rng = np.random.default_rng([master, sim, grid, seed, 1])
        null: dict[str, list[float]] = {name: [] for name in STATS}
        for _ in range(n_surr):
            out = iaaft_surrogate(x, rng=rng)
            surr = out[0] if isinstance(out, tuple) else out
            for name, value in all_stats(np.asarray(surr, dtype=float)).items():
                null[name].append(value)
        rec["p"] = {name: rank_p(rec["stats"][name], np.array(null[name])) for name in STATS}
        rec["null_mean"] = {name: float(np.nanmean(null[name])) for name in STATS}
    return rec


# --- evaluation ---------------------------------------------------------------
def rejects(ps: list[float]) -> int:
    return int(sum(1 for p in ps if np.isfinite(p) and p <= P_REJECT))


def evaluate(records: list[dict], n_seeds: int) -> dict:
    by = {(r["sim"], r["grid"], r["seed"]): r for r in records}
    d = [1.0 - g for g in GRID]
    near, far = GRID.index(NEAR), GRID.index(FAR)
    per_stat: dict = {}
    for name in STATS:
        entry: dict = {"simulators": {}, "linear": {}}
        for si, sim_name in enumerate(SIMULATORS):
            rhos = []
            for s in range(n_seeds):
                vals = [by[(si, g, s)]["stats"][name] for g in range(len(GRID))]
                rho = spearmanr(d, vals).statistic if np.all(np.isfinite(vals)) else float("nan")
                rhos.append(float(rho))
            finite = [r for r in rhos if np.isfinite(r)]
            med = float(np.median(np.abs(finite))) if finite else float("nan")
            same_sign = len(finite) == n_seeds and (
                all(r > 0 for r in finite) or all(r < 0 for r in finite)
            )
            n_near = rejects([by[(si, near, s)]["p"][name] for s in range(n_seeds)])
            n_far = rejects([by[(si, far, s)]["p"][name] for s in range(n_seeds)])
            entry["simulators"][sim_name] = {
                "rho_per_seed": [round(r, 4) for r in rhos],
                "median_abs_rho": round(med, 4),
                "same_sign_all_seeds": bool(same_sign),
                "a_tracking": bool(np.isfinite(med) and med >= TRACK_MEDIAN_ABS_RHO and same_sign),
                "rejects_near": n_near,
                "b_beyond_spectrum": n_near >= B_MIN_REJECTS,
                "rejects_far_informational": n_far,
                "mean_by_grid": [
                    round(float(np.nanmean([by[(si, g, s)]["stats"][name] for s in range(n_seeds)])), 6)
                    for g in range(len(GRID))
                ],
            }
        for li, lin_name in enumerate(LINEAR):
            n_lin = rejects([by[(2 + li, 0, s)]["p"][name] for s in range(n_seeds)])
            entry["linear"][lin_name] = {"rejects": n_lin, "c_silent": n_lin <= C_MAX_REJECTS}
        entry["passes_g0"] = bool(
            all(v["a_tracking"] and v["b_beyond_spectrum"] for v in entry["simulators"].values())
            and all(v["c_silent"] for v in entry["linear"].values())
        )
        per_stat[name] = entry
    control_broken = any(v["b_beyond_spectrum"] for v in per_stat[CONTROL]["simulators"].values())
    passed = [name for name in CANDIDATES if per_stat[name]["passes_g0"]]
    if control_broken:
        verdict = "VOID_METHOD"
    elif passed:
        verdict = "G0_PASS"
    else:
        verdict = "G0_FAIL"
    return {"per_statistic": per_stat, "passed": passed, "verdict": verdict}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=EVIDENCE_PATH)
    ap.add_argument("--pilot", action="store_true", help="2 seeds, M=19, master seed 999")
    ap.add_argument("--workers", type=int, default=8)
    ns = ap.parse_args(argv)
    if ns.pilot and ns.out == EVIDENCE_PATH:
        ap.error("--pilot must not write to the evidence path; pass --out")
    master, n_seeds, n_surr = (999, 2, 19) if ns.pilot else (MASTER_SEED, N_SEEDS, N_SURROGATES)

    surrogate_grids = {GRID.index(NEAR), GRID.index(FAR)}
    tasks = [
        (si, g, s, master, n_surr, g in surrogate_grids)
        for si in range(len(SIMULATORS))
        for g in range(len(GRID))
        for s in range(n_seeds)
    ] + [(2 + li, 0, s, master, n_surr, True) for li in range(len(LINEAR)) for s in range(n_seeds)]
    with ProcessPoolExecutor(max_workers=ns.workers) as pool:
        records = list(pool.map(work, tasks))
    records.sort(key=lambda r: (r["sim"], r["grid"], r["seed"]))

    result = evaluate(records, n_seeds)
    payload = {
        "schema": "g0_ground_truth_v1",
        "pilot": bool(ns.pilot),
        "source_sha256": hashlib.sha256(THIS_FILE.read_bytes()).hexdigest(),
        "preregistration_sha256": hashlib.sha256(PREREG_FILE.read_bytes()).hexdigest(),
        "claim_status": "measured",
        "scope": "two simulators with analytically known critical points; synthetic only",
        "config": {
            "MASTER_SEED": master,
            "N_SEEDS": n_seeds,
            "N_SURROGATES": n_surr,
            "N_SAMPLES": N_SAMPLES,
            "GRID": list(GRID),
            "KURAMOTO": {"N": KUR_N, "D": KUR_D, "dt": KUR_DT, "stride": KUR_STRIDE},
            "BRANCHING": {"h": BR_H},
            "BURN_IN": BURN_IN,
            "TRACK_MEDIAN_ABS_RHO": TRACK_MEDIAN_ABS_RHO,
            "P_REJECT": P_REJECT,
            "B_MIN_REJECTS": B_MIN_REJECTS,
            "C_MAX_REJECTS": C_MAX_REJECTS,
        },
        **result,
        "records": [
            {
                **{k: r[k] for k in ("sim", "grid", "seed")},
                "stats": {k: (None if not np.isfinite(v) else round(v, 6)) for k, v in r["stats"].items()},
                **(
                    {"p": {k: (None if not np.isfinite(v) else round(v, 4)) for k, v in r["p"].items()}}
                    if "p" in r
                    else {}
                ),
            }
            for r in records
        ],
    }
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(payload, indent=1) + "\n")

    for name in STATS:
        e = result["per_statistic"][name]
        row = "  ".join(
            f"{sn[:3]}: |rho|={v['median_abs_rho']:.2f}{'=' if v['same_sign_all_seeds'] else '~'} "
            f"near {v['rejects_near']}/{n_seeds} far {v['rejects_far_informational']}/{n_seeds}"
            for sn, v in e["simulators"].items()
        )
        lin = "  ".join(f"{ln.split('_')[0]} {v['rejects']}/{n_seeds}" for ln, v in e["linear"].items())
        print(f"{name:6s} {row}  | linear: {lin}  | pass={e['passes_g0']}")
    print(f">>> {result['verdict']}  passed={result['passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
