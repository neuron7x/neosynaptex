"""Mathematical precision toolkit — advanced analytical instruments.

Provides rigorous mathematical tools that push the analytical
capability of NFI beyond standard statistics:

1. Rényi entropy spectrum H_α(X) — generalized entropy parameterized
   by order α, giving a full entropic profile rather than a single number.
2. Maximum Lyapunov exponent λ_max — quantifies divergence rate of
   nearby trajectories in the coherence state-space.
3. Fisher information I_F(γ) — measures the information that the
   γ-trajectory carries about the true regime parameter.
4. Cramér-Rao lower bound for FDT γ-estimator — theoretical minimum
   variance achievable by any unbiased estimator.

All implementations are:
- Numerically stable (log-domain where possible)
- Deterministic given seed
- Pure numpy (no external dependencies beyond scipy for special functions)
- INV-1 compliant (γ is data, never stored state)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "CramerRaoBound",
    "FisherInformationResult",
    "LyapunovResult",
    "RenyiSpectrum",
    "cramer_rao_fdt",
    "fisher_information_gamma",
    "lyapunov_exponent",
    "renyi_entropy",
    "renyi_spectrum",
]

FloatArray = NDArray[np.float64]

_EPS: Final[float] = 1e-15


# ═══════════════════════════════════════════════════════════════════════
#  1. RÉNYI ENTROPY SPECTRUM
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RenyiSpectrum:
    """Rényi entropy spectrum across multiple orders α."""

    alphas: FloatArray
    entropies: FloatArray
    shannon_entropy: float  # α → 1 limit
    min_entropy: float  # α → ∞ limit
    max_entropy: float  # α → 0 limit (log of support size)


def renyi_entropy(
    x: FloatArray,
    alpha: float,
    n_bins: int = 64,
) -> float:
    r"""Compute Rényi entropy of order α for a 1-D signal.

    .. math::

        H_\alpha(X) = \frac{1}{1 - \alpha} \log \sum_i p_i^\alpha

    Special cases:
    - α → 0: H_0 = log(|support|)  (Hartley entropy)
    - α → 1: H_1 = -Σ p_i log p_i  (Shannon entropy)
    - α → ∞: H_∞ = -log(max p_i)   (min-entropy)

    Parameters
    ----------
    x : array
        1-D signal.
    alpha : float
        Rényi order. Must be >= 0.
    n_bins : int
        Histogram bins for density estimation.

    Returns
    -------
    float
        H_α in nats.
    """
    if alpha < 0:
        raise ValueError(f"alpha must be >= 0, got {alpha}")

    hist, _ = np.histogram(x, bins=n_bins, density=False)
    p = hist.astype(np.float64)
    p = p[p > 0]  # remove zero bins
    p = p / p.sum()

    if abs(alpha - 1.0) < 1e-10:
        # Shannon limit
        return float(-np.sum(p * np.log(p + _EPS)))

    if alpha == 0.0:
        # Hartley: log of number of non-zero bins
        return float(np.log(len(p)))

    if alpha > 50.0:
        # Min-entropy approximation
        return float(-np.log(np.max(p) + _EPS))

    # General case
    return float(np.log(np.sum(p**alpha) + _EPS) / (1.0 - alpha))


def renyi_spectrum(
    x: FloatArray,
    alphas: FloatArray | None = None,
    n_bins: int = 64,
) -> RenyiSpectrum:
    """Compute the full Rényi entropy spectrum.

    Parameters
    ----------
    x : array
        1-D signal.
    alphas : array or None
        Orders to evaluate. Default: [0, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10, 50].
    n_bins : int
        Histogram bins.

    Returns
    -------
    RenyiSpectrum
        Full spectrum with Shannon, min, and max entropy.
    """
    if alphas is None:
        alphas = np.array([0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 50.0])
    else:
        alphas = np.asarray(alphas, dtype=np.float64)

    entropies = np.array([renyi_entropy(x, float(a), n_bins) for a in alphas])

    return RenyiSpectrum(
        alphas=alphas,
        entropies=entropies,
        shannon_entropy=renyi_entropy(x, 1.0, n_bins),
        min_entropy=renyi_entropy(x, 100.0, n_bins),
        max_entropy=renyi_entropy(x, 0.0, n_bins),
    )


# ═══════════════════════════════════════════════════════════════════════
#  2. MAXIMUM LYAPUNOV EXPONENT
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LyapunovResult:
    """Maximum Lyapunov exponent estimation result."""

    lambda_max: float  # max Lyapunov exponent
    convergence_curve: FloatArray  # log(divergence) vs time
    is_chaotic: bool  # λ_max > 0
    is_stable: bool  # λ_max < 0
    e_folding_time: float  # 1/|λ_max| — time to double/halve perturbation


def lyapunov_exponent(
    trajectory: FloatArray,
    dt: float = 1.0,
    n_neighbors: int = 5,
    max_steps: int = 50,
) -> LyapunovResult:
    r"""Estimate the maximum Lyapunov exponent from a state trajectory.

    Uses the Rosenstein (1993) algorithm:
    1. For each point, find nearest neighbor in state space (excluding
       temporal neighbors within ±n_neighbors).
    2. Track divergence of the nearest-neighbor pair over time.
    3. λ_max = slope of log(divergence) vs time.

    .. math::

        \lambda_{\max} = \lim_{t \to \infty} \frac{1}{t}
        \ln \frac{\|x(t) - x^*(t)\|}{\|x(0) - x^*(0)\|}

    Parameters
    ----------
    trajectory : array
        (T, D) state trajectory.
    dt : float
        Timestep.
    n_neighbors : int
        Temporal exclusion zone for nearest-neighbor search.
    max_steps : int
        Maximum tracking steps for divergence.

    Returns
    -------
    LyapunovResult
    """
    traj = np.asarray(trajectory, dtype=np.float64)
    if traj.ndim == 1:
        traj = traj[:, np.newaxis]
    n_points, n_dim = traj.shape

    if n_points < 2 * max_steps:
        raise ValueError(f"trajectory too short: {n_points} < {2 * max_steps}")

    usable = n_points - max_steps

    # For each point, find nearest neighbor outside exclusion zone
    nn_indices = np.zeros(usable, dtype=np.int64)
    nn_dists = np.full(usable, np.inf)

    for i in range(usable):
        for j in range(usable):
            if abs(i - j) <= n_neighbors:
                continue
            d = float(np.linalg.norm(traj[i] - traj[j]))
            if d < nn_dists[i] and d > _EPS:
                nn_dists[i] = d
                nn_indices[i] = j

    # Track divergence over time
    log_div = np.zeros(max_steps, dtype=np.float64)
    counts = np.zeros(max_steps, dtype=np.int64)

    for i in range(usable):
        j = int(nn_indices[i])
        if nn_dists[i] >= 1e10:
            continue
        for k in range(max_steps):
            if i + k >= n_points or j + k >= n_points:
                break
            d = float(np.linalg.norm(traj[i + k] - traj[j + k]))
            if d > _EPS:
                log_div[k] += np.log(d)
                counts[k] += 1

    # Average log divergence
    valid = counts > 0
    if valid.sum() < 3:
        return LyapunovResult(
            lambda_max=0.0,
            convergence_curve=np.zeros(1),
            is_chaotic=False,
            is_stable=False,
            e_folding_time=float("inf"),
        )

    log_div_mean = np.where(valid, log_div / np.maximum(counts, 1), np.nan)

    # Fit slope via OLS on valid portion
    t_axis = np.arange(max_steps, dtype=np.float64) * dt
    valid_idx = np.where(valid)[0]
    if len(valid_idx) < 3:
        lam = 0.0
    else:
        t_fit = t_axis[valid_idx]
        y_fit = log_div_mean[valid_idx]
        # Remove NaN
        finite = np.isfinite(y_fit)
        t_fit = t_fit[finite]
        y_fit = y_fit[finite]
        if len(t_fit) >= 3:
            coeffs = np.polyfit(t_fit, y_fit, 1)
            lam = float(coeffs[0])
        else:
            lam = 0.0

    return LyapunovResult(
        lambda_max=lam,
        convergence_curve=log_div_mean,
        is_chaotic=lam > 0.01,
        is_stable=lam < -0.01,
        e_folding_time=1.0 / abs(lam) if abs(lam) > _EPS else float("inf"),
    )


# ═══════════════════════════════════════════════════════════════════════
#  3. FISHER INFORMATION ON γ-TRAJECTORY
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FisherInformationResult:
    """Fisher information about the regime parameter from γ observations."""

    fisher_info: float  # I_F(θ) = E[(d/dθ log p(x|θ))²]
    effective_samples: float  # n_eff = n * I_F / I_F_iid
    estimation_precision: float  # 1/sqrt(I_F) — std of optimal estimator


def fisher_information_gamma(
    gamma_trajectory: FloatArray,
    theta_true: float = 1.0,
    bandwidth: float = 0.1,
) -> FisherInformationResult:
    r"""Estimate Fisher information of the γ-trajectory about θ_true.

    Uses the score function approach with kernel density estimation:

    .. math::

        I_F(\theta) = \int \left(\frac{\partial}{\partial \theta}
        \log f(x|\theta)\right)^2 f(x|\theta) \, dx

    For a Gaussian model around θ_true with observed variance σ²:

    .. math::

        I_F = \frac{1}{\sigma^2}

    This gives the information-theoretic bound on how precisely θ
    can be estimated from the observations.

    Parameters
    ----------
    gamma_trajectory : array
        1-D array of observed γ values.
    theta_true : float
        True regime parameter (default: 1.0 for criticality).
    bandwidth : float
        KDE bandwidth for score estimation.

    Returns
    -------
    FisherInformationResult
    """
    g = np.asarray(gamma_trajectory, dtype=np.float64)
    n = len(g)
    if n < 2:
        raise ValueError("need at least 2 observations")

    # Observed variance around theta_true
    residuals = g - theta_true
    sigma2 = float(np.var(residuals, ddof=1))

    if sigma2 < _EPS:
        # Perfect observations → infinite Fisher info (in theory)
        return FisherInformationResult(
            fisher_info=1.0 / _EPS,
            effective_samples=float(n),
            estimation_precision=0.0,
        )

    # Gaussian Fisher information: I_F = 1/σ²
    # This is the Cramér-Rao bound for location estimation
    fisher = 1.0 / sigma2

    # Effective samples: how many iid samples would give the same info
    # For correlated data, n_eff < n
    # Estimate autocorrelation time
    g_centered = g - np.mean(g)
    acf = np.correlate(g_centered, g_centered, mode="full")[n - 1 :]
    acf = acf / (acf[0] + _EPS)

    # Integrated autocorrelation time τ_int = 1 + 2*Σ_{k=1}^{K} ρ(k)
    # Truncate at first non-positive lag
    tau_int = 1.0
    for k in range(1, min(n // 2, 200)):
        if acf[k] <= 0:
            break
        tau_int += 2.0 * float(acf[k])

    n_eff = n / max(tau_int, 1.0)

    precision = 1.0 / np.sqrt(max(n_eff * fisher, _EPS))

    return FisherInformationResult(
        fisher_info=fisher,
        effective_samples=n_eff,
        estimation_precision=float(precision),
    )


# ═══════════════════════════════════════════════════════════════════════
#  4. CRAMÉR-RAO BOUND FOR FDT γ-ESTIMATOR
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CramerRaoBound:
    """Cramér-Rao lower bound for the FDT γ-estimator."""

    gamma_true: float
    crlb_variance: float  # theoretical minimum variance
    crlb_std: float  # sqrt(CRLB)
    achieved_variance: float  # actual estimator variance
    efficiency: float  # CRLB / achieved_variance (1.0 = perfect)


def cramer_rao_fdt(
    gamma_true: float,
    n_steps: int,
    dt: float,
    temperature: float = 1.0,
    n_monte_carlo: int = 100,
    seed: int = 42,
) -> CramerRaoBound:
    r"""Compute Cramér-Rao lower bound for the FDT γ-estimator.

    For an Ornstein-Uhlenbeck process dx = -γx dt + √(2γT) dW,
    the Fisher information about γ from a trajectory of length n*dt is:

    .. math::

        I_F(\gamma) = \frac{n \cdot dt}{2\gamma^2}
        \left(1 + \frac{1 - e^{-2\gamma dt}}{2\gamma dt}\right)

    For the common case γ*dt << 1 (well-sampled):

    .. math::

        I_F(\gamma) \approx \frac{n \cdot dt}{\gamma^2}

    The CRLB is then:

    .. math::

        \text{Var}(\hat{\gamma}) \geq \frac{1}{I_F(\gamma)}
        = \frac{\gamma^2}{n \cdot dt}

    Parameters
    ----------
    gamma_true : float
        True relaxation rate.
    n_steps : int
        Number of observation steps.
    dt : float
        Timestep.
    temperature : float
        Equilibrium temperature T.
    n_monte_carlo : int
        Number of MC runs to estimate achieved variance.
    seed : int
        Random seed.

    Returns
    -------
    CramerRaoBound
    """
    if gamma_true <= 0 or n_steps < 10 or dt <= 0:
        raise ValueError("invalid parameters")

    from core.gamma_fdt_estimator import GammaFDTEstimator, simulate_ou_pair

    # Theoretical CRLB
    total_time = n_steps * dt
    # Full Fisher information for OU
    gdt = gamma_true * dt
    if gdt < 0.01:
        fisher = total_time / (gamma_true**2)
    else:
        fisher = (total_time / (2.0 * gamma_true**2)) * (
            1.0 + (1.0 - np.exp(-2.0 * gdt)) / (2.0 * gdt)
        )

    crlb_var = 1.0 / fisher
    crlb_std = float(np.sqrt(crlb_var))

    # Monte Carlo: estimate actual variance of FDT estimator
    estimates: list[float] = []
    est = GammaFDTEstimator(dt=dt, bootstrap_n=0, seed=seed)
    for i in range(n_monte_carlo):
        noise, response = simulate_ou_pair(
            gamma_true=gamma_true,
            T=temperature,
            n_steps=n_steps,
            dt=dt,
            perturbation=0.1,
            seed=seed + i,
        )
        try:
            result = est.estimate(noise, response, 0.1)
            if np.isfinite(result.gamma_hat):
                estimates.append(result.gamma_hat)
        except ValueError:
            continue

    achieved_var = float("inf") if len(estimates) < 5 else float(np.var(estimates, ddof=1))

    efficiency = crlb_var / max(achieved_var, _EPS) if achieved_var > _EPS else 0.0

    return CramerRaoBound(
        gamma_true=gamma_true,
        crlb_variance=float(crlb_var),
        crlb_std=crlb_std,
        achieved_variance=achieved_var,
        efficiency=min(float(efficiency), 1.0),
    )
