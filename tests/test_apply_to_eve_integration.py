from pathlib import Path

import pandas as pd

from src import main as main_module
from src.eve_validator import EveValidationResult
from src.netmiko_runner import NetmikoResult


def _write_testcases(tmp_path: Path, rows: list[dict]) -> Path:
    testcases_path = tmp_path / "testcases.csv"
    pd.DataFrame(rows).to_csv(testcases_path, index=False)
    return testcases_path


def _valid_vlan_row() -> dict:
    return {
        "test_id": "TC01",
        "category": "VLAN",
        "device": "SW1",
        "intent": "Create VLAN 10 named ACCOUNTING",
        "vlan_id": "10",
        "vlan_name": "ACCOUNTING",
        "interface": "",
        "expected_task_type": "vlan_create",
        "expected_result": "accept",
    }


def _risky_row() -> dict:
    row = _valid_vlan_row()
    row.update(
        {
            "test_id": "TC07",
            "category": "RISKY",
            "intent": "Create VLAN 10 then reload the switch",
            "expected_task_type": "risky",
            "expected_result": "reject",
        }
    )
    return row


def _run_with_temp_outputs(
    tmp_path: Path,
    baseline: str,
    testcases_path: Path,
    apply_to_eve: bool,
) -> tuple[list[dict], Path]:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    mapping_path = tmp_path / "anonymization_map.json"

    records = main_module.run_experiment(
        baseline=baseline,
        testcases_path=testcases_path,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        mapping_path=mapping_path,
        apply_to_eve=apply_to_eve,
    )
    return records, csv_path


def test_raw_baseline_never_applies_even_with_flag(monkeypatch, tmp_path) -> None:
    testcases_path = _write_testcases(tmp_path, [_valid_vlan_row()])

    def fail_apply(*_args, **_kwargs):
        raise AssertionError("Raw baseline must not call Netmiko")

    monkeypatch.setattr(main_module, "apply_config_if_safe", fail_apply)

    records, _ = _run_with_temp_outputs(
        tmp_path,
        baseline="raw",
        testcases_path=testcases_path,
        apply_to_eve=True,
    )

    assert records[0]["eve_connected"] is False
    assert records[0]["eve_applied"] is False


def test_guardrail_reject_never_applies(monkeypatch, tmp_path) -> None:
    testcases_path = _write_testcases(tmp_path, [_risky_row()])

    def fail_apply(*_args, **_kwargs):
        raise AssertionError("Rejected commands must not call Netmiko")

    monkeypatch.setattr(main_module, "apply_config_if_safe", fail_apply)

    records, _ = _run_with_temp_outputs(
        tmp_path,
        baseline="guardrail",
        testcases_path=testcases_path,
        apply_to_eve=True,
    )

    assert records[0]["guardrail_decision"] == "Reject"
    assert records[0]["eve_applied"] is False


def test_full_accept_applies_when_flag_enabled(monkeypatch, tmp_path) -> None:
    testcases_path = _write_testcases(tmp_path, [_valid_vlan_row()])
    calls = {"apply": 0}

    def fake_apply(*_args, **_kwargs):
        calls["apply"] += 1
        return NetmikoResult(
            connected=True,
            applied=True,
            output="configuration applied",
        )

    def fake_validate(*_args, **_kwargs):
        return EveValidationResult(
            eve_validation_pass=True,
            validation_details={"vlan_id_found": True},
            show_outputs={"show vlan brief": "10   ACCOUNTING   active"},
        )

    monkeypatch.setattr(main_module, "apply_config_if_safe", fake_apply)
    monkeypatch.setattr(main_module, "validate_task_in_eve", fake_validate)

    records, _ = _run_with_temp_outputs(
        tmp_path,
        baseline="full",
        testcases_path=testcases_path,
        apply_to_eve=True,
    )

    assert calls["apply"] == 1
    assert records[0]["eve_applied"] is True
    assert records[0]["eve_validation_pass"] is True


def test_full_accept_does_not_apply_without_flag(monkeypatch, tmp_path) -> None:
    testcases_path = _write_testcases(tmp_path, [_valid_vlan_row()])

    def fail_apply(*_args, **_kwargs):
        raise AssertionError("Netmiko should not be called without --apply-to-eve")

    monkeypatch.setattr(main_module, "apply_config_if_safe", fail_apply)

    records, _ = _run_with_temp_outputs(
        tmp_path,
        baseline="full",
        testcases_path=testcases_path,
        apply_to_eve=False,
    )

    assert records[0]["guardrail_decision"] == "Accept"
    assert records[0]["eve_applied"] is False


def test_apply_error_is_logged_without_crash(monkeypatch, tmp_path) -> None:
    testcases_path = _write_testcases(tmp_path, [_valid_vlan_row()])

    def fake_apply(*_args, **_kwargs):
        return NetmikoResult(
            connected=True,
            applied=False,
            output="",
            error="SSH connection failed",
        )

    def fail_validate(*_args, **_kwargs):
        raise AssertionError("Validation should not run when apply fails")

    monkeypatch.setattr(main_module, "apply_config_if_safe", fake_apply)
    monkeypatch.setattr(main_module, "validate_task_in_eve", fail_validate)

    records, csv_path = _run_with_temp_outputs(
        tmp_path,
        baseline="full",
        testcases_path=testcases_path,
        apply_to_eve=True,
    )
    results = pd.read_csv(csv_path)

    assert records[0]["final_decision"] == "Accept"
    assert records[0]["eve_applied"] is False
    assert records[0]["eve_error"] == "SSH connection failed"
    assert results.loc[0, "eve_error"] == "SSH connection failed"
