import csv
import json

import pandas as pd

from src import logger


def _record(**overrides) -> dict:
    record = {
        "timestamp": "2026-07-03T00:00:00+00:00",
        "test_id": "TC01",
        "baseline": "full",
        "device": "SW1",
        "intent": "Create VLAN 10 named ACCOUNTING",
        "standardized_prompt": "Role:\nGenerate Cisco IOS CLI.",
        "anonymized_prompt": "Device: DEVICE_A\nVLAN Name: VLAN_NAME_001",
        "llm_output": "conf t\nvlan 10\nname VLAN_NAME_001\nend",
        "de_anonymized_cli": "conf t\nvlan 10\nname ACCOUNTING\nend",
        "syntax_pass": True,
        "security_pass": True,
        "policy_pass": True,
        "guardrail_decision": "Accept",
        "guardrail_reasons": [],
        "final_decision": "Accept",
        "latency_ms": 12.345,
        "error_message": None,
        "eve_connected": False,
        "eve_applied": False,
        "eve_output": "",
        "eve_error": None,
        "eve_validation_pass": None,
        "eve_validation_details": {},
        "show_outputs": {},
    }
    record.update(overrides)
    return record


def test_append_result_creates_csv_and_jsonl(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    record = _record()

    logger.append_result(record, csv_path=csv_path, jsonl_path=jsonl_path)

    assert csv_path.exists()
    assert jsonl_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))

    assert rows[0] == logger.RESULT_FIELDS
    assert len(rows) == 2

    jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 1
    assert json.loads(jsonl_lines[0])["test_id"] == "TC01"


def test_append_result_handles_multiline_cli(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    cli = "conf t\nvlan 10\nname ACCOUNTING, FINANCE\nend"

    logger.append_result(
        _record(llm_output=cli, de_anonymized_cli=cli),
        csv_path=csv_path,
        jsonl_path=jsonl_path,
    )

    results = pd.read_csv(csv_path)

    assert len(results) == 1
    assert results.loc[0, "llm_output"] == cli
    assert results.loc[0, "de_anonymized_cli"] == cli


def test_append_result_handles_dict_and_list_fields(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    reasons = ["Dangerous command detected: reload", "contains comma, safely"]
    validation_details = {
        "vlan_id_found": True,
        "note": "line one\nline two, with comma",
    }
    show_outputs = {
        "show vlan brief": "10 ACCOUNTING active\n20 SALES active",
    }

    logger.append_result(
        _record(
            guardrail_reasons=reasons,
            eve_validation_details=validation_details,
            show_outputs=show_outputs,
        ),
        csv_path=csv_path,
        jsonl_path=jsonl_path,
    )

    results = pd.read_csv(csv_path)

    assert results.loc[0, "guardrail_reasons"] == json.dumps(
        reasons,
        ensure_ascii=False,
    )
    assert results.loc[0, "eve_validation_details"] == json.dumps(
        validation_details,
        ensure_ascii=False,
    )
    assert results.loc[0, "show_outputs"] == json.dumps(
        show_outputs,
        ensure_ascii=False,
    )


def test_results_csv_can_be_read_by_pandas(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"

    logger.append_result(
        _record(
            test_id="TC01",
            llm_output="conf t\nvlan 10\nname ACCOUNTING, FINANCE\nend",
        ),
        csv_path=csv_path,
        jsonl_path=jsonl_path,
    )
    logger.append_result(
        _record(
            test_id="TC02",
            guardrail_reasons=["Out-of-scope command detected: router ospf 1"],
            eve_validation_details={"command": "show vlan brief"},
            show_outputs={"show vlan brief": "10 ACCOUNTING active"},
        ),
        csv_path=csv_path,
        jsonl_path=jsonl_path,
    )

    results = pd.read_csv(csv_path)
    jsonl_lines = jsonl_path.read_text(encoding="utf-8").splitlines()

    assert list(results.columns) == logger.RESULT_FIELDS
    assert results["test_id"].to_list() == ["TC01", "TC02"]
    assert len(jsonl_lines) == 2
    assert all(json.loads(line) for line in jsonl_lines)


def test_append_result_migrates_old_csv_header(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    jsonl_path = tmp_path / "results.jsonl"
    old_fields = logger.RESULT_FIELDS[:17]
    old_row = {field: "" for field in old_fields}
    old_row.update(
        {
            "timestamp": "2026-07-03T00:00:00+00:00",
            "test_id": "OLD01",
            "baseline": "raw",
            "final_decision": "Generated",
        }
    )

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=old_fields)
        writer.writeheader()
        writer.writerow(old_row)

    logger.append_result(
        _record(
            test_id="TC02",
            eve_validation_details={"vlan_id_found": True},
            show_outputs={"show vlan brief": "10 ACCOUNTING active"},
        ),
        csv_path=csv_path,
        jsonl_path=jsonl_path,
    )

    results = pd.read_csv(csv_path)

    assert list(results.columns) == logger.RESULT_FIELDS
    assert results["test_id"].to_list() == ["OLD01", "TC02"]
    assert results.loc[1, "eve_validation_details"] == json.dumps(
        {"vlan_id_found": True},
        ensure_ascii=False,
    )
