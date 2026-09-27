#!/usr/bin/env python3
"""The decision rules. Each one maps a decision point to an action, nothing more.

A decision point carries, for every candidate action, a predicted risk, an
ensemble uncertainty and an intervention cost. What a policy may look at is
restricted here rather than by convention: the observed outcome is not passed in,
so no rule can accidentally see it.

WHAT IS AND IS NOT IMPLEMENTED, so the paper does not overstate the comparison.

  B1_threshold   a reactive rule on one observable, with its thresholds chosen on
                 the VALIDATION split by grid search over a declared grid
  B2_assoc       the associative challenger: lowest predicted risk, no gate
  B5t_time_only  the permanently retained time-only baseline f(t, a)
  B6_csc         the method: uncertainty filter, calibrated threshold, then the
                 cheapest admissible action, else guarded abstention
  A1a            B6 with the uncertainty filter removed, threshold kept
  A1b            B6 with no gate at all -- degenerate by construction, and
                 reported because that degeneracy is the argument for the gate
  A2_no_mni      B6 with the gate but choosing the lowest-risk admissible action
                 instead of the cheapest. This is the arm the manuscript names as
                 what the controller is NOT

  B3 graph-based and B4 PPO are not implemented, and the reason is in the paper
  rather than here. A3, the no-causal ablation, is B2: the associative challenger
  IS the arm without a causal layer, and reporting it twice under two names would
  inflate the table.

C(NO_OP) = 0 by definition: doing nothing disrupts nothing. The harm of doing
nothing appears in the risk term, which is where it belongs. Without this the
cost rule would rank inaction by the damage the fault is doing, and
minimum-necessary intervention would stop meaning anything.
"""
FALLBACK = "NO_OP"          # declared in advance; the fallback is not learned


def _admissible(risk, unc, tau, u_max):
    return [a for a in risk if risk[a] <= tau and unc[a] <= u_max]


def b1_threshold(point, deficit_t, backlog_t):
    """Reactive: act when an observable crosses a threshold, cheapest first.

    Deliberately the kind of rule an operator writes by hand. It reads the
    windowed service deficit and the admission backlog share, both of which are
    in the permitted state, and it never predicts anything.
    """
    x = point["x"]
    deficit = max(x[f"{e}_serve_deficit_windowed"] for e in
                  ("edge00", "edge01", "edge02"))
    backlog = x["gw00_backlog_depth"] + x["gw01_backlog_depth"]
    offered = max(x["system_accepted_last_epoch"], 1.0)
    if deficit > deficit_t and "REROUTE" in point["risk"]:
        return "REROUTE", False
    if backlog / offered > backlog_t and "THROTTLE" in point["risk"]:
        return "THROTTLE", False
    return "NO_OP", False


def lowest_risk(point, key="risk"):
    r = point[key]
    return min(r, key=lambda a: (r[a], a)), False


def b6_csc(point, tau, u_max):
    safe = _admissible(point["risk"], point["unc"], tau, u_max)
    if not safe:
        return FALLBACK, True
    cost = point["cost"]
    return min(safe, key=lambda a: (cost[a], a)), False


def a1a_no_uncertainty_filter(point, tau):
    """The calibrated threshold kept, the uncertainty filter removed.

    This is the informative reading of "no gate": it isolates what the
    epistemic filter contributes on top of the risk threshold, which is a
    question with an answer.
    """
    safe = [a for a in point["risk"] if point["risk"][a] <= tau]
    if not safe:
        return FALLBACK, True
    cost = point["cost"]
    return min(safe, key=lambda a: (cost[a], a)), False


def a1b_no_gate_at_all(point):
    """No admissible set at all: the cheapest action, always.

    This arm is DEGENERATE BY CONSTRUCTION and that is the point of reporting
    it. With C(NO_OP) = 0, removing the gate entirely makes the cost rule choose
    inaction at every decision point, whatever the state. It is not a competitor
    that happens to do badly; it is the demonstration that minimum-necessary
    intervention is only meaningful downstream of a risk gate. Anyone tempted to
    "fix" it into something that acts has removed the ablation.

    Both readings are reported rather than one chosen silently, because the
    protocol says "no gate" without saying which gate.
    """
    cost = point["cost"]
    return min(cost, key=lambda a: (cost[a], a)), False


def a2_no_mni(point, tau, u_max):
    safe = _admissible(point["risk"], point["unc"], tau, u_max)
    if not safe:
        return FALLBACK, True
    r = point["risk"]
    return min(safe, key=lambda a: (r[a], a)), False


def fit_b1(points, grid_deficit=(0.05, 0.10, 0.20, 0.35, 0.50),
           grid_backlog=(0.10, 0.25, 0.50, 1.00, 2.00)):
    """Choose B1's thresholds on the split it is handed, by mean observed J_obs.

    The grid is declared here, in the source, rather than widened until the
    baseline looks weak. A baseline tuned worse than it can be is not a baseline,
    and the fairest version of the simplest rule is the one worth beating.
    """
    best, best_val = (grid_deficit[0], grid_backlog[0]), float("inf")
    for dt in grid_deficit:
        for bt in grid_backlog:
            tot = 0.0
            for p in points:
                a, _ = b1_threshold(p, dt, bt)
                tot += p["j_obs"].get(a, max(p["j_obs"].values()))
            val = tot / max(len(points), 1)
            if val < best_val:
                best, best_val = (dt, bt), val
    return best, best_val
