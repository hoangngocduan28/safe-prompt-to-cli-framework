from pathlib import Path
import argparse
from datetime import datetime, timezone
import time

from src.anonymizer import anonymize_text
from src.config_loader import load_csv, load_yaml
from src.de_anonymizer import deanonymize_text, find_unresolved_tokens
from src.guardrail import validate_cli
from src.llm_client import generate_cli
from src.logger import append_result
from src.prompt_builder import build_prompt, testcase_from_dict, TestCase


def _base_record(test_case: TestCase, baseline: str) -> dict:
    """Create the common result record fields for one test case."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_id": test_case.test_id,
        "baseline": baseline,
        "device": test_case.device,
        "intent": test_case.intent,
        "standardized_prompt": "",
        "anonymized_prompt": "",
        "llm_output": "",
        "de_anonymized_cli": "",
        "syntax_pass": None,
        "security_pass": None,
        "policy_pass": None,
        "guardrail_decision": "",
        "guardrail_reasons": [],
        "final_decision": "",
        "latency_ms": None,
        "error_message": "",
    }


def _store_guardrail_result(record: dict, cli: str, topology: dict, settings: dict) -> None:
    """Run guardrail validation and store its result in the record."""
    result = validate_cli(cli, topology, settings)
    record["syntax_pass"] = result.syntax_pass
    record["security_pass"] = result.security_pass
    record["policy_pass"] = result.policy_pass
    record["guardrail_decision"] = result.decision
    record["guardrail_reasons"] = result.reasons
    record["final_decision"] = result.decision


def _process_test_case(
    test_case: TestCase,
    baseline: str,
    topology: dict,
    settings: dict,
    mapping_path: str | Path,
) -> dict:
    """Run one test case through the selected research baseline."""
    record = _base_record(test_case, baseline)
    start_time = time.perf_counter()

    try:
        prompt = build_prompt(test_case)
        record["standardized_prompt"] = prompt

        if baseline == "raw":
            record["llm_output"] = generate_cli(prompt, test_case)
            record["final_decision"] = "Generated"

        elif baseline == "guardrail":
            record["llm_output"] = generate_cli(prompt, test_case)
            _store_guardrail_result(record, record["llm_output"], topology, settings)

        elif baseline == "full":
            anonymized_prompt, mapping = anonymize_text(prompt, mapping_path)
            record["anonymized_prompt"] = anonymized_prompt
            record["llm_output"] = generate_cli(anonymized_prompt, test_case)
            record["de_anonymized_cli"] = deanonymize_text(record["llm_output"], mapping)

            unresolved_tokens = find_unresolved_tokens(record["de_anonymized_cli"])
            _store_guardrail_result(record, record["de_anonymized_cli"], topology, settings)

            if unresolved_tokens:
                record["final_decision"] = "Reject"
                record["error_message"] = (
                    "Unresolved anonymization tokens: "
                    + ", ".join(unresolved_tokens)
                )

        else:
            raise ValueError(f"Unsupported baseline: {baseline}")

    except Exception as exc:
        record["final_decision"] = "Error"
        record["error_message"] = str(exc)

    record["latency_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
    return record


def run_experiment(
    baseline: str,
    testcases_path: str | Path = "data/testcases.csv",
    csv_path: str | Path = "outputs/results.csv",
    jsonl_path: str | Path = "outputs/results.jsonl",
    mapping_path: str | Path = "data/anonymization_map.json",
) -> list[dict]:
    """Run all test cases for one baseline and append result records."""
    testcases = load_csv(testcases_path)
    topology = load_yaml("config/topology.yaml")
    settings = load_yaml("config/settings.yaml")
    records: list[dict] = []

    for _, row in testcases.iterrows():
        test_case = testcase_from_dict(row.to_dict())
        record = _process_test_case(
            test_case=test_case,
            baseline=baseline,
            topology=topology,
            settings=settings,
            mapping_path=mapping_path,
        )
        append_result(record, csv_path=csv_path, jsonl_path=jsonl_path)
        records.append(record)
        print(
            f"[{record['test_id']}] baseline={baseline} "
            f"decision={record['final_decision']}"
        )

    print(f"Experiment completed. Results saved to {csv_path} and {jsonl_path}")
    return records


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and run the selected experiment baseline."""
    parser = argparse.ArgumentParser(description="Run PROMPT-TO-CLI mock baselines.")
    parser.add_argument(
        "--baseline",
        choices=["raw", "guardrail", "full"],
        required=True,
        help="Experiment baseline to run.",
    )
    parser.add_argument(
        "--testcases",
        default="data/testcases.csv",
        help="Path to the testcase CSV file.",
    )
    args = parser.parse_args(argv)

    run_experiment(baseline=args.baseline, testcases_path=args.testcases)


if __name__ == "__main__":
    main()
