import json, os, sys, time, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from RCAEval.e2e import baro, nsigma, e_diagnosis

METHODS = {"baro": baro, "nsigma": nsigma, "e_diagnosis": e_diagnosis}
ROOT = "/tmp/claude-0/re1"
OUT = "/tmp/claude-0/probe/results.jsonl"

cases = pd.read_parquet(f"{ROOT}/cases.parquet")
cases = cases[cases.suite == "RE1"]

done = set()
if os.path.exists(OUT):
    for line in open(OUT):
        try: done.add(json.loads(line)["case"])
        except Exception: pass

t0 = time.time()
with open(OUT, "a") as fh:
    for i, row in enumerate(cases.itertuples(), 1):
        if row.case in done: continue
        d = f"{ROOT}/{row.case}"
        try:
            data = pd.read_parquet(f"{d}/metrics.parquet")
            t = int(open(f"{d}/inject_time.txt").read().strip())
        except Exception as e:
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
print("DONE", time.time()-t0, flush=True)
