# Analysis-host runbook: from "the containers are gone" to a citable archive

Written 2026-10-30, after the published archive was found to contain code only.
Everything below runs on the analysis host (`ssh cybernord`), in the repository
clone, in this order. Stop at the first REFUSED and read it: every refusal in
these scripts is deliberate and names what is missing.

The deleted Docker containers are the substrate, not the evidence. The reported
figures come from `jobs.csv` and the per-branch directories under
`data/raw/<stack-id>/<matrix>/`. If those files are intact, nothing needs to be
re-executed and no container needs to be rebuilt. Step 0 decides that, and
nothing else should be attempted before it answers.

## Step 0 — does the evidence still exist?

```bash
ssh cybernord
cd ~/csc-iot            # or wherever the clone is: `ls -d ~/csc-iot*`
for m in b5-matrix-v2 d45-matrix-v1 d6-pilot-v2; do
  find data/raw -maxdepth 2 -type d -name "$m" \
       -not -path '*_quarantine*' -not -path '*_legacy*' |
  while read -r r; do
    printf '%-16s %s  jobs.csv:%s  branches:%s\n' "$m" "$r" \
      "$([ -f "$r/jobs.csv" ] && wc -l < "$r/jobs.csv" | tr -d ' ' || echo MISSING)" \
      "$(find "$r" -maxdepth 1 -type d ! -path "$r" | wc -l | tr -d ' ')"
  done
done
```

Expected, and the only outcome that lets the paper proceed as written:

```
b5-matrix-v2     data/raw/<stack>/b5-matrix-v2   jobs.csv:6211  branches:6210
d45-matrix-v1    data/raw/<stack>/d45-matrix-v1  jobs.csv:1801  branches:1800
d6-pilot-v2      data/raw/<stack>/d6-pilot-v2    jobs.csv:109   branches:108
```

(`jobs.csv` is one line longer than the branch count: the header.)

- **All three present** -> continue to Step 1. The container deletion cost
  nothing.
- **Any of them missing or short** -> stop and report the exact output. Do not
  re-run anything yet. A partial re-execution produces branches from a different
  substrate than the ones already reported, and mixing them silently is how a
  figure gets attributed to hardware that did not run it. The paper's 8118
  branches are either all re-derived from one substrate or the claim changes.

## Step 1 — bring the clone up to the committed state

The CRC ledger exporter and the independent replay do not exist in any earlier
commit. From the Mac, once (the host VM used here has no GitHub credentials):

```bash
git push origin main
```

Then on the host:

```bash
git fetch origin && git status --short
git stash list                     # make sure nothing local is about to be lost
git merge --ff-only origin/main
git log --oneline -1               # must be the epsilon-Diagnosis commit
```

## Step 2 — export the ledger, replay it independently, build the package

One command does all of it, finds the three matrix roots itself, and refuses on
a matrix that appears under zero or more than one stack id:

```bash
python3 -c 'import numpy, pandas; print("deps ok")'
bash scripts/package_reported_matrices.sh 2>&1 | tee /tmp/package.log
```

It prints the branch total, which must be **8118**, and writes
`dist/csc-iot-data.tar.gz`. Along the way it writes
`crc_calibration.csv` (every calibration branch with its run key, anchor,
action, predicted risk, uncertainty, observed `Y_ms` and failure indicator) and
`crc_curve_independent.csv`.

## Step 3 — the number that has never been independently checked

```bash
primary=$(find data/raw -maxdepth 2 -type d -name b5-matrix-v2 \
            -not -path '*_quarantine*' -not -path '*_legacy*')
python3 analysis/recompute_crc_independent.py "$primary/crc_calibration.csv"
```

This imports only `argparse`, `csv` and `math`. It must print `runs=20` and
`tau_hat=0.0447`, and the corrected risk must be at or below `0.10`.

- **`tau_hat=0.0447`** -> the manuscript's threshold survives a replay that
  shares no code with the implementation that produced it.
- **anything else, including `tau_hat=NONE` or `REFUSED: reconstructed loss is
  not monotone`** -> stop. Section V of the paper is wrong and must be rewritten
  around the replayed value, not the published one. Do not adjust `delta`,
  `u_max` or the split to recover 0.0447.

Also confirm no run unit straddles a split, which is the premise the guarantee
rests on:

```bash
python3 - <<'PY'
import csv, collections
import glob
p = glob.glob('data/raw/*/b5-matrix-v2/crc_calibration.csv')[0]
rows = list(csv.DictReader(open(p)))
key = lambda r: (r['seed'], r['fault_type'], r['fault_onset'],
                 r['fault_severity'], r['workload_level'])
runs = collections.defaultdict(set)
for r in rows:
    runs[key(r)].add(r['split'])
print('calibration runs:', len(runs))
bad = {k: v for k, v in runs.items() if len(v) != 1}
print('runs spanning more than one split:', len(bad))
print('anchors per run:', sorted({len({r["anchor"] for r in rows if key(r)==k})
                                  for k in runs}))
PY
```

## Step 4 — verify the package the way a reviewer would

In a clean directory, with nothing from the repository on the path:

```bash
rm -rf /tmp/verify && mkdir -p /tmp/verify && cd /tmp/verify
tar -xzf ~/csc-iot/dist/csc-iot-data.tar.gz
cd zenodo-data
shasum -a 256 -c SHA256SUMS | grep -v ': OK$' || echo "ALL CHECKSUMS OK"
cat */branch_index.txt | wc -l                      # 8118
python3 -I recompute_crc_independent.py b5-matrix-v2/crc_calibration.csv
cd rcaeval && python3 -I verify_independent.py      # must end: VERIFICATION OK
```

`python3 -I` is not decoration: it stops the interpreter from importing anything
out of the extracted directory, which is what makes this a replay rather than a
re-run of the same code.

## Step 5 — publish, and do not move a tag again

The published 0.3 record contains one 764,856-byte file,
`Dev-Nikita/csc-iot-0.3.zip`, holding the repository at commit `5d0ed56` and no
data: no `jobs.csv`, no CRC ledger, no RCAEval cases, no checksums. The GitHub
tag `0.3` has since been moved to `63f215a`, so the tag and the archived zip are
now different trees. Create a new tag; never re-point `0.3`.

```bash
# on the Mac, after Steps 2-4 pass on the host
git tag -a 0.4 -m "data package: 8118 branches, CRC ledger, RCAEval cases"
git push origin 0.4
```

Then, on the Zenodo record for `10.5281/zenodo.23165224`, use **New version**
and upload *both* files to the same version:

1. `csc-iot-0.4.zip` (the code, from the GitHub release)
2. `csc-iot-data.tar.gz` (the derived data, from Step 2)

Add all four authors as creators — the 0.3 DataCite record lists one. Then
confirm from the outside, not from the browser session that uploaded it:

```bash
curl -s https://zenodo.org/api/records/<new-id> |
  python3 -c 'import json,sys; d=json.load(sys.stdin);
print(d["doi"]); [print(f["key"], f["size"]) for f in d["files"]]'
```

Finally put that **version** DOI — not the concept DOI — into
`paper/main.tex`, `paper/supplement.tex`, `paper/submission-ready-keep/README.md`
and `paper/submission-ready-keep/cover_letter.md`, rebuild, and re-run
`bash scripts/audit_repo.sh`.

## What is still not done by any of the above

The replay in Step 3 is a different implementation, but it is still run by the
authors. The presubmission gate asks for a person outside this work to repeat
Steps 3 and 4 from the published archive alone. Until that happens the result is
internally audited, not independently verified, and the paper should say exactly
that.
