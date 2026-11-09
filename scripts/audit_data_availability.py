#!/usr/bin/env python3
"""Verify the data-availability register instead of asserting it.

    python3 -I scripts/audit_data_availability.py --package <zenodo-dir> --raw data/raw/<stack>
    python3 -I scripts/audit_data_availability.py --schema-only

Every row of data_availability.csv claims a level and a recompute command. This
script decides, per row, whether that claim holds, writes
`data_availability_report.json`, and exits non-zero when any row claiming public
reproducibility fails. The register is the source of the manuscript's
data-availability statement, so a row that has not been verified must say
`unverified` and must not be written up as though it had.

The three levels, kept apart on purpose:

  A  the published tables are recomputed from the PUBLIC archive
  B  the experiment is repeated from published code; needs the runtime stack,
     the dependencies and the machine time, and the result may differ because
     the system is nondeterministic -- which is this paper's own subject
  C  only a derived result is published; the inputs needed to redo the step are
     not. Limited checkability, and it is not reproducibility

Collapsing the three into one sentence is what produces a "fully reproducible"
claim that a reviewer can falsify in an afternoon.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

REGISTER = "data_availability.csv"
REQUIRED = ["claim_id", "result_id", "paper_location", "source_run",
            "derived_file", "recompute_command", "level",
            "analysis_host_required", "publicly_reproducible",
            "claim_criticality", "validation_status", "limitations"]
LEVELS = {"A", "B", "C"}
CRITICALITY = {"central", "supporting", "provenance"}


def load(path=REGISTER):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit(f"REFUSED: {path} has no rows")
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        sys.exit(f"REFUSED: {path} lacks columns {missing}")
    return rows


def check_schema(rows):
    """Internal consistency, before anything is run."""
    problems = []
    seen = set()
    for i, r in enumerate(rows, 2):
        rid = r["result_id"]
        if rid in seen:
            problems.append(f"line {i}: duplicate result_id {rid!r}")
        seen.add(rid)
        if r["level"] not in LEVELS:
            problems.append(f"line {i}: level {r['level']!r} not in {sorted(LEVELS)}")
        if r["publicly_reproducible"] not in ("yes", "no", "partial"):
            problems.append(f"line {i}: publicly_reproducible "
                            f"{r['publicly_reproducible']!r}")
        if r["analysis_host_required"] not in ("yes", "no"):
            problems.append(f"line {i}: analysis_host_required "
                            f"{r['analysis_host_required']!r}")
        # The combinations that cannot both be true.
        if r["level"] == "A" and r["analysis_host_required"] == "yes":
            problems.append(f"line {i}: {rid} claims level A and also needs the "
                            f"analysis host; A means recomputable from the "
                            f"public archive")
        if r["level"] == "C" and r["publicly_reproducible"] == "yes":
            problems.append(f"line {i}: {rid} claims level C and public "
                            f"reproducibility; C means the inputs are not "
                            f"published")
        if r["analysis_host_required"] == "yes" and \
                r["publicly_reproducible"] == "yes":
            problems.append(f"line {i}: {rid} needs the analysis host and "
                            f"claims public reproducibility")
        if r["claim_criticality"] not in CRITICALITY:
            problems.append(f"line {i}: claim_criticality "
                            f"{r['claim_criticality']!r} not in "
                            f"{sorted(CRITICALITY)}")
        # Nineteen checkable side tables do not compensate for one unverifiable
        # result that a central claim rests on. The register must make that
        # visible rather than let a count of levels imply the opposite.
        if r["claim_criticality"] == "central" and \
                r["publicly_reproducible"] == "no":
            problems.append(f"line {i}: {rid} carries a CENTRAL claim and is "
                            f"not publicly reproducible. Either publish what it "
                            f"needs, or the claim it supports must be lowered.")
        if r["publicly_reproducible"] == "no" and not r["limitations"].strip():
            problems.append(f"line {i}: {rid} is not publicly reproducible and "
                            f"names no limitation; say what a reader cannot check")
        if r["recompute_command"].strip() in ("", "TBD") and \
                r["validation_status"] == "pass":
            problems.append(f"line {i}: {rid} has no command and claims pass")
    return problems


def substitute(cmd, paths):
    for key, value in paths.items():
        cmd = cmd.replace("{" + key + "}", value)
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", help="the published data package directory")
    ap.add_argument("--raw", help="data/raw/<stack>")
    ap.add_argument("--rcaeval-root", default="")
    ap.add_argument("--schema-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    rows = load()
    problems = check_schema(rows)
    print(f"REGISTER: {len(rows)} results")
    if problems:
        print("\nSCHEMA PROBLEMS")
        for p in problems:
            print("  " + p)
    else:
        print("  schema consistent: no row claims a level its own flags deny")

    by_level = {}
    for r in rows:
        by_level.setdefault(r["level"], []).append(r["result_id"])
    for level in sorted(by_level):
        print(f"  level {level}: {len(by_level[level])} results")
    crit = {}
    for r in rows:
        crit.setdefault(r["claim_criticality"], []).append(r)
    print("  by criticality, which is what a level count hides:")
    for c in sorted(crit):
        pub = sum(1 for r in crit[c] if r["publicly_reproducible"] == "yes")
        print(f"    {c:11s} {len(crit[c]):3d} results, {pub} publicly "
              f"reproducible")
    # The question a reviewer asks first, answered without being asked.
    weak = [r for r in rows if r["claim_criticality"] == "central"
            and r["publicly_reproducible"] != "yes"]
    if weak:
        print("  CENTRAL results a reader cannot fully recompute from the "
              "archive alone:")
        for r in weak:
            print(f"    {r['result_id']:24s} level {r['level']}  "
                  f"{r['publicly_reproducible']:8s} {r['limitations']}")
        print("    These are what the data-availability statement must name "
              "explicitly.")

    if args.schema_only:
        return 1 if problems else 0
    if not args.package and not args.raw:
        sys.exit("REFUSED: pass --package and/or --raw, or --schema-only")

    report, failures = [], []
    for r in rows:
        rid, cmd = r["result_id"], r["recompute_command"].strip()
        rec = {k: r[k] for k in REQUIRED}
        rec["checked_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if cmd in ("", "TBD"):
            rec["outcome"] = "no command yet"
        elif r["analysis_host_required"] == "yes":
            rec["outcome"] = "skipped: declared to need the analysis host"
        elif "{rcaeval_root}" in cmd and not args.rcaeval_root:
            rec["outcome"] = "skipped: no --rcaeval-root given"
        else:
            paths = {"package": args.package or "", "raw": args.raw or "",
                     "rcaeval_root": args.rcaeval_root}
            # {root} means every source run of this row, one at a time.
            roots = [os.path.join(args.raw or "", s)
                     for s in r["source_run"].split(";")] or [""]
            outcomes = []
            for root in (roots if "{root}" in cmd else [None]):
                p = dict(paths)
                if root is not None:
                    p["root"] = root
                full = substitute(cmd, p)
                try:
                    proc = subprocess.run(full, shell=True, capture_output=True,
                                          text=True, timeout=args.timeout)
                    outcomes.append(f"exit {proc.returncode}"
                                    + ("" if proc.returncode == 0
                                       else ": " + (proc.stderr.strip()
                                                    .splitlines() or [""])[-1][:160]))
                except subprocess.TimeoutExpired:
                    outcomes.append(f"timeout after {args.timeout}s")
            rec["outcome"] = "; ".join(outcomes)
            if any(not o.startswith("exit 0") for o in outcomes):
                if r["publicly_reproducible"] == "yes":
                    failures.append((rid, rec["outcome"]))
                rec["validation_status"] = "fail"
            else:
                rec["validation_status"] = "pass"
        report.append(rec)
        print(f"  {rid:28s} {rec['level']}  {rec.get('validation_status', r['validation_status']):10s} "
              f"{rec['outcome']}")

    out = {"register": REGISTER, "rows": report,
           "package": args.package, "raw": args.raw,
           "schema_problems": problems,
           "failures": [f[0] for f in failures]}
    with open("data_availability_report.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(f"\nwrote data_availability_report.json")

    if problems:
        print(f"\nFAILED: {len(problems)} schema problems", file=sys.stderr)
        return 1
    if failures:
        print(f"\nFAILED: {len(failures)} results claim public reproducibility "
              f"and did not recompute:", file=sys.stderr)
        for rid, why in failures:
            print(f"  {rid}: {why}", file=sys.stderr)
        print("  Either fix the command and the archive, or lower the claim. Do "
              "not write up\n  a level the register cannot verify.", file=sys.stderr)
        return 1
    print("\nPASS: every row claiming public reproducibility recomputed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
