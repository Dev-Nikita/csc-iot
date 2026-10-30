# Second stand: resolvability on a published benchmark

The manuscript's weakest point was external validity: every number came from one
emulation testbed of nine containers on one host. This directory carries the
probe that answers it, and it required no new testbed.

## What was done

`RCAEval` (Pham, Ha and Zhang; ASE'24/WWW'25/FSE'26) publishes 735 microservice
fault cases across Online Boutique, Sock Shop and Train Ticket, **with explicit
repetitions of each fault-service configuration**. Suite RE1 is metrics-only,
124 MB, 375 cases, five repetitions per configuration. That repetition structure
is exactly what the dispersion band needs, so the question "how much of a
reported difference between methods survives run-to-run variation" can be asked
of somebody else's benchmark without running anything.

`batch.py` scores every RE1 case with three of RCAEval's own shipped
metrics-only methods -- BARO, N-Sigma and epsilon-Diagnosis -- recording the
rank position of the true root-cause service. `analyse.py` then applies the
manuscript's own band definition, carried over unchanged: the band is the pooled
Q0.95 of within-configuration pairwise |differences| of the same method across
repetitions of the same fault, and a contrast between two methods at a
configuration is resolvable only if it exceeds that band.

Reproduce:

    pip install RCAEval pyarrow huggingface_hub
    python -c "from huggingface_hub import snapshot_download; \
      snapshot_download('phamquiluan/RCAEval', repo_type='dataset', \
      allow_patterns=['re1*','cases.parquet'], local_dir='re1')"
    python batch.py && python analyse.py

Scoring all 375 cases took about 17 minutes on one core.

## What it found

**Repetitions of the same method on the same fault disagree often.**
Hit@1 flips between two repetitions in **20.6%** of repetition pairs and hit@5
in **12.3%**. On reciprocal rank, 26.8% of repetition pairs differ by more than
0.25 and the Q0.95 band is **0.667**.

**Three quarters of per-configuration method comparisons do not survive it.**
Of 225 contrasts (75 configurations x 3 method pairs), **170 (75.6%)** are
smaller than the band. By method pair:

| pair | resolvable |
|---|---|
| BARO vs N-Sigma | **0 of 75** |
| BARO vs epsilon-Diagnosis | 13 of 75 |
| N-Sigma vs epsilon-Diagnosis | 42 of 75 |

The first row is the sharpest number here: two competitive published methods,
75 configurations, five repetitions each, and **not one configuration** where
their difference exceeds repetition noise. The third row resolves often only
because epsilon-Diagnosis scores near zero throughout.

**But the aggregate leaderboard is stable, and that must be said.** Bootstrapping
whole repetitions within each configuration, 2000 times, the ordering
N-Sigma > BARO > epsilon-Diagnosis holds in **100%** of resamples on all three
systems. The claim that published rankings are unresolvable would be false.

## What this licenses the paper to claim, and what it does not

It licenses: the pathology is not a property of our testbed. On an independent,
published, widely used benchmark, the per-configuration comparisons -- which is
where fault-type-specific claims such as "our method is best on network faults"
are made -- are mostly indistinguishable from repetition noise, and two real
methods are never distinguishable at that granularity.

It does not license: any claim about aggregate leaderboards, which survive here
intact. And it is a weaker instrument than the manuscript's own: RCAEval
repetitions are independent runs, not branches forked from a verified-equivalent
state, so the dispersion measured here conflates run-to-run variation with
initial-state variation. That the number is *worse* under the weaker instrument
is consistent, not contradictory, and the manuscript should say so rather than
claim the two measurements are the same quantity.

## Honest limits of this probe

- Three metrics-only methods, not the full set; `ht` needs `pyrca`, which is not
  installed. More methods would strengthen it and are cheap to add.
- Reciprocal rank is our choice of continuous score. The benchmark's own Avg@5
  is binary per case, and a Q0.95 band on a Bernoulli difference saturates at
  1.0, so nothing is resolvable by construction under it -- which is itself
  worth reporting: the benchmark's headline metric cannot support a
  per-configuration comparison at all.
- RE1 only. RE2 and RE3 have three repetitions each and would extend this.
