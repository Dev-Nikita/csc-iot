#!/usr/bin/env python3
"""Build-time guard against terminology that a superseded methodology left behind.

CANONICAL COPY: this file lives here and nowhere else. It has twice been
clobbered by a stale copy pushed from a scratch build directory, each time
silently dropping the EXEMPT refinements and turning legitimate definitions into
false positives. If you find yourself editing a second copy, delete it.

Every entry here was a real stale fragment found in a compiled draft after the
prose around it had already been rewritten. Prose gets edited; the sentence two
paragraphs down does not. This fails the build instead.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# pattern -> why it is banned. A line is exempt if it also matches EXEMPT.
BANNED = {
    r"counterfactual ground truth": "v1 overclaim; use 'replay-based empirical reference outcomes'",
    r"R_\{?\\?mathrm\{safe\}\}|R_safe": "v1 hand-set threshold; the gate uses the CRC-calibrated tau_hat",
    r"R\^\{\+\}": "v1 per-action conformal upper bound; removed as invalid",
    r"adaptive variant restores": "v2.1 froze tau_hat; there is no online recalibration",
    r"randomis(e|ing) the action at a subset": "v2.1 retired the behaviour policy for exhaustive training branches",
    r"prop:cov|Proposition~\\ref": "Proposition 1 was removed",
    r"calibrated (interventional|uncertainty) (risk )?(bound|gating)": "CRC calibrates a set-level loss, not per-action bounds",
    r"ID \(test\)\s*\\\\": "F6 belongs to scenario shift, not the ID split",
    r"behaviour[- ]policy|behaviour_policy|pi_b\(": "v2.1 retired the behaviour policy for exhaustive training branches",
    r"\bdistinguishable\b": "reserve for |J(a_i)-J(a_j)| > eta_J after D0; before that say 'action-dependent divergence'",
}
# Negations and explanatory passages are allowed to name what was removed.
# Negations, explanatory passages, and the one legitimate use of
# "distinguishable" -- its definition relative to eta_J -- are allowed.
EXEMPT = re.compile(
    r"\bnot\b|\bno longer\b|removed|superseded|banned|retired|v1 |%"
    r"|eta_J|\\eta_J|\u03b7_J",          # a definition may name the band it defines
    re.IGNORECASE,
)

# The manuscript is not the only place a superseded definition can survive.
# check_stale.py originally scanned three .tex files; the stale F6 split and the
# retired behaviour policy had by then already spread into the spec, the
# protocol and the backlog, where nothing was checking.
TARGETS = [
    "main.tex", "table_scenarios.tex", "table_related.tex",
    "../RESEARCH_SPEC.md", "../EXPERIMENT_PROTOCOL.md", "../BACKLOG.md",
    "../README.md", "../METHODOLOGY_FREEZE_V2_1.md", "../ARCHITECTURE.md",
]


def main() -> int:
    problems = []
    for name in TARGETS:
        path = ROOT / name
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines, 1):
            # A banned phrase may legitimately straddle a line break inside a
            # sentence that negates it, so the exemption looks at the previous
            # line too.
            context = (lines[i - 2] if i >= 2 else "") + " " + line
            for pat, why in BANNED.items():
                if re.search(pat, line) and not EXEMPT.search(context):
                    problems.append(f"{name}:{i}: {why}\n    {line.strip()[:100]}")
    if problems:
        print("STALE TERMINOLOGY FOUND", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1
    print(f"terminology check passed ({len(TARGETS)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
