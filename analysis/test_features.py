"""The feature set may not depend on the fault schedule. Tested, not intended.

Run: pytest analysis/test_features.py
"""
import json
import os
import shutil

import pytest

import features

BRANCH = os.path.join(os.path.dirname(__file__), "..", "data", "raw",
                      "b7e0de9844d79602", "m2prime-903", "a12-NO_OP-r01")
have_branch = os.path.exists(os.path.join(BRANCH, "anchor.json"))
needs_branch = pytest.mark.skipif(not have_branch,
                                  reason="recorded branch not present locally")


def test_a_forbidden_name_is_refused_even_if_renamed():
    with pytest.raises(AssertionError, match="fault_onset"):
        features._assert_clean({"fault_onset": 12.0})
    with pytest.raises(AssertionError, match="substring"):
        features._assert_clean({"epochs_since_fault_start": 3.0})
    with pytest.raises(AssertionError, match="substring"):
        features._assert_clean({"edge00_degraded_capacity": 60.0})
    features._assert_clean({"epoch": 12.0, "edge00_inbox_len": 140.0})


def test_the_forbidden_set_names_the_schedule_and_the_scenario_identity():
    for name in ("fault_onset", "fault_severity", "fault_type", "scenario_id",
                 "seed", "degrade_at_epoch", "degraded_serve", "regime"):
        assert name in features.FORBIDDEN


@needs_branch
def test_extraction_reads_the_anchor_and_not_the_outcome(tmp_path):
    """The outcome is the future. A feature that needs it is target leakage."""
    d = tmp_path / "branch"
    d.mkdir()
    shutil.copy(os.path.join(BRANCH, "anchor.json"), d / "anchor.json")
    assert not (d / "outcome.json").exists()
    f = features.extract(str(d))
    assert f["epoch"] > 0
    assert len(f) > 30


@needs_branch
def test_features_are_invariant_to_the_recorded_fault_schedule(tmp_path):
    """The strongest form of the schema test.

    The node reports its degradation configuration in the structural state, so
    the schedule is physically present in the file the extractor opens. Changing
    it must change nothing, because nothing reads it.
    """
    d = tmp_path / "branch"
    d.mkdir()
    src = os.path.join(BRANCH, "anchor.json")
    before = features.extract(os.path.dirname(src))

    doc = json.load(open(src))
    cap = doc["state"]["edge_capacity"]
    cap["edge00/degrade_at_epoch"] = 999
    cap["edge00/degraded_serve"] = 1
    doc["state"]["fault_phase"] = "epoch=999"
    json.dump(doc, open(d / "anchor.json", "w"))

    after = features.extract(str(d))
    assert before == after


@needs_branch
def test_the_time_only_baseline_is_a_strict_subset():
    f = features.extract(BRANCH)
    assert set(features.TIME_ONLY) < set(f)
    assert features.TIME_ONLY == ("epoch",)
