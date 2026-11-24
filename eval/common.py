"""Small statistics helpers shared by the evaluation scripts. Standard library only."""
import math
import random


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n. Returns (low, high) or (None, None) when n == 0."""
    if n <= 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def pct(x, digits=1):
    return '-' if x is None else f'{100 * x:.{digits}f}%'


def fmt_rate(k, n):
    """'47/52 = 90.4% (95% CI 79.4% to 96.1%)'  -  always show n, small samples are the whole story here."""
    if n <= 0:
        return '0/0 = n/a'
    lo, hi = wilson(k, n)
    return f'{k}/{n} = {pct(k / n)} (95% CI {pct(lo)} to {pct(hi)})'


def bootstrap_ci(values, stat, reps=2000, seed=0, alpha=0.05):
    """Percentile bootstrap interval of stat(list_of_values). Returns (low, high)."""
    values = list(values)
    if not values:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    est = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(reps))
    return est[int((alpha / 2) * reps)], est[min(reps - 1, int((1 - alpha / 2) * reps))]


def sign_test_p(b, c):
    """Exact two-sided sign test. b and c are the numbers of questions system A won / system B won (ties left out)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)
