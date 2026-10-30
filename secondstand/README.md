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

## Correction, 2026-10-30

The first version of this probe used one criterion: the difference of two
methods' **means** over a configuration's five repetitions, compared against a
band built from differences between **single** repetitions. Those are different
scales. A mean of five is roughly four times less dispersed than one
observation, so the criterion was far too conservative. It produced "BARO vs
N-Sigma resolvable in 0 of 75 configurations", which was briefly presented as the
sharpest number here. An independent review identified the mismatch; it was
reproduced and confirmed before anything was changed. `analyse.py` is superseded
by `analyse2.py`; the old figures are kept in `RESULTS.md` so the earlier claim
can be traced, and must not be cited.

## What it found

**Repetitions of the same method on the same fault disagree often.** Hit@1 flips
between two repetitions in **20.6%** of repetition pairs, hit@5 in **12.3%**. On
reciprocal rank, 26.8% of repetition pairs differ by more than 0.25 and the
Q0.95 band is **0.667**.

**(A) One run of each method cannot separate them.** Comparing two methods as
single observations on the same case -- the regime the manuscript's own design is
in, one branch per action per anchor -- only **277 of 1125** contrasts exceed the
band, and **14 of 375** for BARO against N-Sigma.

**(B) Five repetitions mostly can.** Keeping the repetitions and testing the
paired difference of means by bootstrap, **188 of 225** per-configuration
contrasts resolve, including **43 of 75** for BARO against N-Sigma.

**(C) Over the whole suite every pair separates.** Hierarchical bootstrap over
configurations and repetitions: BARO minus N-Sigma -0.2195, 95% CI
[-0.2626, -0.1766]; the other two pairs likewise. Aggregate orderings are stable
in 100% of 2000 resamples on all three systems.

| pair | (A) one run each | (B) five repetitions |
|---|---|---|
| BARO vs N-Sigma | 14 of 375 | 43 of 75 |
| BARO vs eps-Diagnosis | 80 of 375 | 71 of 75 |
| N-Sigma vs eps-Diagnosis | 183 of 375 | 74 of 75 |

## What this licenses the paper to claim, and what it does not

It licenses: the quantity an evaluation reports from a **single** run of each
candidate is dominated by that evaluation's own dispersion, on an independent
published benchmark as well as on ours, and recovering the comparison took five
repetitions and a paired test. Studies reporting one run per configuration are
reporting dispersion.

It does not license: any claim that these methods are indistinguishable. They are
distinguishable, and criteria B and C show it. Nor any claim about aggregate
leaderboards, which are stable. Nor the pattern for automated recovery in
general: this is one benchmark suite, one family of diagnosis methods, three
methods.

## Honest limits of this probe


- Three metrics-only methods, not the full set; `ht` needs `pyrca`, which is not
  installed. More methods would strengthen it and are cheap to add.
- Reciprocal rank is our choice of continuous score. The benchmark's own Avg@5
  is binary per case, and a Q0.95 band on a Bernoulli difference saturates at
  1.0, so nothing is resolvable by construction under it -- which is itself
  worth reporting: the benchmark's headline metric cannot support a
  per-configuration comparison at all.
- RE1 only. RE2 and RE3 have three repetitions each and would extend this.
