import numpy as np
import pytest

from billionaires import stats


def test_gini_bounds():
    assert stats.gini(np.ones(100)) == pytest.approx(0, abs=1e-12)
    x = np.zeros(1000)
    x[-1] = 1
    assert stats.gini(x) == pytest.approx(1, abs=1e-2)


def test_top_share():
    assert stats.top_share(np.array([5, 3, 1, 1]), 1) == pytest.approx(0.5)


@pytest.mark.parametrize("alpha", [1.8, 2.5])
def test_pareto_fit_recovers_known_exponent(alpha):
    rng = np.random.default_rng(1)
    # Inverse-CDF sampling from a Pareto with xmin = 1.
    x = (1 - rng.random(5000)) ** (-1 / (alpha - 1))
    fit = stats.fit_pareto(x)
    assert fit.alpha == pytest.approx(alpha, abs=0.12)
    assert fit.tail_index == pytest.approx(alpha - 1, abs=0.12)


def test_pareto_bootstrap_interval_covers_estimate():
    rng = np.random.default_rng(2)
    x = (1 - rng.random(2000)) ** (-1 / 1.5)
    fit = stats.fit_pareto(x, bootstrap=30, seed=3)
    assert fit.ci_low < fit.alpha < fit.ci_high


def test_demeaned_ols_recovers_slope_and_ignores_group_shifts():
    rng = np.random.default_rng(4)
    groups = np.repeat(np.arange(5), 400)
    x = rng.normal(size=groups.size)
    y = 0.3 * x + groups * 10 + rng.normal(scale=0.5, size=groups.size)
    reg = stats.demeaned_ols(x, y, groups)
    assert reg.slope == pytest.approx(0.3, abs=0.05)
    assert abs(reg.t) > 10


def test_binned_means_shape():
    x = np.arange(100.0)
    mx, my, half = stats.binned_means(x, 2 * x, bins=5)
    assert mx.shape == my.shape == half.shape == (5,)
    assert np.allclose(my, 2 * mx)
