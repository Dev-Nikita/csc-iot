# Runbook to a finished paper

One file, in order, copy-paste ready. Written 2026-09-27 at protocol 0.10.

**Legend.** `[SERVER]` = paste on `cybernord`, in `~/csc-iot`. `[MAC]` = paste in
the project folder on the laptop. `[CLAUDE]` = I do it, you do nothing.

Every phase ends with a **STOP** condition. A STOP is not advice. If it trips,
send me the output and do not run the next block — three matrices have already
been thrown away to defects that were visible in the numbers and that nothing
looked at.

---

## Phase 1 — Deploy protocol 0.10 and restart B5  `[MAC]` then `[SERVER]`

The node binary changed, so every existing branch was recorded against a
different observable set. The matrix must be re-run before the structural and
associative layers can be compared on the same state.

### 1.1 Push the code `[MAC]`

```bash
cd ~/"Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot-v2"
make deploy HOST=cybernord
```

### 1.2 Verify the deploy landed `[SERVER]`

```bash
cd ~/csc-iot
go build ./... && go vet ./... && go test ./... 2>&1 | tail -20
python3 -m pytest -q analysis/ 2>&1 | tail -5
bash scripts/audit_repo.sh | tail -3
```

**STOP** unless all three pass and the audit prints `REPO AUDIT OK`. It now
carries 54 guards, eight of them new today. A failing guard means the sync did
not land, not that the guard is wrong.

### 1.3 Bring up the reportable stack `[SERVER]`

```bash
cd ~/csc-iot
make stack-nats
python3 check_reportable_stack.py --print-stack-id
```

**STOP** unless a stack id is printed. Note it down; every path below contains
it, and `$STACK` in the blocks that follow means exactly this value.

```bash
STACK=$(python3 check_reportable_stack.py --print-stack-id)
echo "STACK=$STACK"
```

### 1.4 Three-scenario pilot — the one thing that must not be skipped `[SERVER]`

Its only job is to prove the two new counters reach `anchor.json`. Anchors 2 and
18 are chosen because a02 is exactly where the structural model failed and a18
is where it already passed.

```bash
cd ~/csc-iot
python3 scripts/gen_scenarios.py --n 3 --master-seed 20260927 \
  --mechanisms D1 --workloads 100 --out configs/scenarios-windowed-pilot.json

SCENARIOS=configs/scenarios-windowed-pilot.json ANCHOR_LIST="2,18" \
  bash scripts/m2prime_nats_matrix.sh windowed-pilot-v1 2>&1 | tail -20
```

Then score it:

```bash
cd ~/csc-iot
R=data/raw/$STACK/windowed-pilot-v1
python3 analysis/audit_accounting.py $R
python3 analysis/jobs.py $R --latency-max-ms 3000 --latency-max-epochs 14 \
  --allow-partial-cost --out $R/jobs.csv | tail -5
python3 analysis/structural.py $R $R/jobs.csv --out $R/structural.csv
python3 analysis/structural_signtest.py $R/jobs.csv $R/structural.csv | head -8
```

**STOP** unless the last command's first line reads

```
WINDOWED OBSERVABLES present in N/N anchors sampled
```

with both numbers equal and non-zero. `0/N` means the containers are running the
old image: `make stack-nats` again and confirm the rebuild. A pilot this small
resolves few contrasts; that is expected and is not what is being tested here.

### 1.5 Launch the full matrix `[SERVER]`

`run_nightly.sh` detaches itself with `setsid`, so no `nohup`, no `tmux`, and the
laptop may sleep or disconnect.

```bash
cd ~/csc-iot
bash scripts/run_nightly.sh b5-matrix-v2 SCENARIOS=configs/scenarios-b5.json \
  ANCHOR_LIST="2,6,10,14,18,22,26,30" REPEATS=5 HORIZON=8 \
  ACTIONS="NO_OP THROTTLE REROUTE"
```

2880 branches at roughly 22 s is about 17.6 hours. Check on it from anywhere:

```bash
cd ~/csc-iot && bash scripts/run_nightly.sh --status
tail -5 logs/b5-matrix-v2.log
```

The wrapper now runs the accounting audit itself and **stops before the analysis
if it fails**, leaving `logs/b5-matrix-v2.audit-failed` behind. Until today it
passed two obsolete flags to the audit, argparse rejected them, and no nightly
run was ever audited at all — so if you remember that line scrolling past, that
is what it was.

### 1.6 Budget calibration for workload 60 and 140 `[SERVER]`

Independent of everything above; do it while the matrix runs only if the machine
has headroom, otherwise after. Protocol 0.9 requires one budget per workload
level and only L=100 is frozen, at 750 ms, so every cross-load figure is
currently unscorable. Workload is a scenario factor, not an environment
variable, so each calibration needs its own single-workload file.

```bash
cd ~/csc-iot
for L in 60 140; do
  python3 scripts/gen_scenarios.py --n 2 --master-seed 2026092$L \
    --mechanisms D1 --workloads $L --out configs/scenarios-cal-L$L.json
  SCENARIOS=configs/scenarios-cal-L$L.json ANCHOR_LIST="2,6" \
    bash scripts/m2prime_nats_matrix.sh budget-cal-L$L 2>&1 | tail -3
  python3 analysis/calibrate_budget.py data/raw/$STACK/budget-cal-L$L --workload $L
done
```

Send me both printed budgets. I write them into `configs/budgets.json` and log
the amendment — do not hand-edit that file, the runner checks it.

---

## Phase 2 — The decision layer  `[CLAUDE]`, runs in parallel with Phase 1

This is the largest piece of code still missing and it needs no server, so it
gets written while the matrix runs. Nothing for you to do here.

What I am building, over the branch matrix, offline:

- `analysis/predictor.py` — the action-conditioned ensemble, K=10, in numpy
  (no scipy, sklearn or torch on either machine, and no reason to need them).
- `analysis/crc.py` — conformal risk control on the set-level monotone loss,
  calibrating `tau_hat` for a declared `delta`.
- `analysis/policies.py` — the decision methods, including minimum-necessary
  intervention with guarded abstention.
- `analysis/evaluate.py` — `CRA_eta`, `Reg_eta`, `CRA@2`, common-anchor PFR and
  WIR, on the shared denominator, reported per regime.

**A scope decision, so you can object now rather than at submission.** The
methods I will implement and report are: B1 reactive threshold, B2 the
associative action-conditioned predictor, B5t the retained time-only baseline,
B6 full CSC, and ablations A1 (no gate) and A2 (no minimum-necessary
intervention).

I am dropping two baselines from the original plan and saying so in the
Limitations:

- **B3 graph-based.** The topology is one gateway and three edges. A graph
  baseline has no graph structure to exploit here and would be B2 with a
  different name. Reporting it as a distinct baseline would be padding.
- **B4 PPO.** A reinforcement-learning baseline needs online interaction with
  the environment. Trained on replay data it can only be evaluated off-policy,
  which is a different paper and a weaker comparison, not a stronger one. What I
  will report instead is the strongest associative predictor buildable on
  *identical* state, which is the comparison that actually bears on the claim.

A3, the no-causal ablation, is not a separate run: B2 **is** the no-causal arm,
and it is reported as such. Three honest baselines beat five hand-waved ones,
and a reviewer who checks will find the argument in the paper rather than a gap.

Say the word if you want B4 attempted anyway and I will, with the off-policy
caveat stated in the text.

---

## Phase 3 — Score the new matrix  `[SERVER]`

Run after `b5-matrix-v2` finishes with exit 0 **and** after I tell you Phase 2
has landed and you have re-run `make deploy`.

```bash
cd ~/csc-iot
STACK=$(python3 check_reportable_stack.py --print-stack-id)
R=data/raw/$STACK/b5-matrix-v2
cat logs/b5-matrix-v2.done          # must be 0
ls logs/b5-matrix-v2.audit-failed   # must NOT exist
```

**STOP** if `.done` is not `0` or if the audit-failed marker exists.

```bash
cd ~/csc-iot
python3 analysis/audit_accounting.py $R
python3 analysis/jobs.py $R --latency-max-ms 3000 --latency-max-epochs 14 \
  --allow-partial-cost --out $R/jobs.csv | tail -20
python3 analysis/band_sensitivity.py $R/jobs.csv | tail -25
```

**STOP** and send me the output if the band section reports that no contrast
survives all four bands. Everything downstream is then meaningless and the
answer is a design change, not another script.

```bash
cd ~/csc-iot
python3 analysis/leakage_tests.py $R $R/jobs.csv | tail -20
python3 analysis/regime_holdout.py $R $R/jobs.csv --regime spanning | tail -12
```

**STOP** if either leakage test fails. A model result published over a failed
leakage test is the single fastest way to be rejected, and correctly.

```bash
cd ~/csc-iot
python3 analysis/structural.py $R $R/jobs.csv --out $R/structural.csv
python3 analysis/structural_signtest.py $R/jobs.csv $R/structural.csv
```

This is the one I care about most. Send the whole output either way. If it still
fails at a02 with the windowed counters present, the telemetry was not the cause
and the model is wrong — that gets reported as written, and the paper carries an
associative structural layer instead. The retention rule was fixed before any of
these sets were seen and does not move in either direction.

```bash
cd ~/csc-iot
python3 analysis/evaluate.py $R $R/jobs.csv --out $R/decisions.csv
python3 analysis/d0_audit.py
```

Then package everything small enough to send:

```bash
cd ~/csc-iot
tar czf /tmp/b5v2-results.tgz \
  data/raw/$STACK/b5-matrix-v2/jobs.csv \
  data/raw/$STACK/b5-matrix-v2/structural.csv \
  data/raw/$STACK/b5-matrix-v2/decisions.csv \
  data/raw/$STACK/b5-matrix-v2/matrix.json \
  data/raw/$STACK/b5-matrix-v2/scenarios.json \
  logs/b5-matrix-v2.log
ls -la /tmp/b5v2-results.tgz
```

Pull it to the laptop and attach it here:

```bash
scp cybernord:/tmp/b5v2-results.tgz ~/Downloads/
```

---

## Phase 4 — Fill the paper  `[CLAUDE]`

With Phase 3's numbers I close the twelve remaining TODO blocks: six results
subsections, the two figures, the abstract and the closing sentence. Tables come
from `analysis/make_tables.py` so that no number in the manuscript is typed by
hand.

```bash
# for reference; I run this
python3 analysis/make_tables.py --factored-root data/raw/$STACK/b5-matrix-v2 \
  --out-dir paper/generated_tables
```

**The page budget, measured today and not estimated.** The manuscript compiles
to exactly 10 pages with all 20 references resolved — which is the TNSM free
limit, reached before any results section is written. Phase 4 adds roughly two to
three pages.

That is a deliberate 12–13 page submission, which is normal for TNSM: up to 16
pages are allowed at \$220 per page over 10, and an academic waiver can be
requested within 30 days of acceptance. The compression levers, cheapest first,
are the related-work table, then the two figures if the tables already carry
their numbers, then the worked example in the System Model. The identifiability
subsection and the four-band reporting are not levers — those are the parts a
reviewer will check.

Worth knowing why this only surfaced now: `IEEEtran.bst` lived one directory
*above* the repository, so `bibtex` failed silently and `main.bbl` was empty.
Every PDF built in that state had no bibliography at all, which is why the paper
appeared to fit. The style file is now inside `paper/`.

---

## Phase 5 — Submission package  `[MAC]` and `[CLAUDE]`

### 5.1 Two things only you can supply

- the e-mail address for the `\thanks` block on page 1;
- the public artifact URL (Zenodo or GitHub release) for the reproducibility
  statement. If there is no URL yet, say so and I will write the statement with
  an explicit placeholder rather than a plausible-looking link.

### 5.2 Build it self-contained `[MAC]`

```bash
cd ~/"Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot-v2/paper"
latexmk -C
latexmk -pdf main.tex
pdfinfo main.pdf | grep Pages
grep -c 'Citation.*undefined' main.log      # must be 0
grep -c bibitem main.bbl                    # must be 20
```

### 5.3 Final gates `[MAC]`

```bash
cd ~/"Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot-v2"
make check-stale
python3 paper/check_citations.py
python3 paper/check_stale.py
grep -c 'TODO' paper/main.tex                # must be 1, the macro definition
```

**STOP** on any non-zero TODO count beyond the macro. A `[TODO: ...]` block
renders as bold text in the PDF and reviewers do see it.

---

## What is genuinely still unbuilt, so nothing reads as further along than it is

- The decision layer of Phase 2. Scaffolding exists in `analysis/common.py` and
  `analysis/metrics.py` from the pre-pivot design; the methods themselves do not.
- Fault mechanism D2, the ingress impairment ramp. It needs netem re-applied
  part-way through a branch, and `gen_scenarios.py` refuses to emit it rather
  than quietly running it as D1. Either it gets implemented or the paper claims
  two mechanisms, not three.
- MIGRATE as an action with real side effects. Currently the action set that has
  been measured is NO_OP, THROTTLE and REROUTE.
- The closed-loop system outcome subsection needs a run where the controller
  actually drives the stack, not only scores branches offline. That is a
  separate matrix and it is not in Phase 1's 17.6 hours.

The first is mine and is in flight. The last three are scope decisions, and the
honest options are to implement them or to state the action set and mechanism
count as measured. My recommendation is to state them: a reviewer accepts a
narrow, exactly-described scope far more readily than a broad one with soft
evidence.
