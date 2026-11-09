"""The register must refuse to describe a level its own flags deny."""
import csv
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_data_availability as ada


def row(**kw):
    base = {c: "" for c in ada.REQUIRED}
    base.update({"claim_id": "C1", "result_id": "r", "paper_location": "tab:x",
                 "source_run": "m", "derived_file": "f.csv",
                 "recompute_command": "true", "level": "A",
                 "analysis_host_required": "no",
                 "publicly_reproducible": "yes",
                 "claim_criticality": "supporting",
                 "validation_status": "unverified", "limitations": ""})
    base.update(kw)
    return base


def test_a_clean_row_has_no_problems():
    assert ada.check_schema([row()]) == []


def test_level_a_cannot_need_the_analysis_host():
    p = ada.check_schema([row(analysis_host_required="yes",
                              publicly_reproducible="partial")])
    assert any("level A and also needs the analysis host" in x for x in p)


def test_level_c_cannot_be_publicly_reproducible():
    p = ada.check_schema([row(level="C", publicly_reproducible="yes")])
    assert any("level C and public" in x for x in p)


def test_needing_the_host_contradicts_public_reproducibility():
    p = ada.check_schema([row(level="B", analysis_host_required="yes",
                              publicly_reproducible="yes")])
    assert any("needs the analysis host and claims public" in x for x in p)


def test_a_non_reproducible_row_must_name_what_cannot_be_checked():
    p = ada.check_schema([row(level="C", publicly_reproducible="no",
                              analysis_host_required="yes", limitations="")])
    assert any("names no limitation" in x for x in p)
    assert ada.check_schema([row(level="C", publicly_reproducible="no",
                                 analysis_host_required="yes",
                                 limitations="L-REPRO-001")]) == []


def test_a_row_without_a_command_cannot_claim_pass():
    p = ada.check_schema([row(recompute_command="TBD",
                              validation_status="pass")])
    assert any("no command and claims pass" in x for x in p)


def test_duplicate_result_ids_are_caught():
    p = ada.check_schema([row(result_id="x"), row(result_id="x")])
    assert any("duplicate result_id" in x for x in p)


def test_the_checked_in_register_passes_its_own_schema():
    rows = ada.load(str(ROOT / "data_availability.csv"))
    assert ada.check_schema(rows) == []
    assert len(rows) >= 20


def test_every_limitation_named_in_the_register_exists():
    text = (ROOT / "LIMITATIONS.md").read_text()
    for r in ada.load(str(ROOT / "data_availability.csv")):
        for lim in r["limitations"].split(";"):
            lim = lim.strip()
            if lim.startswith("L-"):
                assert f"## {lim}" in text, f"{lim} is cited but not registered"


def test_the_schema_check_runs_as_a_command():
    out = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / "audit_data_availability.py"),
         "--schema-only"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "schema consistent" in out.stdout


def test_a_central_claim_cannot_rest_on_a_non_reproducible_result():
    """Nineteen checkable side tables do not pay for one unverifiable central one."""
    p = ada.check_schema([row(claim_criticality="central", level="C",
                              publicly_reproducible="no",
                              analysis_host_required="yes",
                              limitations="L-REPRO-001")])
    assert any("CENTRAL claim and is not publicly reproducible" in x for x in p)


def test_supporting_results_may_be_non_reproducible_if_declared():
    assert ada.check_schema([row(claim_criticality="supporting", level="C",
                                 publicly_reproducible="no",
                                 analysis_host_required="yes",
                                 limitations="L-REPRO-001")]) == []


def test_criticality_must_be_one_of_the_three_values():
    p = ada.check_schema([row(claim_criticality="important")])
    assert any("claim_criticality" in x for x in p)


def test_the_checked_in_register_declares_criticality_everywhere():
    rows = ada.load(str(ROOT / "data_availability.csv"))
    assert all(r["claim_criticality"] in ada.CRITICALITY for r in rows)
    central = [r for r in rows if r["claim_criticality"] == "central"]
    assert central, "no central results declared"
    assert all(r["publicly_reproducible"] != "no" for r in central)
