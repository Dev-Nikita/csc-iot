# CRC implementation audit

Date: 2026-10-30.  Scope: internal code-and-claim audit, not the independent
third-party audit required by `PRESUBMISSION.md`.

## Result

The implemented calibration rule matches equation (4) of Angelopoulos et al.,
*Conformal Risk Control* (ICLR 2024), after the manuscript's change of parameter
from the paper's non-increasing `lambda` to `tau = -lambda`:

`(n * empirical risk + B) / (n + 1) <= delta`.

For the manuscript's set loss, increasing `tau` can only add admissible actions,
so the loss is non-decreasing.  Selecting the largest feasible `tau` is therefore
the transformed version of selecting the smallest feasible `lambda`.  The code
rejects a non-monotone loss matrix, uses the run rather than the temporally
dependent anchor as the calibration unit, returns abstention when no threshold
is feasible, and keeps fallback outcomes outside the stated guarantee.

The claim about adaptive action selection is pointwise valid: whenever the
controller selects an action from the admissible set, its binary failure
indicator cannot exceed the indicator that *some* action in that set fails.
This does not cover the fallback used when the set is empty.

## Defect found and repaired

`intelligence/tests/test_crc.py::test_guarantee_holds_on_held_out_runs` counted
the frequency with which a fresh loss exceeded `delta`.  CRC controls expected
loss, not that tail probability.  The test now averages fresh held-out losses
over independently recalibrated trials and checks the quantity the theorem
actually bounds.  This was a test-semantics defect; it did not alter the
calibration code or any reported result.

## Assumption that code cannot certify

The theorem requires exchangeability of the calibration runs and a future run
after conditioning on the already-fitted predictor and validation choices.  The
pipeline assigns complete `(design point, seed)` runs to splits with a fixed
random permutation and never treats anchors as exchangeable observations.  This
is consistent with exchangeability over the declared finite ID run pool (or a
future run sampled by the same declared design-point/seed mechanism), but code
inspection cannot establish that the physical executions are identically
distributed: drift, hidden host state, or changes in the generator would break
the premise.  The paper correctly excludes scenario shift, but the independent
audit must still verify the run manifests and the construction of the ID pool.

## Remaining independent checks

1. Reconstruct the 20 calibration run identifiers from the archived manifests
   and confirm that no anchor or branch crosses a split boundary.
2. Recompute `theta`, every `L_i(tau)`, the corrected-risk curve, and
   `tau_hat = 0.0447` from the archived data without importing the project CRC
   implementation.
3. Confirm that predictor fitting and `U_max` selection use only training and
   validation data, respectively, before calibration outcomes are opened.
4. Inspect execution dates and stack identifiers for evidence against the
   exchangeability premise and report any such evidence rather than treating
   independent seeds as sufficient by themselves.

Until another researcher performs those checks, the presubmission gate remains
open and the result should be described as internally audited, not independently
verified.

## Portable audit path added after this review

`analysis/export_crc_ledger.py` now freezes every calibration branch's run key,
anchor, action, predicted risk, uncertainty, observed `Y_ms`, failure indicator
and all calibration constants. `analysis/recompute_crc_independent.py` consumes
only that CSV and Python's standard library; it does not import the project CRC
or predictor implementation. The archive packager refuses to build without the
ledger and its independently reconstructed curve. These tools make the external
audit possible, but their real-data output cannot be produced in this checkout
because the reported matrices remain on the analysis host.
