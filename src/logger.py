from pathlib import Path
import csv
import json


RESULT_FIELDS = [
    "timestamp",
    "test_id",
    "baseline",
    "device",
    "intent",
    "standardized_prompt",
    "anonymized_prompt",
    "llm_output",
    "de_anonymized_cli",
    "syntax_pass",
    "security_pass",
    "policy_pass",
    "guardrail_decision",
    "guardrail_reasons",
    "final_decision",
    "latency_ms",
    "error_message",
]


def _csv_value(value: object) -> object:
    """Convert structured values to CSV-friendly strings."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def append_result(
    record: dict,
    csv_path: str | Path = "outputs/results.csv",
    jsonl_path: str | Path = "outputs/results.jsonl",
) -> None:
    """Append an experiment result to CSV and JSONL output files."""
    csv_file = Path(csv_path)
    jsonl_file = Path(jsonl_path)
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    jsonl_file.parent.mkdir(parents=True, exist_ok=True)

    with jsonl_file.open("a", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, default=str)
        file.write("\n")

    write_header = not csv_file.exists() or csv_file.stat().st_size == 0
    row = {field: _csv_value(record.get(field)) for field in RESULT_FIELDS}

    with csv_file.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
