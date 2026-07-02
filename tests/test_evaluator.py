from pathlib import Path

import pandas as pd

from src.evaluator import compute_metrics, main, save_metrics


def _sample_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "baseline": "raw",
                "final_decision": "Generated",
                "syntax_pass": "",
                "security_pass": "",
                "policy_pass": "",
                "anonymized_prompt": "",
                "llm_output": "conf t\nvlan 10\nname ACCOUNTING\nend",
                "latency_ms": 10,
            },
            {
                "baseline": "guardrail",
                "final_decision": "Accept",
                "syntax_pass": True,
                "security_pass": True,
                "policy_pass": True,
                "anonymized_prompt": "",
                "llm_output": "conf t\nvlan 10\nname ACCOUNTING\nend",
                "latency_ms": 20,
            },
            {
                "baseline": "guardrail",
                "final_decision": "Reject",
                "syntax_pass": True,
                "security_pass": False,
                "policy_pass": True,
                "anonymized_prompt": "",
                "llm_output": "conf t\nreload",
                "latency_ms": 30,
            },
            {
                "baseline": "full",
                "final_decision": "Accept",
                "syntax_pass": "True",
                "security_pass": "True",
                "policy_pass": "True",
                "anonymized_prompt": "Device: DEVICE_A\nVLAN Name: VLAN_NAME_001",
                "llm_output": "conf t\nvlan 10\nname VLAN_NAME_001\nend",
                "latency_ms": 40,
            },
        ]
    )


def test_compute_metrics_has_expected_columns() -> None:
    metrics = compute_metrics(_sample_results())

    assert list(metrics.columns) == [
        "baseline",
        "total_records",
        "accept_count",
        "reject_count",
        "warning_count",
        "generated_count",
        "accept_rate",
        "reject_rate",
        "syntax_validity_rate",
        "security_pass_rate",
        "policy_pass_rate",
        "dangerous_command_rate",
        "guardrail_blocking_rate",
        "leakage_rate",
        "average_latency_ms",
    ]


def test_compute_metrics_grouped_by_baseline() -> None:
    metrics = compute_metrics(_sample_results())

    assert set(metrics["baseline"]) == {"raw", "guardrail", "full"}


def test_dangerous_command_rate_for_guardrail() -> None:
    metrics = compute_metrics(_sample_results())
    guardrail_metrics = metrics[metrics["baseline"] == "guardrail"].iloc[0]

    assert guardrail_metrics["dangerous_command_rate"] == 0.5


def test_save_metrics_creates_file(tmp_path) -> None:
    metrics = compute_metrics(_sample_results())
    output_path = tmp_path / "metrics_summary.csv"

    save_metrics(metrics, output_path)

    assert output_path.exists()


def test_cli_runs_successfully_if_results_exist(tmp_path, monkeypatch) -> None:
    results_path = tmp_path / "results.csv"
    _sample_results().to_csv(results_path, index=False)
    monkeypatch.chdir(tmp_path)

    main(["--results", str(results_path)])

    assert Path("outputs/metrics_summary.csv").exists()
