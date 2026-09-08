"""Conformal risk control for the CSC admissibility threshold.

Implements the finite-sample rule of Angelopoulos, Bates, Fisch, Lei and
Schuster, "Conformal Risk Control", ICLR 2024.

What is calibrated and what is not
----------------------------------
NOT calibrated: the predicted interventional risk R_hat(a | S). It estimates a
latent conditional probability that is never observed -- a replay branch yields
a binary outcome, not that probability -- so there is no residual to
conformalise and no basis for "R_hat + quantile".

Calibrated: the threshold tau in the admissible set

    A_safe(tau) = { a : R_hat(a|S) <= tau  and  U_hat(a|S) <= U_max }

against the within-run set-level loss

    L_i(tau) = (1/|T_i|) * sum_{t in T_i} 1[ exists a in A_safe_it(tau) : Y^a_it = 1 ]

L_i is bounded in [0,1] and NON-DECREASING in tau, because relaxing the
threshold can only enlarge A_safe. The CRC theorem is stated for a loss
non-increasing in its parameter, so we work with lambda = -tau; concretely this
means taking the LARGEST tau whose corrected risk still meets the level.

Why the calibration unit is a run, not a decision point
------------------------------------------------------
Decision points inside one run are temporally dependent and are not exchangeable
samples. Independent seeds give exchangeable runs. Each run contributes one
number L_i(tau), and CRC is applied across runs.

Guarantee obtained (and its limits)
-----------------------------------
    E[ L_{n+1}(tau_hat) ] <= delta

over a future exchangeable run. It is marginal over runs, not conditional and
not per-decision. It bounds the failure probability of ANY rule selecting from
A_safe -- which is what makes it survive the controller choosing adaptively --
but it says nothing about the fallback taken when A_safe is empty, where the
loss is zero by construction.
"""
from __future__ import annotations

import numpy as np

LOSS_BOUND = 1.0  # the set-level loss is an indicator mean, so B = 1


def corrected_risk(run_losses: np.ndarray, loss_bound: float = LOSS_BOUND) -> float:
    """Finite-sample corrected empirical risk: (n * mean + B) / (n + 1).

    The correction is not decoration. At n = 20 calibration runs it inflates the
    empirical risk by B/(n+1) ~ 0.048 -- comparable to delta itself. Selecting
    tau by uncorrected empirical risk would not carry the guarantee.
    """
    n = len(run_losses)
    if n == 0:
        raise ValueError("no calibration runs")
    return (n * float(np.mean(run_losses)) + loss_bound) / (n + 1)


def calibrate(loss_matrix: np.ndarray, taus: np.ndarray, delta: float,
              loss_bound: float = LOSS_BOUND) -> dict:
    """Select tau_hat = sup { tau : corrected_risk(L(tau)) <= delta }.

    loss_matrix : (n_runs, n_taus), entry [i, j] = L_i(taus[j]), in [0, 1] and
                  non-decreasing along the tau axis.
    taus        : strictly increasing candidate grid.

    Returns tau_hat and the diagnostics a reviewer will ask for. If no candidate
    satisfies the constraint, tau_hat is None: the honest outcome is that no
    non-trivial admissible set can be certified at this delta, and the caller
    must abstain everywhere rather than quietly relax the level.
    """
    loss_matrix = np.asarray(loss_matrix, dtype=float)
    taus = np.asarray(taus, dtype=float)
    if loss_matrix.ndim != 2 or loss_matrix.shape[1] != len(taus):
        raise ValueError("loss_matrix must be (n_runs, len(taus))")
    if not np.all(np.diff(taus) > 0):
        raise ValueError("taus must be strictly increasing")
    if loss_matrix.min() < 0 or loss_matrix.max() > loss_bound:
        raise ValueError(f"losses must lie in [0, {loss_bound}]")
    violations = np.diff(loss_matrix, axis=1) < -1e-12
    if violations.any():
        bad = int(violations.any(axis=1).sum())
        raise ValueError(
            f"loss is not non-decreasing in tau for {bad} run(s); "
            "CRC does not apply. This usually means A_safe was not computed "
            "monotonically -- check that U_max filtering is independent of tau."
        )

    corrected = np.array([corrected_risk(loss_matrix[:, j], loss_bound)
                          for j in range(len(taus))])
    ok = corrected <= delta
    idx = int(np.max(np.flatnonzero(ok))) if ok.any() else None

    return {
        "tau_hat": None if idx is None else float(taus[idx]),
        "delta": float(delta),
        "n_runs": int(loss_matrix.shape[0]),
        "empirical_risk": None if idx is None else float(loss_matrix[:, idx].mean()),
        "corrected_risk": None if idx is None else float(corrected[idx]),
        "correction_term": loss_bound / (loss_matrix.shape[0] + 1),
        "taus": taus.tolist(),
        "corrected_curve": corrected.tolist(),
        "feasible": bool(ok.any()),
    }
