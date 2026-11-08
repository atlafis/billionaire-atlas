"""Small, dependency-light statistics used by the analysis.

Everything here is a pure function of numpy arrays, so it is unit-tested on
synthetic data with known answers (see ``tests/test_stats.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def gini(x: np.ndarray) -> float:
    """Gini coefficient of a non-negative sample (0 = equal, 1 = one holds all)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    if n == 0 or x.sum() == 0:
        return float("nan")
    ranks = np.arange(1, n + 1)
    return float((2 * (ranks * x).sum()) / (n * x.sum()) - (n + 1) / n)


def top_share(x: np.ndarray, k: int) -> float:
    """Share of the total held by the k largest values."""
    x = np.sort(np.asarray(x, dtype=float))[::-1]
    return float(x[:k].sum() / x.sum())


# --------------------------------------------------------------------------- Pareto

@dataclass(frozen=True)
class ParetoFit:
    alpha: float        # density exponent: p(x) ~ x^-alpha
    xmin: float         # power-law behaviour starts here
    n_tail: int         # observations at or above xmin
    ks: float           # Kolmogorov-Smirnov distance of the fit
    ci_low: float = float("nan")
    ci_high: float = float("nan")

    @property
    def tail_index(self) -> float:
        """Exponent of the survival function, P(X > x) ~ x^-(alpha-1)."""
        return self.alpha - 1


def _alpha_mle(tail: np.ndarray, xmin: float) -> float:
    return 1 + tail.size / np.log(tail / xmin).sum()


def _ks(tail: np.ndarray, xmin: float, alpha: float) -> float:
    tail = np.sort(tail)
    n = tail.size
    model = 1 - (tail / xmin) ** (1 - alpha)
    emp_hi = np.arange(1, n + 1) / n
    emp_lo = np.arange(0, n) / n
    return float(max(np.abs(emp_hi - model).max(), np.abs(emp_lo - model).max()))


def fit_pareto(x: np.ndarray, min_tail: int = 50, n_candidates: int = 300,
               bootstrap: int = 0, seed: int = 0) -> ParetoFit:
    """Continuous power-law fit with xmin chosen by minimum KS distance.

    This is the method of Clauset, Shalizi & Newman (2009, SIAM Review): for
    each candidate xmin, estimate alpha by maximum likelihood on the tail and
    keep the xmin whose fitted tail is closest to the data. With ``bootstrap``
    > 0 a percentile confidence interval for alpha is added; each replicate
    re-runs the whole procedure, including the choice of xmin.
    """
    x = np.asarray(x, dtype=float)
    x = x[x > 0]
    uniq = np.unique(x)
    cands = uniq[: max(1, uniq.size - min_tail)]
    if cands.size > n_candidates:
        cands = cands[np.linspace(0, cands.size - 1, n_candidates).astype(int)]
    best = None
    for xmin in cands:
        tail = x[x >= xmin]
        if tail.size < min_tail:
            break
        a = _alpha_mle(tail, xmin)
        d = _ks(tail, xmin, a)
        if best is None or d < best.ks:
            best = ParetoFit(alpha=a, xmin=float(xmin), n_tail=int(tail.size), ks=d)
    if best is None:
        raise ValueError("not enough data for a tail fit")
    if bootstrap:
        rng = np.random.default_rng(seed)
        alphas = [fit_pareto(rng.choice(x, x.size), min_tail, n_candidates // 3).alpha
                  for _ in range(bootstrap)]
        lo, hi = np.percentile(alphas, [2.5, 97.5])
        best = ParetoFit(best.alpha, best.xmin, best.n_tail, best.ks, float(lo), float(hi))
    return best


def ccdf(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Empirical P(X >= x) at each sorted value."""
    x = np.sort(np.asarray(x, dtype=float))
    return x, 1 - np.arange(x.size) / x.size


# -------------------------------------------------------------------------- Gibrat

@dataclass(frozen=True)
class Regression:
    slope: float
    se: float
    n: int

    @property
    def t(self) -> float:
        return self.slope / self.se


def demeaned_ols(x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> Regression:
    """Slope of y on x with group fixed effects and HC1 robust standard error.

    Used to test Gibrat's law: if fortunes grow at rates independent of their
    size, the slope of log-growth on log-wealth is zero. Year fixed effects
    remove market-wide swings (2022 hit everyone).
    """
    x, y, g = np.asarray(x, float), np.asarray(y, float), np.asarray(groups)
    xd, yd = x.copy(), y.copy()
    for k in np.unique(g):
        m = g == k
        xd[m] -= x[m].mean()
        yd[m] -= y[m].mean()
    n, k_fe = x.size, np.unique(g).size
    beta = (xd @ yd) / (xd @ xd)
    resid = yd - beta * xd
    dof = n - k_fe - 1
    var = (n / dof) * ((xd ** 2) @ (resid ** 2)) / (xd @ xd) ** 2
    return Regression(slope=float(beta), se=float(np.sqrt(var)), n=int(n))


def binned_means(x: np.ndarray, y: np.ndarray, bins: int = 10) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean of y within quantile bins of x, with a 95% normal interval."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    edges = np.quantile(x, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, bins - 1)
    mx = np.array([x[idx == b].mean() for b in range(bins)])
    my = np.array([y[idx == b].mean() for b in range(bins)])
    half = np.array([1.96 * y[idx == b].std(ddof=1) / np.sqrt((idx == b).sum()) for b in range(bins)])
    return mx, my, half
