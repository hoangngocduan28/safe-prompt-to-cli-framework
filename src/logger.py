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
    "eve_connected",
    "eve_applied",
    "eve_output",
    "eve_error",
    "eve_validation_pass",
    "eve_validation_details",
    "show_outputs",
]


def _csv_value(value: object) -> object:
    """Convert structured values to CSV-friendly strings."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def _write_csv_rows(csv_file: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Write CSV rows with the project's stable quoting settings."""
    with csv_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _normalize_existing_csv_header(csv_file: Path, fieldnames: list[str]) -> None:
    """Rewrite older result CSV files so future appended rows use one header."""
    if not csv_file.exists() or csv_file.stat().st_size == 0:
        return

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, restkey="__extra_fields")
        existing_header = reader.fieldnames or []
        if existing_header == fieldnames:
            return

        rows: list[dict] = []
        missing_fields = fieldnames[len(existing_header):]
        can_map_extra_fields = fieldnames[: len(existing_header)] == existing_header

        for row in reader:
            extra_fields = row.pop("__extra_fields", None) or []
            if can_map_extra_fields:
                for field, value in zip(missing_fields, extra_fields):
                    row[field] = value
            rows.append(row)

    _write_csv_rows(csv_file, rows, fieldnames)


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

    fieldnames = list(RESULT_FIELDS)
    _normalize_existing_csv_header(csv_file, fieldnames)
    write_header = not csv_file.exists() or csv_file.stat().st_size == 0
    row = {field: _csv_value(record.get(field)) for field in fieldnames}

    with csv_file.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
        )
        if write_header:
            writer.writeheader()
        writer.writerow(row)
