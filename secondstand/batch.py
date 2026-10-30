import argparse, hashlib, json, platform, time, warnings
from importlib.metadata import version
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
from RCAEval.e2e import baro, nsigma, e_diagnosis

METHODS = {"baro": baro, "nsigma": nsigma, "e_diagnosis": e_diagnosis}
DATASET_REVISION = "afeacb11bcc94dadfd1c8f483ee4377b2b8b614e"

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True,
                help="RCAEval snapshot directory containing cases.parquet")
ap.add_argument("--out", default=str(Path(__file__).with_name("results.jsonl")))
ap.add_argument("--dataset-revision", default=DATASET_REVISION,
                help="Hugging Face commit used to download --root")
args = ap.parse_args()
ROOT = Path(args.root)
OUT = Path(args.out)
OUT.parent.mkdir(parents=True, exist_ok=True)

cases = pd.read_parquet(ROOT / "cases.parquet")
cases = cases[cases.suite == "RE1"]
if len(cases) != 375:
    raise SystemExit(f"REFUSED: expected 375 RE1 cases, found {len(cases)}")

provenance = {
    "dataset": "phamquiluan/RCAEval",
    "dataset_revision": args.dataset_revision,
    "cases": int(len(cases)),
    "python": platform.python_version(),
    "packages": {name: version(name) for name in
                 ("RCAEval", "pandas", "pyarrow", "numpy", "scikit-learn",
                  "scipy", "huggingface-hub")},
}

done = set()
if OUT.exists():
    for line in OUT.open():
        try: done.add(json.loads(line)["case"])
        except Exception: pass

t0 = time.time()
failures = []
with OUT.open("a") as fh:
    for i, row in enumerate(cases.itertuples(), 1):
        if row.case in done: continue
        d = ROOT / row.case
        try:
            data = pd.read_parquet(d / "metrics.parquet")
            t = int((d / "inject_time.txt").read_text().strip())
        except Exception as e:
            failures.append(f"{row.case}: input: {type(e).__name__}: {e}")
            continue
        rec = {"case": row.case, "dataset": row.dataset, "system": row.system_name,
               "service": row.root_cause_service, "fault": row.fault,
               "rep": int(row.repetition)}
        for name, fn in METHODS.items():
            try:
                ranks = fn(data, t)["ranks"]
                pos = next((j+1 for j, r in enumerate(ranks)
                            if str(r).split("_")[0] == row.root_cause_service
                            or str(r) == row.root_cause_service), None)
                rec[name] = pos
            except Exception as ex:
                rec[name] = None
                rec[name + "_err"] = f"{type(ex).__name__}"
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        if i % 25 == 0:
            print(f"{i}/{len(cases)}  {time.time()-t0:.0f}s", flush=True)

records = [json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines()
           if line.strip()]
case_ids = [record["case"] for record in records]
if failures or len(case_ids) != 375 or len(set(case_ids)) != 375:
    details = "\n".join(failures[:10])
    raise SystemExit(
        f"REFUSED: incomplete/non-unique output: {len(case_ids)} rows, "
        f"{len(set(case_ids))} unique cases, {len(failures)} input failures\n{details}")
provenance["output_sha256"] = hashlib.sha256(OUT.read_bytes()).hexdigest()
Path(str(OUT) + ".provenance.json").write_text(
    json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("DONE", time.time()-t0, flush=True)
