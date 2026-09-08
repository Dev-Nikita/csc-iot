"""Unit tests for the CRC threshold rule, on synthetic monotone losses whose
risk is known in closed form."""
import numpy as np
import pytest

from crc import calibrate, corrected_risk


def monotone_losses(n_runs, taus, rate, rng):
    """L_i(tau) = clip(rate * tau + noise, 0, 1): monotone by construction."""
    noise = rng.normal(0, 0.01, size=(n_runs, 1))
    return np.clip(rate * taus[None, :] + noise, 0.0, 1.0)


def test_correction_matches_closed_form():
    losses = np.full(20, 0.05)
    assert corrected_risk(losses) == pytest.approx((20 * 0.05 + 1.0) / 21)


def test_correction_is_material_at_realistic_n():
    """At n=20 the correction is ~0.048 -- the same order as delta itself.
    A test that lets this shrink silently would hide a real regression."""
    assert corrected_risk(np.zeros(20)) == pytest.approx(1 / 21, abs=1e-9)
    assert corrected_risk(np.zeros(20)) > 0.045


def test_picks_largest_feasible_tau():
    rng = np.random.default_rng(0)
    taus = np.linspace(0.01, 0.5, 50)
    L = monotone_losses(30, taus, rate=0.4, rng=rng)
    out = calibrate(L, taus, delta=0.10)
    assert out["feasible"]
    j = taus.tolist().index(out["tau_hat"])
    assert out["corrected_risk"] <= 0.10
    if j + 1 < len(taus):  # the next threshold up must violate the level
        nxt = corrected_risk(L[:, j + 1])
        assert nxt > 0.10


def test_infeasible_returns_none_rather_than_relaxing():
    rng = np.random.default_rng(1)
    taus = np.linspace(0.1, 0.9, 20)
    L = monotone_losses(20, taus, rate=2.0, rng=rng)  # loss high everywhere
    out = calibrate(L, taus, delta=0.01)
    assert out["tau_hat"] is None and not out["feasible"]


def test_rejects_non_monotone_loss():
    taus = np.array([0.1, 0.2, 0.3])
    L = np.array([[0.5, 0.1, 0.6]])  # dips: not a valid CRC loss
    with pytest.raises(ValueError, match="non-decreasing"):
        calibrate(L, taus, delta=0.5)


def test_guarantee_holds_on_held_out_runs():
    """The point of the whole exercise: calibrate on n runs, check the realised
    loss on fresh exchangeable runs sits at or below delta on average."""
    rng = np.random.default_rng(7)
    taus = np.linspace(0.01, 0.6, 60)
    delta, breaches = 0.10, 0
    trials = 200
    for _ in range(trials):
        cal = monotone_losses(25, taus, rate=0.35, rng=rng)
        out = calibrate(cal, taus, delta=delta)
        if out["tau_hat"] is None:
            continue
        j = taus.tolist().index(out["tau_hat"])
        fresh = monotone_losses(1, taus, rate=0.35, rng=rng)
        breaches += fresh[0, j] > delta
    assert breaches / trials <= delta + 0.05   # slack for a finite trial count
