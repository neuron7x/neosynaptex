"""neosynaptex -- NFI integrating mirror layer.

Single-file convergence module that observes four NFI subsystems
(BN-Syn, MFN+, PsycheCore, mvstack/GeoSync) and computes cross-domain
coherence diagnostics with scientific rigor: bootstrap CI, permutation
tests, Granger causality, phase portraits, anomaly isolation,
resilience proof, and reflexive modulation signals.

Author: Yaroslav Vasylenko (neuron7xLab)
License: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from scipy.linalg import lstsq as scipy_lstsq
from scipy.spatial import ConvexHull
from scipy.stats import theilslopes

from contracts.provenance import (
    ClaimStatus as _ClaimStatus,
)
from contracts.provenance import (
    EngineMode,
    ensure_admissible,
)
from contracts.provenance import (
    Provenance as _Provenance,
)
from contracts.provenance import (
    ProvenanceClass as _ProvenanceClass,
)
from core.value_function import ValueEstimate, estimate_value

__all__ = [
    "COLLAPSING",
    "CONVERGING",
    "DEGENERATE",
    "DIVERGING",
    "DRIFTING",
    "DomainAdapter",
    "INITIALIZING",
    "METASTABLE",
    "MockBnSynAdapter",
    "MockMarketAdapter",
    "MockMfnAdapter",
    "MockPsycheCoreAdapter",
    "Neosynaptex",
    "NeosynaptexState",
]

__version__ = "3.0.0"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_PAIRS_GAMMA = 5
_LOG_RANGE_GATE = 0.5
_R2_GATE = 0.3  # relaxed from 0.5 to match canonical core.gamma (Hole 4 fix)
_SR_METASTABLE_LO = 0.80
_SR_METASTABLE_HI = 1.25
_SR_DEGENERATE = 1.5
_DEGENERATE_COUNT = 3
_HYSTERESIS_COUNT = 3
_MAX_STATE_KEYS = 4
_TOPO_FLOOR = 0.01
_BOOTSTRAP_N = 500  # unified with canonical core.gamma (was 200, Hole 4 fix)
_PERMUTATION_N = 500
_COND_GATE = 1e6
_EMA_ALPHA = 0.3

# Phase labels
INITIALIZING = "INITIALIZING"
METASTABLE = "METASTABLE"
COLLAPSING = "COLLAPSING"
DIVERGING = "DIVERGING"
DEGENERATE = "DEGENERATE"
CONVERGING = "CONVERGING"
DRIFTING = "DRIFTING"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
class DomainAdapter(Protocol):
    """Interface each NFI subsystem implements."""

    @property
    def domain(self) -> str: ...

    @property
    def state_keys(self) -> list[str]: ...

    def state(self) -> dict[str, float]: ...

    def topo(self) -> float: ...

    def thermo_cost(self) -> float: ...


# ---------------------------------------------------------------------------
# Immutable state snapshot
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NeosynaptexState:
    """Immutable snapshot returned by Neosynaptex.observe().

    Invariant STATE != PROOF: *phi* and *diagnostic* are independent objects.
    Invariant gamma-derived-only: gamma is computed per call, never stored
    on the Neosynaptex instance.
    """

    t: int
    phi: np.ndarray
    phi_per_domain: dict[str, np.ndarray]

    # --- Gamma ---
    gamma_per_domain: dict[str, float]
    gamma_ci_per_domain: dict[str, tuple[float, float]]
    gamma_mean: float
    gamma_std: float
    cross_coherence: float

    # --- Gamma dynamics ---
    dgamma_dt: float
    gamma_ema_per_domain: dict[str, float]

    # --- Universal scaling test ---
    universal_scaling_p: float

    # --- Jacobian ---
    sr_per_domain: dict[str, float]
    cond_per_domain: dict[str, float]
    spectral_radius: float

    # --- Phase ---
    phase: str

    # --- Anomaly isolation ---
    anomaly_score: dict[str, float]

    # --- Granger causality ---
    granger_graph: dict[str, dict[str, float]]

    # --- Phase portrait ---
    portrait: dict[str, float]

    # --- Resilience ---
    resilience_score: float

    # --- Modulation signal ---
    modulation: dict[str, float]

    # --- Full diagnostic ---
    diagnostic: dict[str, Any]

    # --- Cross-domain Jacobian (T3) ---
    cross_jacobian: dict[str, dict[str, float]] | None = None
    cross_jacobian_cond: float = float("nan")
    adaptive_window: int = 16
    ci_width_mean: float = float("nan")

    # --- Internal value function (X8 v2) ---
    value_estimate: ValueEstimate | None = None

    # --- INV-YV1: Gradient Ontology ---
    gradient_diagnosis: str = (
        "unknown"  # living_gradient / static_capacitor / dead_equilibrium / transient
    )

    class _Cfg:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Circular buffer (O(1) push, pre-allocated)
# ---------------------------------------------------------------------------
class _DomainBuffer:
    """Per-domain circular buffer for state, topo, and cost histories."""

    __slots__ = (
        "domain",
        "n",
        "capacity",
        "_state_buf",
        "_topo_buf",
        "_cost_buf",
        "_idx",
        "_full",
        "_total",
    )

    def __init__(self, domain: str, n: int, capacity: int) -> None:
        self.domain = domain
        self.n = n
        self.capacity = capacity
        self._state_buf = np.full((capacity, n), np.nan, dtype=np.float64)
        self._topo_buf = np.full(capacity, np.nan, dtype=np.float64)
        self._cost_buf = np.full(capacity, np.nan, dtype=np.float64)
        self._idx = 0
        self._full = False
        self._total = 0

    def push(self, state_vec: np.ndarray, topo: float, cost: float) -> None:
        """Append one observation. O(1)."""
        self._state_buf[self._idx] = state_vec
        self._topo_buf[self._idx] = topo
        self._cost_buf[self._idx] = cost
        self._idx = (self._idx + 1) % self.capacity
        if not self._full and self._idx == 0:
            self._full = True
        self._total += 1

    @property
    def count(self) -> int:
        return self._total

    @property
    def length(self) -> int:
        """Number of valid entries in the buffer."""
        return self.capacity if self._full else self._idx

    def _ordered(self, buf: np.ndarray) -> np.ndarray:
        """Return buffer contents in chronological order."""
        n = self.length
        if self._full:
            return np.concatenate([buf[self._idx :], buf[: self._idx]])
        return cast(np.ndarray, buf[:n].copy())

    def states_array(self) -> np.ndarray:
        return self._ordered(self._state_buf)

    def topos(self) -> np.ndarray:
        return self._ordered(self._topo_buf)

    def costs(self) -> np.ndarray:
        return self._ordered(self._cost_buf)

    def clear(self) -> None:
        self._state_buf[:] = np.nan
        self._topo_buf[:] = np.nan
        self._cost_buf[:] = np.nan
        self._idx = 0
        self._full = False
        self._total = 0


# ---------------------------------------------------------------------------
# Jacobian helper
# ---------------------------------------------------------------------------
def _per_domain_jacobian(states: np.ndarray) -> tuple[float, float]:
    """Estimate spectral radius and condition number from per-domain state history.

    Formula (temporally aligned):
        dPhi(t)     = Phi(t+1) - Phi(t)
        J_local^T   = lstsq(Phi(t),       dPhi(t))     # solves dPhi(t) ~ Phi(t) @ J^T
        A_transition = J_local + I
        sr          = max |eigenvalues(A_transition)|
        cond        = condition_number(Phi(t))

    The previous implementation paired ``dPhi(t+1)`` with ``Phi(t-1)``,
    which silently biased the solve by one step and could misclassify
    sign-flipping stable systems. The current code pairs ``dPhi(t)``
    with ``Phi(t)`` directly via ``np.diff`` over ``clean``.

    Returns:
        ``(spectral_radius, condition_number)``. Insufficient history,
        NaN contamination, ill-conditioned state matrix, or a failed
        solve all collapse to ``(NaN, NaN)``; callers must treat that
        sentinel as fail-closed (see ``contracts.fail_closed``).
    """
    nan_pair = (float("nan"), float("nan"))
    if states.ndim != 2 or states.size == 0:
        return nan_pair
    mask = np.all(np.isfinite(states), axis=1)
    clean = states[mask]
    n = states.shape[1]
    # Need at least n+2 clean states so the regression has n+1 rows
    # with room to reject degenerate solves.
    if clean.shape[0] < n + 2:
        return nan_pair

    # Synchronous pairing: y[i] = Phi(t_{i+1}) - Phi(t_i) depends on x[i] = Phi(t_i).
    x = clean[:-1]
    y = np.diff(clean, axis=0)

    if x.shape[0] < n + 1:
        return nan_pair

    cond = float(np.linalg.cond(x))
    if not np.isfinite(cond) or cond > _COND_GATE:
        return nan_pair

    try:
        j_t, _, _, _ = scipy_lstsq(x, y)
        a_transition = j_t.T + np.eye(n)
        eigvals = np.linalg.eigvals(a_transition)
        sr = float(np.max(np.abs(eigvals)))
        if not np.isfinite(sr):
            return nan_pair
        return (sr, cond)
    except Exception:
        return nan_pair


# ---------------------------------------------------------------------------
# Per-domain slope helper (used by the modulation loop)
# ---------------------------------------------------------------------------
def _domain_slope(trace: list[float], window: int) -> float:
    """Theil-Sen slope on the last ``window`` finite entries of ``trace``.

    Used by the reflexive modulation loop to compute a *per-domain*
    derivative of gamma, so one domain's dynamics cannot steer another
    domain's actuation. Returns NaN when there is not enough finite
    history to fit a slope; callers interpret NaN as "no actuation".
    """
    if not trace:
        return float("nan")
    recent = [g for g in trace[-window:] if np.isfinite(g)]
    if len(recent) < 5:
        return float("nan")
    x_t = np.arange(len(recent), dtype=np.float64)
    slope, _, _, _ = theilslopes(recent, x_t)
    return float(slope)


# ---------------------------------------------------------------------------
# Gamma helper with bootstrap CI
# ---------------------------------------------------------------------------
def _per_domain_gamma(
    topos: np.ndarray, costs: np.ndarray, seed: int = 0
) -> tuple[float, float, float, float, np.ndarray]:
    """Estimate gamma scaling exponent with bootstrap confidence interval.

    Delegates to canonical core.gamma.compute_gamma() (Hole 4/11 fix).
    Returns bootstrap_gammas for reuse in permutation test (eliminates
    the redundant second bootstrap that was doubling computation).

    Returns:
        (gamma, r2, ci_low, ci_high, bootstrap_gammas).
        Non-passing gates return (NaN, NaN, NaN, NaN, empty_array).
    """
    from core.gamma import compute_gamma as _canonical_gamma

    r = _canonical_gamma(
        topos,
        costs,
        min_pairs=_MIN_PAIRS_GAMMA,
        log_range_gate=_LOG_RANGE_GATE,
        r2_gate=_R2_GATE,
        bootstrap_n=_BOOTSTRAP_N,
        seed=seed,
    )
    # Preserve legacy behavior: return NaN quad for non-passing gates
    if r.verdict in ("INSUFFICIENT_DATA", "INSUFFICIENT_RANGE", "LOW_R2"):
        nan = float("nan")
        return (nan, nan, nan, nan, np.array([]))
    return (r.gamma, r.r2, r.ci_low, r.ci_high, r.bootstrap_gammas)


# ---------------------------------------------------------------------------
# Permutation test for universal scaling
# ---------------------------------------------------------------------------
def _permutation_test_universal(gamma_bootstraps: dict[str, np.ndarray], seed: int = 0) -> float:
    """Test H0: all domains share the same gamma.

    Uses permutation of bootstrap distributions. Returns p-value.
    High p (>0.05) = fail to reject universal scaling.
    """
    domains = [k for k, v in gamma_bootstraps.items() if len(v) > 0]
    if len(domains) < 2:
        return float("nan")

    all_vals = [gamma_bootstraps[d] for d in domains]
    sizes = [len(v) for v in all_vals]
    pooled = np.concatenate(all_vals)

    # Observed test statistic: variance of group means
    observed_means = np.array([v.mean() for v in all_vals])
    observed_stat = np.var(observed_means)

    rng = np.random.default_rng(seed)
    count_ge = 0
    for _ in range(_PERMUTATION_N):
        perm = rng.permutation(pooled)
        groups = np.split(perm, np.cumsum(sizes[:-1]))
        perm_means = np.array([g.mean() for g in groups])
        if np.var(perm_means) >= observed_stat:
            count_ge += 1

    return float((count_ge + 1) / (_PERMUTATION_N + 1))


# ---------------------------------------------------------------------------
# Granger causality (pairwise, lag-1)
# ---------------------------------------------------------------------------
def _granger_causality(
    gamma_history: dict[str, list[float]], min_len: int = 10
) -> dict[str, dict[str, float]]:
    """Pairwise Granger causality F-statistic between domain gamma series.

    For each pair (i, j): does gamma_i(t-1) improve prediction of gamma_j(t)
    beyond gamma_j(t-1) alone?

    Returns dict[source][target] = F-statistic. Higher F = stronger causal link.
    """
    graph: dict[str, dict[str, float]] = {}
    domains = sorted(gamma_history.keys())

    for source in domains:
        graph[source] = {}
        s_vals = np.array(gamma_history[source])
        for target in domains:
            if source == target:
                continue
            t_vals = np.array(gamma_history[target])
            n = min(len(s_vals), len(t_vals))
            if n < min_len:
                graph[source][target] = float("nan")
                continue

            s = s_vals[-n:]
            t = t_vals[-n:]
            # Skip if too many NaN
            valid = np.isfinite(s[:-1]) & np.isfinite(t[:-1]) & np.isfinite(t[1:])
            if valid.sum() < min_len - 2:
                graph[source][target] = float("nan")
                continue

            y = t[1:][valid]
            x_restricted = t[:-1][valid].reshape(-1, 1)
            x_full = np.column_stack([t[:-1][valid], s[:-1][valid]])

            # Restricted model: y ~ t_lag
            try:
                b_r, _, _, _ = scipy_lstsq(x_restricted, y)
                rss_r = float(np.sum((y - x_restricted @ b_r) ** 2))
            except Exception:
                graph[source][target] = float("nan")
                continue

            # Full model: y ~ t_lag + s_lag
            try:
                b_f, _, _, _ = scipy_lstsq(x_full, y)
                rss_f = float(np.sum((y - x_full @ b_f) ** 2))
            except Exception:
                graph[source][target] = float("nan")
                continue

            n_obs = len(y)
            p_full = 2
            p_restricted = 1
            df1 = p_full - p_restricted
            df2 = n_obs - p_full
            if df2 <= 0 or rss_f < 1e-15:
                graph[source][target] = float("nan")
                continue

            f_stat = ((rss_r - rss_f) / df1) / (rss_f / df2)
            graph[source][target] = round(float(f_stat), 4)

    return graph


# ---------------------------------------------------------------------------
# Anomaly isolation (leave-one-out)
# ---------------------------------------------------------------------------
def _anomaly_isolation(gamma_per_domain: dict[str, float]) -> dict[str, float]:
    """Leave-one-out coherence test. Score = how much coherence improves without domain d.

    anomaly_score near 1.0 = domain d is the outlier dragging coherence down.
    anomaly_score near 0.0 = domain d is consistent with the group.
    """
    scores: dict[str, float] = {}
    valid = {k: v for k, v in gamma_per_domain.items() if np.isfinite(v)}

    if len(valid) < 3:
        return {k: float("nan") for k in gamma_per_domain}

    vals = np.array(list(valid.values()))
    full_cv = np.std(vals) / abs(np.mean(vals)) if abs(np.mean(vals)) > 1e-10 else 0.0
    full_coherence = 1.0 - full_cv

    for d in gamma_per_domain:
        if d not in valid:
            scores[d] = float("nan")
            continue
        remaining = np.array([v for k, v in valid.items() if k != d])
        if len(remaining) < 2:
            scores[d] = float("nan")
            continue
        loo_cv = (
            np.std(remaining) / abs(np.mean(remaining)) if abs(np.mean(remaining)) > 1e-10 else 0.0
        )
        loo_coherence = 1.0 - loo_cv
        improvement = loo_coherence - full_coherence
        scores[d] = round(
            float(max(0.0, min(1.0, improvement / max(1.0 - full_coherence, 1e-6)))), 4
        )

    return scores


# ---------------------------------------------------------------------------
# Phase portrait
# ---------------------------------------------------------------------------
def _phase_portrait(gamma_trace: list[float], sr_trace: list[float]) -> dict[str, float]:
    """Compute phase portrait metrics from (gamma, sr) trajectory.

    - area: convex hull area (small = fixed point, large = wandering)
    - recurrence: fraction of points within epsilon of a previous point
    - distance_to_ideal: mean distance to (1.0, 1.0)
    """
    valid_pairs = [
        (g, s) for g, s in zip(gamma_trace, sr_trace) if np.isfinite(g) and np.isfinite(s)
    ]
    if len(valid_pairs) < 4:
        return {"area": float("nan"), "recurrence": float("nan"), "distance_to_ideal": float("nan")}

    pts = np.array(valid_pairs)

    # Convex hull area
    try:
        hull = ConvexHull(pts)
        area = float(hull.volume)  # 2D: volume = area
    except Exception:
        area = 0.0

    # Recurrence rate (epsilon = 0.05) — vectorized distance matrix
    eps = 0.05
    n = len(pts)
    if n > 1:
        diffs = pts[:, np.newaxis, :] - pts[np.newaxis, :, :]
        dists = np.sqrt(np.sum(diffs**2, axis=2))
        # For each point i>0, check if any j<i is within epsilon
        recurrence_count = 0
        for i in range(1, n):
            if np.any(dists[i, :i] < eps):
                recurrence_count += 1
        recurrence = float(recurrence_count / (n - 1))
    else:
        recurrence = 0.0

    # Distance to ideal (1.0, 1.0)
    ideal = np.array([1.0, 1.0])
    distances = np.linalg.norm(pts - ideal, axis=1)
    distance_to_ideal = float(np.mean(distances))

    return {
        "area": round(area, 6),
        "recurrence": round(recurrence, 4),
        "distance_to_ideal": round(distance_to_ideal, 4),
    }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class Neosynaptex:
    """Integrating mirror layer for NFI.

    Observes registered domain adapters and computes:
    - Per-domain gamma with bootstrap CI and Theil-Sen regression
    - Per-domain spectral radius with condition number gating
    - Cross-domain coherence and permutation test of universal scaling
    - Granger causality graph between domains
    - Anomaly isolation (leave-one-out)
    - Phase portrait topology (area, recurrence, distance-to-ideal)
    - Resilience score (return rate after departures from metastability)
    - Reflexive modulation signal (bounded |mod| <= 0.05)
    - Phase with hysteresis (CONVERGING / METASTABLE / DRIFTING / ...)

    Usage::

        nx = Neosynaptex(window=16)
        nx.register(MockBnSynAdapter())
        nx.register(MockMfnAdapter())
        state = nx.observe()
        print(state.phase, state.gamma_mean, state.modulation)
    """

    def __init__(
        self,
        window: int = 16,
        *,
        mode: str | EngineMode = "test",
    ) -> None:
        if window < 8:
            raise ValueError(f"window must be >= 8, got {window}")
        # Resolve and store the operating mode. ``mode`` gates what
        # ``register()`` will accept: REAL / CANONICAL / PROOF /
        # REPLICATION require admissible, real-provenance adapters; the
        # default TEST mode is permissive so existing unit tests and
        # smoke paths keep working unchanged.
        if isinstance(mode, EngineMode):
            self._mode = mode
        else:
            try:
                self._mode = EngineMode(str(mode).strip().lower())
            except ValueError as exc:
                raise ValueError(f"unknown engine mode: {mode!r}") from exc
        self._window = window
        self._adapters: dict[str, DomainAdapter] = {}
        self._buffers: dict[str, _DomainBuffer] = {}
        self._tick = 0

        # Phase hysteresis
        self._confirmed_phase = INITIALIZING
        self._candidate_phase = INITIALIZING
        self._candidate_count = 0
        self._degenerate_count = 0

        # History
        self._history: list[NeosynaptexState] = []
        self._gamma_history: dict[str, list[float]] = {}
        self._gamma_trace: list[float] = []
        self._sr_trace: list[float] = []

        # EMA state
        self._gamma_ema: dict[str, float] = {}

        # Resilience tracking
        self._departures = 0
        self._returns = 0
        self._was_metastable = False

        # Bootstrap cache for permutation test
        self._gamma_bootstraps: dict[str, np.ndarray] = {}

        # Free-energy proxy history for valence (X8 v2)
        self._f_history: list[float] = []

        # Cross-domain Jacobian traces (T3)
        self._gamma_per_domain_trace: list[dict[str, float]] = []
        self._state_mean_trace: list[dict[str, float]] = []
        self._adaptive_window: int = window

        # Proof chain (T4)
        self._chain_root: str = self._load_chain_root()
        self._last_proof_hash: str | None = None
        self._proof_count: int = 0

    @staticmethod
    def _load_chain_root() -> str:
        """Load genesis hash from X1 manifest."""
        manifest = Path(__file__).parent / "evidence_bundle_v1" / "manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text())
            return str(data.get("chain_root", "GENESIS"))
        return "GENESIS"

    def _compute_cross_jacobian(
        self,
        domains: list[str],
    ) -> tuple[dict[str, dict[str, float]], float]:
        """Cross-domain Jacobian: J[i][j] = d(gamma_i)/d(state_mean_j).

        Requires >= 64 ticks. Uses scipy_lstsq. Condition gate < 1e6.
        """
        nan_result: dict[str, dict[str, float]] = {
            d: {d2: float("nan") for d2 in domains} for d in domains
        }
        n_dom = len(domains)
        n_ticks = len(self._gamma_per_domain_trace)

        if n_ticks < 64 or n_dom < 2:
            return nan_result, float("nan")

        x_rows = []
        y_rows = []
        for t in range(n_ticks - 1):
            sm = self._state_mean_trace[t]
            gt = self._gamma_per_domain_trace[t + 1]
            x_row = [sm.get(d, np.nan) for d in domains]
            y_row = [gt.get(d, np.nan) for d in domains]
            if all(np.isfinite(v) for v in x_row) and all(np.isfinite(v) for v in y_row):
                x_rows.append(x_row)
                y_rows.append(y_row)

        if len(x_rows) < n_dom + 1:
            return nan_result, float("nan")

        x_arr = np.array(x_rows)
        y_arr = np.array(y_rows)

        cond = float(np.linalg.cond(x_arr))
        if cond > _COND_GATE:
            return nan_result, cond

        try:
            j_t, _, _, _ = scipy_lstsq(x_arr, y_arr)
            j_cross = j_t.T  # (N, N): J[i][j] = d(gamma_i)/d(state_j)
            result = {
                domains[i]: {domains[j]: round(float(j_cross[i, j]), 6) for j in range(n_dom)}
                for i in range(n_dom)
            }
            return result, cond
        except Exception:
            return nan_result, cond

    def _update_adaptive_window(
        self,
        gamma_ci_per_domain: dict[str, tuple[float, float]],
    ) -> int:
        """Adjust observation window based on mean CI width."""
        widths = []
        for lo, hi in gamma_ci_per_domain.values():
            if np.isfinite(lo) and np.isfinite(hi):
                widths.append(hi - lo)

        if not widths:
            return self._adaptive_window

        mean_width = float(np.mean(widths))

        if mean_width > 0.15:
            new_w = min(int(self._adaptive_window * 1.5), 256)
        elif mean_width < 0.05:
            new_w = max(int(self._adaptive_window / 1.2), 16)
        else:
            new_w = self._adaptive_window

        return new_w

    def _compute_proof_hash(self, proof_dict: dict[str, Any]) -> str:
        """SHA-256 of canonical JSON excluding chain.self_hash."""
        import hashlib

        clean = {k: v for k, v in proof_dict.items() if k != "chain"}
        if "chain" in proof_dict:
            chain_without_self = {k: v for k, v in proof_dict["chain"].items() if k != "self_hash"}
            clean["chain"] = chain_without_self
        canonical = json.dumps(clean, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def mode(self) -> EngineMode:
        """Operating mode of this engine instance (affects registration)."""
        return self._mode

    def register(self, adapter: DomainAdapter) -> None:
        """Register a domain adapter. Max 4 state variables per adapter.

        In REAL / CANONICAL / PROOF / REPLICATION modes, the adapter
        must carry a ``provenance`` attribute declaring
        ``provenance_class == REAL`` and ``claim_status == ADMISSIBLE``.
        Synthetic, mock, and downgraded adapters are rejected at
        registration time via ``contracts.provenance.ensure_admissible``.
        """
        # Provenance gate runs BEFORE any state is mutated, so a
        # rejected registration leaves the engine in its prior state.
        ensure_admissible(adapter, self._mode)
        keys = adapter.state_keys
        if len(keys) > _MAX_STATE_KEYS:
            raise ValueError(
                f"Adapter '{adapter.domain}' has {len(keys)} state keys, max is {_MAX_STATE_KEYS}"
            )
        name = adapter.domain
        if name in self._adapters:
            raise ValueError(f"Domain '{name}' already registered")
        self._adapters[name] = adapter
        self._buffers[name] = _DomainBuffer(name, len(keys), self._window)
        self._gamma_history[name] = []
        self._gamma_ema[name] = float("nan")

    def observe(self) -> NeosynaptexState:
        """Collect state from all adapters, compute full diagnostics.

        Returns immutable NeosynaptexState with gamma CI, Granger causality,
        anomaly isolation, phase portrait, resilience, and modulation signal.
        """
        if not self._adapters:
            raise RuntimeError("No adapters registered. Call register() first.")

        self._tick += 1
        domain_order = sorted(self._adapters.keys())

        # === Layer 1: Collect ===
        phi_parts: list[np.ndarray] = []
        phi_per_domain: dict[str, np.ndarray] = {}

        for name in domain_order:
            adapter = self._adapters[name]
            buf = self._buffers[name]
            s = adapter.state()
            vec = np.array([s.get(k, float("nan")) for k in adapter.state_keys], dtype=np.float64)
            t_val = adapter.topo()
            c_val = adapter.thermo_cost()
            if np.isfinite(t_val) and t_val < _TOPO_FLOOR:
                t_val = _TOPO_FLOOR
            if np.isfinite(c_val) and c_val < _TOPO_FLOOR:
                c_val = _TOPO_FLOOR
            buf.push(vec, t_val, c_val)
            phi_parts.append(vec.copy())
            phi_per_domain[name] = vec.copy()

        phi = np.concatenate(phi_parts)

        # === Layer 2: Per-domain Jacobian with condition number ===
        sr_per_domain: dict[str, float] = {}
        cond_per_domain: dict[str, float] = {}

        for name in domain_order:
            buf = self._buffers[name]
            if buf.length < buf.n + 3:
                sr_per_domain[name] = float("nan")
                cond_per_domain[name] = float("nan")
            else:
                sr, cond = _per_domain_jacobian(buf.states_array())
                sr_per_domain[name] = sr
                cond_per_domain[name] = cond

        sr_valid = [v for v in sr_per_domain.values() if np.isfinite(v)]
        spectral_radius = float(np.median(sr_valid)) if sr_valid else float("nan")

        # === Layer 3: Per-domain gamma with bootstrap CI ===
        gamma_per_domain: dict[str, float] = {}
        gamma_ci_per_domain: dict[str, tuple[float, float]] = {}
        r2_per_domain: dict[str, float] = {}

        for i, name in enumerate(domain_order):
            buf = self._buffers[name]
            g, r2, ci_lo, ci_hi, boot_samples = _per_domain_gamma(
                buf.topos(), buf.costs(), seed=self._tick * 100 + i
            )
            gamma_per_domain[name] = g
            gamma_ci_per_domain[name] = (ci_lo, ci_hi)
            r2_per_domain[name] = r2
            self._gamma_history[name].append(g)

            # Reuse bootstrap samples from canonical computation
            # (eliminates redundant 2nd bootstrap that was doubling cost)
            self._gamma_bootstraps[name] = boot_samples

            # EMA
            if np.isfinite(g):
                prev = self._gamma_ema[name]
                if np.isfinite(prev):
                    self._gamma_ema[name] = _EMA_ALPHA * g + (1 - _EMA_ALPHA) * prev
                else:
                    self._gamma_ema[name] = g

        gamma_ema_per_domain = dict(self._gamma_ema)

        # Cross-domain coherence (clamped to [0, 1])
        gamma_valid = [v for v in gamma_per_domain.values() if np.isfinite(v)]
        if len(gamma_valid) >= 2:
            gamma_mean = float(np.mean(gamma_valid))
            gamma_std = float(np.std(gamma_valid))
            if abs(gamma_mean) > 1e-10:
                cross_coherence = float(np.clip(1.0 - gamma_std / gamma_mean, 0.0, 1.0))
            else:
                cross_coherence = float("nan")
        elif len(gamma_valid) == 1:
            gamma_mean = gamma_valid[0]
            gamma_std = float("nan")
            cross_coherence = float("nan")
        else:
            gamma_mean = float("nan")
            gamma_std = float("nan")
            cross_coherence = float("nan")

        # === dg/dt: gamma convergence rate ===
        self._gamma_trace.append(gamma_mean)
        self._sr_trace.append(spectral_radius)
        dgamma_dt = float("nan")
        if len(self._gamma_trace) >= 5:
            recent = [g for g in self._gamma_trace[-self._window :] if np.isfinite(g)]
            if len(recent) >= 5:
                x_t = np.arange(len(recent), dtype=np.float64)
                slope_g, _, _, _ = theilslopes(recent, x_t)
                dgamma_dt = float(slope_g)

        # === Permutation test for universal scaling ===
        universal_scaling_p = _permutation_test_universal(self._gamma_bootstraps, seed=self._tick)

        # === Granger causality ===
        granger_graph = _granger_causality(self._gamma_history)

        # === Anomaly isolation ===
        anomaly_score = _anomaly_isolation(gamma_per_domain)

        # === Phase portrait ===
        portrait = _phase_portrait(self._gamma_trace, self._sr_trace)

        # === Phase determination with hysteresis ===
        raw_phase = self._raw_phase(spectral_radius, dgamma_dt, gamma_mean)

        if raw_phase == self._confirmed_phase:
            self._candidate_phase = raw_phase
            self._candidate_count = 0
        elif raw_phase == self._candidate_phase:
            self._candidate_count += 1
            if self._candidate_count >= _HYSTERESIS_COUNT:
                self._confirmed_phase = raw_phase
                self._candidate_count = 0
        else:
            self._candidate_phase = raw_phase
            self._candidate_count = 1

        phase = self._confirmed_phase

        # === Resilience tracking ===
        is_meta = phase == METASTABLE
        if self._was_metastable and not is_meta:
            self._departures += 1
        if not self._was_metastable and is_meta and self._departures > 0:
            self._returns += 1
        self._was_metastable = is_meta
        if self._departures > 0:
            resilience_score = float(self._returns / self._departures)
        elif is_meta and self._tick > 1:
            # Never departed from METASTABLE = perfect resilience
            resilience_score = 1.0
        else:
            resilience_score = float("nan")

        # === Reflexive modulation signal (per-domain, deadbanded, smooth) ===
        #
        # The previous version used a single *global* ``dgamma_dt`` and a
        # hard ``sign(dg)`` switch, which (a) let one domain's slope steer
        # another domain's actuation and (b) flipped sign on any jitter
        # around zero. The current version computes a per-domain slope on
        # that domain's own gamma trace, applies a tanh saturating law
        # with a deadband, and bounds the output symmetrically.
        modulation: dict[str, float] = {}
        gamma_target = 1.0
        alpha_mod = 0.05
        eps_dgamma = 1e-3  # deadband half-width; |dg| << eps_dgamma -> no actuation
        modulation_clip = 0.05
        for name in domain_order:
            g = gamma_per_domain[name]
            dg_i = _domain_slope(self._gamma_history[name], self._window)
            if np.isfinite(g) and np.isfinite(dg_i):
                # Smooth saturating control with deadband. tanh(x/eps) is
                # ~linear for |x| << eps (deadband) and saturates to +/-1
                # for |x| >> eps, so micro-slope jitter never produces a
                # discontinuous sign flip.
                u = float(np.tanh(dg_i / eps_dgamma))
                raw_mod = -alpha_mod * (g - gamma_target) * u
                modulation[name] = round(
                    float(np.clip(raw_mod, -modulation_clip, modulation_clip)), 6
                )
            else:
                modulation[name] = 0.0

        # === Value function (X8 v2: 4-signal neuromodulatory) ===
        f_proxy = 1.0 - cross_coherence if np.isfinite(cross_coherence) else 0.5
        self._f_history.append(f_proxy)
        if len(self._f_history) > 10:
            self._f_history = self._f_history[-10:]

        gamma_valid_count = len(gamma_valid)
        n_total_domains = len(domain_order)
        if phase != INITIALIZING and gamma_valid_count > 0 and np.isfinite(gamma_mean):
            value_estimate = estimate_value(
                gamma_mean=gamma_mean,
                spectral_radius=spectral_radius if np.isfinite(spectral_radius) else 1.0,
                cross_coherence=cross_coherence if np.isfinite(cross_coherence) else 0.0,
                n_valid_domains=gamma_valid_count,
                n_total_domains=max(n_total_domains, 1),
                f_history=self._f_history,
            )
        else:
            value_estimate = None

        # === Cross-domain Jacobian + Adaptive Window (T3) ===
        state_means = {
            name: float(np.nanmean(phi_per_domain[name]))
            for name in domain_order
            if name in phi_per_domain
        }
        self._gamma_per_domain_trace.append(dict(gamma_per_domain))
        self._state_mean_trace.append(state_means)
        # Bound traces to prevent memory leak (cross-Jacobian needs 64 ticks)
        _trace_cap = 256
        if len(self._gamma_per_domain_trace) > _trace_cap:
            self._gamma_per_domain_trace = self._gamma_per_domain_trace[-_trace_cap:]
            self._state_mean_trace = self._state_mean_trace[-_trace_cap:]

        cross_jacobian, cross_jacobian_cond = self._compute_cross_jacobian(domain_order)
        self._adaptive_window = self._update_adaptive_window(gamma_ci_per_domain)

        ci_widths = [
            hi - lo
            for lo, hi in gamma_ci_per_domain.values()
            if np.isfinite(lo) and np.isfinite(hi)
        ]
        ci_width_mean = float(np.mean(ci_widths)) if ci_widths else float("nan")

        # === Build diagnostic ===
        diagnostic = {
            "tick": self._tick,
            "sr_per_domain": dict(sr_per_domain),
            "cond_per_domain": dict(cond_per_domain),
            "gamma_per_domain": dict(gamma_per_domain),
            "gamma_ci_per_domain": {k: list(v) for k, v in gamma_ci_per_domain.items()},
            "r2_per_domain": dict(r2_per_domain),
            "n_gamma_valid": len(gamma_valid),
            "dgamma_dt": dgamma_dt,
            "universal_scaling_p": universal_scaling_p,
            "degenerate_count": self._degenerate_count,
            "resilience": {"departures": self._departures, "returns": self._returns},
        }

        # === INV-YV1: Gradient Ontology diagnosis ===
        gradient_diagnosis = "unknown"
        if len(self._history) >= 2:
            from contracts.invariants import enforce_gradient_ontology

            # Build a trajectory from recent phi vectors
            recent_states = self._history[-(self._window) :]
            if len(recent_states) >= 2:
                traj = np.array([s.phi for s in recent_states], dtype=np.float64)
                if traj.ndim == 2 and traj.shape[0] >= 2:
                    eq = np.mean(traj, axis=0)
                    dv = np.linalg.norm(traj - eq, axis=1)
                    alive_frac = float(np.mean(dv > 1e-6))
                    ddv = np.abs(np.diff(dv))
                    dynamic_frac = float(np.mean(ddv > 1e-8)) if len(ddv) > 0 else 0.0
                    gradient_diagnosis = enforce_gradient_ontology(alive_frac, dynamic_frac)

        state = NeosynaptexState(
            t=self._tick,
            phi=phi.copy(),
            phi_per_domain={k: v.copy() for k, v in phi_per_domain.items()},
            gamma_per_domain=dict(gamma_per_domain),
            gamma_ci_per_domain=dict(gamma_ci_per_domain),
            gamma_mean=gamma_mean,
            gamma_std=gamma_std,
            cross_coherence=cross_coherence,
            dgamma_dt=dgamma_dt,
            gamma_ema_per_domain=dict(gamma_ema_per_domain),
            universal_scaling_p=universal_scaling_p,
            sr_per_domain=dict(sr_per_domain),
            cond_per_domain=dict(cond_per_domain),
            spectral_radius=spectral_radius,
            phase=phase,
            anomaly_score=dict(anomaly_score),
            granger_graph=dict(granger_graph),
            portrait=dict(portrait),
            resilience_score=resilience_score,
            modulation=dict(modulation),
            diagnostic=dict(diagnostic),
            cross_jacobian=cross_jacobian
            if any(np.isfinite(v) for row in cross_jacobian.values() for v in row.values())
            else None,
            cross_jacobian_cond=cross_jacobian_cond,
            adaptive_window=self._adaptive_window,
            ci_width_mean=ci_width_mean,
            value_estimate=value_estimate,
            gradient_diagnosis=gradient_diagnosis,
        )

        self._history.append(state)
        max_hist = 3 * self._window
        if len(self._history) > max_hist:
            self._history = self._history[-max_hist:]

        return state

    def _raw_phase(self, sr: float, dgamma_dt: float, gamma_mean: float) -> str:
        """Determine raw phase before hysteresis.

        Phase logic:
            NaN sr                      -> INITIALIZING
            sr > 1.5 sustained (3+)     -> DEGENERATE
            sr > 1.25                   -> DIVERGING
            sr < 0.80                   -> COLLAPSING
            |gamma-1| < 0.15 and dg->0  -> METASTABLE
            dg < -0.005 toward 1.0      -> CONVERGING
            dg > 0.005 away from 1.0    -> DRIFTING
            else                        -> METASTABLE
        """
        if not np.isfinite(sr):
            self._degenerate_count = 0
            return INITIALIZING

        if sr > _SR_DEGENERATE:
            self._degenerate_count += 1
            if self._degenerate_count >= _DEGENERATE_COUNT:
                return DEGENERATE
            return DIVERGING
        self._degenerate_count = 0

        if sr > _SR_METASTABLE_HI:
            return DIVERGING
        if sr < _SR_METASTABLE_LO:
            return COLLAPSING

        # SR is in metastable band -- check gamma dynamics
        if np.isfinite(dgamma_dt) and np.isfinite(gamma_mean):
            dist_from_one = gamma_mean - 1.0
            moving_toward = (dist_from_one > 0 and dgamma_dt < -0.003) or (
                dist_from_one < 0 and dgamma_dt > 0.003
            )
            moving_away = (dist_from_one > 0 and dgamma_dt > 0.005) or (
                dist_from_one < 0 and dgamma_dt < -0.005
            )

            if moving_toward and abs(dist_from_one) > 0.05:
                return CONVERGING
            if moving_away and abs(dist_from_one) > 0.05:
                return DRIFTING

        return METASTABLE

    def need_vector(self) -> None:
        """Placeholder for v2. Returns None."""
        return

    def history(self) -> list[NeosynaptexState]:
        """Return list of past snapshots (oldest first)."""
        return list(self._history)

    def reset(self) -> None:
        """Clear all state history."""
        for buf in self._buffers.values():
            buf.clear()
        self._history.clear()
        self._gamma_history = {k: [] for k in self._gamma_history}
        self._gamma_trace.clear()
        self._sr_trace.clear()
        self._gamma_ema = {k: float("nan") for k in self._gamma_ema}
        self._gamma_bootstraps = {k: np.array([]) for k in self._gamma_bootstraps}
        self._tick = 0
        self._degenerate_count = 0
        self._confirmed_phase = INITIALIZING
        self._candidate_phase = INITIALIZING
        self._candidate_count = 0
        self._departures = 0
        self._returns = 0
        self._was_metastable = False
        self._f_history.clear()
        self._gamma_per_domain_trace.clear()
        self._state_mean_trace.clear()
        self._adaptive_window = self._window
        self._last_proof_hash = None
        self._proof_count = 0

    def truth_function(self) -> dict[str, Any]:
        """Unified truth function -- answers: is gamma REAL or ARTIFACT?

        Runs 5 independent verification axes per domain:
          1. Tautology detection (R2 too perfect?)
          2. Estimator consensus (Theil-Sen vs OLS vs Huber)
          3. Surrogate significance (IAAFT null hypothesis)
          4. DFA cross-validation (Hurst exponent agreement)
          5. RQA regime fingerprint (deterministic structure?)

        Returns dict with per-domain TruthAssessment and global verdict.
        Call periodically (not every tick) -- runs surrogate tests.

        The global verdict is computed via ``contracts.fail_closed.aggregate_verdicts``:
        every registered domain must contribute an explicit status (NaN
        gamma -> ``MISSING``), and ``all([])`` can never upgrade to
        VERIFIED. See ``contracts/fail_closed.py`` for the exact law.
        """
        from contracts.fail_closed import Verdict, aggregate_verdicts, parse_verdict
        from core.truth_function import assess_truth

        if not self._history:
            return {"error": "no observations", "global_verdict": Verdict.INCONCLUSIVE.value}

        domain_order = sorted(self._adapters.keys())
        assessments: dict[str, dict[str, Any]] = {}
        per_domain_status: dict[str, Verdict] = {}

        for name in domain_order:
            buf = self._buffers[name]
            topos = buf.topos()
            costs = buf.costs()
            gamma = self._history[-1].gamma_per_domain.get(name, float("nan"))
            gamma_hist = self._gamma_history.get(name, [])

            if not np.isfinite(gamma):
                # A NaN gamma is a registered-but-unverifiable domain; it
                # must contribute MISSING to the aggregator, never be
                # silently skipped (the old behaviour let ``all([])``
                # upgrade an empty verdict set to VERIFIED).
                assessments[name] = {
                    "verdict": Verdict.MISSING.value,
                    "reason": "gamma is NaN",
                }
                per_domain_status[name] = Verdict.MISSING
                continue

            a = assess_truth(
                topos,
                costs,
                gamma,
                gamma_trace=gamma_hist,
                sr_trace=list(self._sr_trace),
                n_surrogates=99,
                seed=self._tick,
            )
            assessments[name] = {
                "verdict": a.verdict,
                "confidence": round(a.confidence, 3),
                "axes_passed": a.n_axes_passed,
                "tautology_risk": round(a.tautology_risk, 3),
                "estimator_spread": round(a.estimator_spread, 4)
                if np.isfinite(a.estimator_spread)
                else None,
                "estimators_agree": a.estimators_agree,
                "surrogate_p": round(a.surrogate_p, 4) if np.isfinite(a.surrogate_p) else None,
                "survives_null": a.survives_null,
                "hurst_H": round(a.hurst_exponent, 4) if np.isfinite(a.hurst_exponent) else None,
                "gamma_dfa": round(a.gamma_dfa, 4) if np.isfinite(a.gamma_dfa) else None,
                "dfa_consistent": a.dfa_consistent,
                "rqa_DET": round(a.rqa_det, 4) if np.isfinite(a.rqa_det) else None,
                "has_structure": a.has_structure,
            }
            per_domain_status[name] = parse_verdict(a.verdict)

        global_verdict = aggregate_verdicts(domain_order, per_domain_status)

        n_verified = sum(1 for v in per_domain_status.values() if v == Verdict.VERIFIED)
        return {
            "global_verdict": global_verdict.value,
            "per_domain": assessments,
            "n_domains_verified": n_verified,
            "n_domains_total": len(domain_order),
        }

    def export_proof(self, path: str | None = None) -> dict[str, Any]:
        """Export proof bundle as JSON-serializable dict.

        Contains all evidence: gamma values, CIs, R^2, spectral radii,
        condition numbers, Granger graph, anomaly scores, phase portrait,
        resilience, and verdict.
        """
        if not self._history:
            return {"error": "no observations"}
        s = self._history[-1]
        proof = {
            "version": __version__,
            "ticks": s.t,
            "gamma": {
                "per_domain": {
                    k: {
                        "value": round(v, 4) if np.isfinite(v) else None,
                        "ci": [
                            round(c, 4) if np.isfinite(c) else None
                            for c in s.gamma_ci_per_domain[k]
                        ],
                        "r2": round(s.diagnostic["r2_per_domain"][k], 4)
                        if np.isfinite(s.diagnostic["r2_per_domain"].get(k, float("nan")))
                        else None,
                        "ema": round(s.gamma_ema_per_domain.get(k, float("nan")), 4)
                        if np.isfinite(s.gamma_ema_per_domain.get(k, float("nan")))
                        else None,
                    }
                    for k, v in s.gamma_per_domain.items()
                },
                "mean": round(s.gamma_mean, 4) if np.isfinite(s.gamma_mean) else None,
                "std": round(s.gamma_std, 4) if np.isfinite(s.gamma_std) else None,
                "dgamma_dt": round(s.dgamma_dt, 6) if np.isfinite(s.dgamma_dt) else None,
                "universal_scaling_p": round(s.universal_scaling_p, 4)
                if np.isfinite(s.universal_scaling_p)
                else None,
            },
            "jacobian": {
                k: {
                    "sr": round(sr, 4) if np.isfinite(sr) else None,
                    "cond": round(s.cond_per_domain.get(k, float("nan")), 2)
                    if np.isfinite(s.cond_per_domain.get(k, float("nan")))
                    else None,
                }
                for k, sr in s.sr_per_domain.items()
            },
            "phase": s.phase,
            "anomaly": {k: v if np.isfinite(v) else None for k, v in s.anomaly_score.items()},
            "granger": {
                src: {tgt: v if np.isfinite(v) else None for tgt, v in targets.items()}
                for src, targets in s.granger_graph.items()
            },
            "portrait": {k: v if np.isfinite(v) else None for k, v in s.portrait.items()},
            "resilience": round(s.resilience_score, 4) if np.isfinite(s.resilience_score) else None,
            "modulation": {k: v for k, v in s.modulation.items()},
            "coherence": round(s.cross_coherence, 4) if np.isfinite(s.cross_coherence) else None,
            "verdict": "COHERENT"
            if (
                np.isfinite(s.cross_coherence)
                and s.cross_coherence > 0.85
                and s.phase in (METASTABLE, CONVERGING)
            )
            else "INCOHERENT"
            if s.phase in (DEGENERATE, DIVERGING)
            else "PARTIAL",
            "coupling_tensor": {
                "cross_jacobian": {
                    src: {tgt: v if np.isfinite(v) else None for tgt, v in targets.items()}
                    for src, targets in (s.cross_jacobian or {}).items()
                },
                "condition_number": round(s.cross_jacobian_cond, 2)
                if np.isfinite(s.cross_jacobian_cond)
                else None,
                "n_ticks_used": len(self._gamma_per_domain_trace),
                "window_adaptive": s.adaptive_window,
                "ci_width_mean": round(s.ci_width_mean, 4)
                if np.isfinite(s.ci_width_mean)
                else None,
            },
        }

        # Per-domain provenance (REPLICATION_GATE_v1.0 Phase 4 requirement).
        # Every exported bundle must carry ``provenance_class`` and
        # ``claim_status`` for every registered adapter, so downstream
        # consumers can reject inadmissible substrates without having to
        # import the original adapter. Adapters without a ``provenance``
        # attribute emit the explicit ``"unknown"`` sentinel -- never a
        # silent skip.
        per_domain_provenance: dict[str, dict[str, str]] = {}
        for name, adapter in self._adapters.items():
            prov = getattr(adapter, "provenance", None)
            if prov is None:
                per_domain_provenance[name] = {
                    "provenance_class": "unknown",
                    "claim_status": "unknown",
                }
                continue
            cls = getattr(prov.provenance_class, "value", str(prov.provenance_class))
            cst = getattr(prov.claim_status, "value", str(prov.claim_status))
            per_domain_provenance[name] = {
                "provenance_class": cls,
                "claim_status": cst,
            }
        proof["per_domain"] = per_domain_provenance

        # Proof chain (T4)
        self._proof_count += 1
        chain: dict[str, Any] = {
            "t": self._proof_count,
            "prev_hash": self._last_proof_hash or "GENESIS",
            "chain_root": self._chain_root,
            "self_hash": "PENDING",
        }
        proof["chain"] = chain
        self_hash = self._compute_proof_hash(proof)
        chain["self_hash"] = self_hash
        self._last_proof_hash = self_hash

        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(proof, f, indent=2, ensure_ascii=False)
        return proof


# ---------------------------------------------------------------------------
# Mock Adapters
# ---------------------------------------------------------------------------
class MockBnSynAdapter:
    """Mock BN-Syn: oscillating near criticality with gamma ~ 0.95.

    topo = 1.0 + 8.0 * |sin(0.2t)|
    cost = 8.0 * topo^(-0.95) + noise   (gamma=0.95 by construction)
    """

    #: Provenance — MOCK/DOWNGRADED: for smoke tests only, rejected in REAL modes.
    provenance = _Provenance(
        provenance_class=_ProvenanceClass.MOCK,
        claim_status=_ClaimStatus.DOWNGRADED,
        corpus_ref="neosynaptex.MockBnSynAdapter (analytic oscillator with noise)",
        notes="Deterministic gamma~0.95 fixture for CI smoke tests.",
    )

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        self._t = 0

    @property
    def domain(self) -> str:
        return "spike"

    @property
    def state_keys(self) -> list[str]:
        return ["sigma", "firing_rate", "coherence"]

    def state(self) -> dict[str, float]:
        self._t += 1
        t = self._t
        return {
            "sigma": 1.0 + 0.15 * math.sin(0.1 * t) + self._rng.normal(0, 0.02),
            "firing_rate": 20.0 + 5.0 * math.sin(0.08 * t) + self._rng.normal(0, 0.5),
            "coherence": 0.7 + 0.1 * math.cos(0.12 * t) + self._rng.normal(0, 0.02),
        }

    def topo(self) -> float:
        self._topo = max(_TOPO_FLOOR, 1.0 + 8.0 * abs(math.sin(0.2 * self._t)))
        return self._topo

    def thermo_cost(self) -> float:
        t = getattr(self, "_topo", 5.0)
        return float(max(_TOPO_FLOOR, 8.0 * t ** (-0.95) + self._rng.normal(0, 0.03)))


class MockMfnAdapter:
    """Mock MFN+: morphogenesis with gamma ~ 1.0.

    topo_base = 1.0 + 10.0 * |sin(0.2t)|
    cost = 10.0 * topo^(-1.0) + noise   (gamma=1.0 by construction)
    """

    #: Provenance — MOCK/DOWNGRADED: for smoke tests only, rejected in REAL modes.
    provenance = _Provenance(
        provenance_class=_ProvenanceClass.MOCK,
        claim_status=_ClaimStatus.DOWNGRADED,
        corpus_ref="neosynaptex.MockMfnAdapter (analytic oscillator with noise)",
        notes="Deterministic gamma~1.0 fixture for CI smoke tests.",
    )

    def __init__(self, seed: int = 43) -> None:
        self._rng = np.random.default_rng(seed)
        self._t = 0

    @property
    def domain(self) -> str:
        return "morpho"

    @property
    def state_keys(self) -> list[str]:
        return ["d_box", "beta0", "beta1", "delta_h"]

    def state(self) -> dict[str, float]:
        self._t += 1
        t = self._t
        tb = max(0.5, 1.0 + 10.0 * abs(math.sin(0.2 * t)))
        self._topo_base = tb
        self._delta_h = max(_TOPO_FLOOR, 10.0 * tb ** (-1.0) + self._rng.normal(0, 0.05))
        return {
            "d_box": 1.7 + 0.1 * math.sin(0.04 * t),
            "beta0": tb * 0.6,
            "beta1": tb * 0.4,
            "delta_h": self._delta_h,
        }

    def topo(self) -> float:
        return float(max(_TOPO_FLOOR, self._topo_base))

    def thermo_cost(self) -> float:
        return float(self._delta_h)


class MockPsycheCoreAdapter:
    """Mock PsycheCore: free energy minimization with gamma ~ 1.05.

    topo = 5.0 + 45.0 * |sin(0.2t)|
    cost = 20.0 * topo^(-1.05) + noise
    """

    #: Provenance — MOCK/DOWNGRADED: for smoke tests only, rejected in REAL modes.
    provenance = _Provenance(
        provenance_class=_ProvenanceClass.MOCK,
        claim_status=_ClaimStatus.DOWNGRADED,
        corpus_ref="neosynaptex.MockPsycheCoreAdapter (analytic oscillator with noise)",
        notes="Deterministic gamma~1.05 fixture for CI smoke tests.",
    )

    def __init__(self, seed: int = 44) -> None:
        self._rng = np.random.default_rng(seed)
        self._t = 0

    @property
    def domain(self) -> str:
        return "psyche"

    @property
    def state_keys(self) -> list[str]:
        return ["free_energy", "kuramoto_r"]

    def state(self) -> dict[str, float]:
        self._t += 1
        t = self._t
        return {
            "free_energy": max(0.1, 5.0 * math.exp(-0.02 * t) + self._rng.normal(0, 0.1)),
            "kuramoto_r": 0.8 + 0.1 * math.sin(0.07 * t) + self._rng.normal(0, 0.02),
        }

    def topo(self) -> float:
        self._topo = max(_TOPO_FLOOR, 5.0 + 45.0 * abs(math.sin(0.2 * self._t)))
        return self._topo

    def thermo_cost(self) -> float:
        t = getattr(self, "_topo", 25.0)
        return float(max(_TOPO_FLOOR, 20.0 * t ** (-1.05) + self._rng.normal(0, 0.02)))


class MockMarketAdapter:
    """Mock mvstack/GeoSync: regime dynamics with gamma ~ 1.08.

    topo = 1.0 + 7.0 * |sin(0.2t)|
    cost = 5.0 * topo^(-1.08) + noise
    """

    #: Provenance — MOCK/DOWNGRADED: for smoke tests only, rejected in REAL modes.
    provenance = _Provenance(
        provenance_class=_ProvenanceClass.MOCK,
        claim_status=_ClaimStatus.DOWNGRADED,
        corpus_ref="neosynaptex.MockMarketAdapter (analytic oscillator with noise)",
        notes="Deterministic gamma~1.08 fixture for CI smoke tests.",
    )

    def __init__(self, seed: int = 45) -> None:
        self._rng = np.random.default_rng(seed)
        self._t = 0

    @property
    def domain(self) -> str:
        return "market"

    @property
    def state_keys(self) -> list[str]:
        return ["regime", "w1_distance", "ricci_curvature"]

    def state(self) -> dict[str, float]:
        self._t += 1
        t = self._t
        return {
            "regime": 1.0 if math.sin(0.06 * t) > 0 else 0.0,
            "w1_distance": 0.5 + 0.3 * abs(math.sin(0.09 * t)) + self._rng.normal(0, 0.02),
            "ricci_curvature": -0.2 + 0.4 * math.sin(0.05 * t) + self._rng.normal(0, 0.03),
        }

    def topo(self) -> float:
        self._topo = max(_TOPO_FLOOR, 1.0 + 7.0 * abs(math.sin(0.2 * self._t)))
        return self._topo

    def thermo_cost(self) -> float:
        t = getattr(self, "_topo", 4.0)
        return float(max(_TOPO_FLOOR, 5.0 * t ** (-1.08) + self._rng.normal(0, 0.02)))
