from pathlib import Path

import pandas as pd

from src.main import run_experiment


TESTCASES_PATH = Path("data/testcases.csv")


def _run_baseline(tmp_path: Path, baseline: str) -> tuple[list[dict], Path, Path]:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    mapping_path = tmp_path / "anonymization_map.json"

    records = run_experiment(
        baseline=baseline,
        testcases_path=TESTCASES_PATH,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        mapping_path=mapping_path,
    )
    return records, csv_path, jsonl_path


def test_raw_baseline_command_runs_without_error(tmp_path) -> None:
    records, csv_path, jsonl_path = _run_baseline(tmp_path, "raw")

    assert len(records) == 8
    assert csv_path.exists()
    assert jsonl_path.exists()
    assert all(record["final_decision"] == "Generated" for record in records)


def test_guardrail_baseline_rejects_risky_test_cases(tmp_path) -> None:
    records, _, _ = _run_baseline(tmp_path, "guardrail")
    risky_records = {
        record["test_id"]: record
        for record in records
        if record["test_id"] in {"TC07", "TC08"}
    }

    assert risky_records["TC07"]["final_decision"] == "Reject"
    assert risky_records["TC08"]["final_decision"] == "Reject"


def test_full_baseline_produces_results_csv(tmp_path) -> None:
    _, csv_path, _ = _run_baseline(tmp_path, "full")

    assert csv_path.exists()


def test_results_csv_contains_final_decision_column(tmp_path) -> None:
    _, csv_path, _ = _run_baseline(tmp_path, "full")
    results = pd.read_csv(csv_path)

    assert "final_decision" in results.columns


def test_full_baseline_produces_reject_for_risky_prompts(tmp_path) -> None:
    _, csv_path, _ = _run_baseline(tmp_path, "full")
    results = pd.read_csv(csv_path)
    risky_results = results[results["test_id"].isin(["TC07", "TC08"])]

    assert "Reject" in risky_results["final_decision"].to_list()
