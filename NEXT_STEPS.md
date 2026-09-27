# What to do next, in order

Updated 2026-09-27 (after protocol 0.10). Each step says who does it, what it produces, and what
would make it fail. A step is not finished until its check passes; a step whose
check fails is not worked around.

Commands marked **[server]** run on `cybernord` in `~/csc-iot`. Commands marked
**[mac]** run in the project folder. `make deploy HOST=cybernord` before any
server step that uses code changed since the last deploy.

---

## Step 1 — Spanning-regime holdout — DONE

Transfer, not memorisation: trained with every spanning branch removed, the
model reaches MAE 0.0479 on spanning branches against 0.1922 for a constant.
The irreducible component is bounded at 1.9x the post-onset error.

## Step 2 — Structural model — DONE, with a negative result and a fix

`analysis/structural.py` is written, frozen, and documented; three assumptions
are stated in its header and in the paper. `analysis/structural_signtest.py` is
the preregistered test.

On cumulative counters the model reproduces 190/203 resolvable signs and fails
13, all of them THROTTLE at anchor a02. Diagnosis: `served + q = lambda*k` holds
identically, so onset and severity are not separately identifiable from
cumulative counters; and at epoch 2 the cumulative arrival rate reads 50 while
the steady rate is 100, so an admission cap of 50 looks non-binding. Post-onset
signs were already 103/103.

Fix, protocol 0.10: the gateway reports `ingress_accepted_last_epoch`, each edge
reports `served_last_epoch`, `features.py` exposes both and flags their absence,
the model reads them. Verified neutral on existing data: predictions are
bit-identical through the fallback path. Pre-amendment record kept at
`data/derived/structural-prefix-v1/`.

**Still open:** the fix cannot be evaluated without new branches. That is Step 3.

## Step 3 — Rebuild and re-run B5 with the windowed observables — Nikita [server]

The node binary changed, so the matrix must be re-run before any model layer is
compared. Nothing else in the design moves: same 24 scenarios, same anchors,
same budget, same gate.

```bash
# on the mac, in the project folder
make deploy HOST=cybernord

# on the server
cd ~/csc-iot
go build ./... && go vet ./... && go test ./... 2>&1 | tail -20
python3 -m pytest -q analysis/ 2>&1 | tail -5
bash scripts/audit_repo.sh | tail -3
```

All four must pass. The audit now carries six new guards for the windowed
observables; if one fails, the deploy did not land.

Then a three-scenario pilot, NOT the full matrix, to confirm the new counters
actually appear in `anchor.json`. The pilot needs its own scenario file, drawn
by the same generator so that its hash is declared rather than hand-edited:

```bash
cd ~/csc-iot
python3 scripts/gen_scenarios.py --n 3 --master-seed 20260927 \
  --mechanisms D1 --workloads 100 --out configs/scenarios-windowed-pilot.json

SCENARIOS=configs/scenarios-windowed-pilot.json ANCHOR_LIST="2,18" \
  bash scripts/m2prime_nats_matrix.sh windowed-pilot-v1 2>&1 | tail -20
```

Anchor 2 is the one that failed, anchor 18 the one that already passed, so this
pilot tests exactly the two cases that matter. Then:

```bash
R=$(ls -dt data/raw/*/windowed-pilot-v1 | head -1)
python3 analysis/audit_accounting.py $R
python3 analysis/jobs.py $R --latency-max-ms 3000 --latency-max-epochs 14 \
  --allow-partial-cost --out $R/jobs.csv | tail -5
python3 analysis/structural.py $R $R/jobs.csv --out $R/structural.csv
python3 analysis/structural_signtest.py $R/jobs.csv $R/structural.csv | head -8
```

**Check:** the sign test's first line must read `WINDOWED OBSERVABLES present in
N/N anchors sampled`. If it reads `0/N`, the containers are running an old
image — rebuild them, do not proceed. A pilot this small will resolve few
contrasts; that is expected and is not the test. What matters here is that the
counters exist and that `audit_accounting.py` still passes all its invariants
with the new fields present.

Only then the full matrix:

```bash
nohup bash scripts/run_nightly.sh b5-matrix-v2 > logs/b5-matrix-v2.log 2>&1 &
bash scripts/run_nightly.sh --status
```

~2880 branches at ~22 s is about 17.6 h. Start it before leaving the server.

## Step 4 — Re-test the structural layer, then compare — mine

With `b5-matrix-v2` in hand: the sign test again, and only if it passes, the
structural-versus-associative comparison under the Section 11b retention rule.

If the sign test still fails at a02 with windowed counters present, the cause is
not the telemetry and the model is wrong — that gets reported as written, and
the paper reports an associative structural layer instead. The retention rule
was fixed before these sets were seen and does not move either way.

## Step 5 — Budget calibration for workload 60 and 140 — Nikita [server]

Two short runs. Protocol 0.9 requires a budget per workload level; only L=100 is
frozen at 750 ms, so every cross-load figure is currently unscorable. Workload is
a scenario factor, not an environment variable, so each calibration needs its own
single-workload scenario file:

```bash
cd ~/csc-iot
for L in 60 140; do
  python3 scripts/gen_scenarios.py --n 2 --master-seed 2026092$L \
    --mechanisms D1 --workloads $L --out configs/scenarios-cal-L$L.json
  SCENARIOS=configs/scenarios-cal-L$L.json ANCHOR_LIST="2,6" \
    bash scripts/m2prime_nats_matrix.sh budget-cal-L$L 2>&1 | tail -3
  python3 analysis/calibrate_budget.py $(ls -dt data/raw/*/budget-cal-L$L | head -1)
done
```

Calibration is defined on healthy `NO_OP` branches, which is why the anchors are
early ones. Write both results into `configs/budgets.json`, which currently holds
only `100 -> 750`, and record them as a protocol amendment. Independent of
Step 3 — it can run any time, including while the matrix is running if the
machine has headroom, though separately is safer.

## Step 6 — MIGRATE with real side effects; mechanisms D2 and D3

D2 needs mid-branch netem, D3 is severity 0 (a declared no-op fault, the control
for "does the label alone move the objective").

## Step 7 — Controller — mine

Ensemble K=10, CRC on the set-level loss, MNI with abstention, reported per
regime beside the ensemble spread that produced it.

## Step 8 — Baselines B1-B4, B5t, ablations A1-A2, D0 audit — Nikita [server]

## Step 9 — Finish the manuscript, and the page budget

Measured today, not estimated: the manuscript compiles to **exactly 10 pages**
with all 20 references resolved and no undefined citations. References occupy
page 10 alone.

Two things were wrong with the build and are now fixed. `IEEEtran.bst` lived one
directory above the repository, so `bibtex` silently failed and `main.bbl` was
empty --- every PDF built in that state had **no bibliography at all**, which is
why the paper appeared to fit comfortably. The style file is now inside `paper/`,
the submission package is self-contained, and `main.bbl` carries all 20 entries.

The honest consequence: 10 pages is the TNSM free limit and the paper is already
at it, with 12 TODO blocks left --- six results subsections, two figures, the
abstract and the closing sentence. Those will add roughly two to three pages.
Plan for it now rather than discover it at submission:

- TNSM allows up to 16 pages at \$220 per page over 10, with an academic waiver
  requestable within 30 days of acceptance. Twelve to thirteen pages is a normal
  submission, not a problem, provided the overage is deliberate.
- The compression levers, in the order they cost least: Section 2's related-work
  table, the two figures if the tables carry the same numbers, and the
  System Model's worked example.
- Do not compress by deleting the identifiability subsection or the four-band
  reporting. Those are the parts a reviewer will check.

Build it as a self-contained package:

```bash
cd paper && latexmk -C && latexmk -pdf main.tex && pdfinfo main.pdf | grep Pages
```

Still needed from Nikita: the `\thanks` e-mail address and the artifact URL.
