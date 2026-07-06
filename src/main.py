from pathlib import Path
import argparse
from datetime import datetime, timezone
import time

from src.anonymizer import anonymize_text
from src.config_loader import load_csv, load_yaml
from src.de_anonymizer import deanonymize_text, find_unresolved_tokens
from src.eve_validator import validate_task_in_eve
from src.guardrail import validate_cli
from src.llm_client import generate_cli
from src import logger
from src.netmiko_runner import apply_config_if_safe
from src.prompt_builder import build_prompt, testcase_from_dict, TestCase


EVE_RESULT_FIELDS = [
    "eve_connected",
    "eve_applied",
    "eve_output",
    "eve_error",
    "eve_validation_pass",
    "eve_validation_details",
    "show_outputs",
]


def _selected_llm_provider(settings: dict, override: str | None = None) -> str:
    """Resolve and validate the active LLM provider."""
    provider = override or settings.get("llm_provider", "mock")
    if provider not in {"mock", "openai"}:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return provider


def _ensure_logger_fields() -> None:
    """Ensure integration fields are written by the existing logger."""
    for field in EVE_RESULT_FIELDS:
        if field not in logger.RESULT_FIELDS:
            logger.RESULT_FIELDS.append(field)


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
        "eve_connected": False,
        "eve_applied": False,
        "eve_output": "",
        "eve_error": "",
        "eve_validation_pass": None,
        "eve_validation_details": {},
        "show_outputs": {},
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


def _maybe_apply_to_eve(
    record: dict,
    test_case: TestCase,
    cli: str,
    apply_to_eve: bool,
    devices: dict,
    settings: dict,
) -> None:
    """Apply accepted CLI to EVE-NG and validate device state when enabled."""
    if not apply_to_eve:
        return
    if record["guardrail_decision"] != "Accept":
        return

    apply_result = apply_config_if_safe(
        device_name=test_case.device,
        cli=cli,
        guardrail_decision=record["guardrail_decision"],
        devices=devices,
        settings=settings,
    )
    record["eve_connected"] = apply_result.connected
    record["eve_applied"] = apply_result.applied
    record["eve_output"] = apply_result.output
    record["eve_error"] = apply_result.error or ""

    if not apply_result.applied:
        return

    validation_result = validate_task_in_eve(test_case, devices)
    record["eve_validation_pass"] = validation_result.eve_validation_pass
    record["eve_validation_details"] = validation_result.validation_details
    record["show_outputs"] = validation_result.show_outputs
    if validation_result.error:
        record["eve_error"] = validation_result.error


def _process_test_case(
    test_case: TestCase,
    baseline: str,
    topology: dict,
    settings: dict,
    devices: dict,
    mapping_path: str | Path,
    apply_to_eve: bool,
    llm_provider: str,
) -> dict:
    """Run one test case through the selected research baseline."""
    record = _base_record(test_case, baseline)
    record["llm_provider"] = llm_provider
    start_time = time.perf_counter()

    try:
        prompt = build_prompt(test_case)
        record["standardized_prompt"] = prompt

        if baseline == "raw":
            record["llm_output"] = generate_cli(
                prompt,
                test_case,
                mode=llm_provider,
                settings=settings,
            )
            record["final_decision"] = "Generated"
            if apply_to_eve:
                print("Raw baseline is not applied to EVE-NG for safety.")

        elif baseline == "guardrail":
            record["llm_output"] = generate_cli(
                prompt,
                test_case,
                mode=llm_provider,
                settings=settings,
            )
            _store_guardrail_result(record, record["llm_output"], topology, settings)
            _maybe_apply_to_eve(
                record=record,
                test_case=test_case,
                cli=record["llm_output"],
                apply_to_eve=apply_to_eve,
                devices=devices,
                settings=settings,
            )

        elif baseline == "full":
            anonymized_prompt, mapping = anonymize_text(prompt, mapping_path)
            record["anonymized_prompt"] = anonymized_prompt
            record["llm_output"] = generate_cli(
                anonymized_prompt,
                test_case,
                mode=llm_provider,
                settings=settings,
            )
            record["de_anonymized_cli"] = deanonymize_text(record["llm_output"], mapping)

            unresolved_tokens = find_unresolved_tokens(record["de_anonymized_cli"])
            _store_guardrail_result(record, record["de_anonymized_cli"], topology, settings)

            if unresolved_tokens:
                record["final_decision"] = "Reject"
                record["error_message"] = (
                    "Unresolved anonymization tokens: "
                    + ", ".join(unresolved_tokens)
                )

            _maybe_apply_to_eve(
                record=record,
                test_case=test_case,
                cli=record["de_anonymized_cli"],
                apply_to_eve=apply_to_eve,
                devices=devices,
                settings=settings,
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
    apply_to_eve: bool = False,
    llm_provider: str | None = None,
) -> list[dict]:
    """Run all test cases for one baseline and append result records."""
    _ensure_logger_fields()
    testcases = load_csv(testcases_path)
    topology = load_yaml("config/topology.yaml")
    settings = load_yaml("config/settings.yaml")
    devices = load_yaml("config/devices.yaml")
    selected_provider = _selected_llm_provider(settings, llm_provider)
    records: list[dict] = []

    for _, row in testcases.iterrows():
        test_case = testcase_from_dict(row.to_dict())
        record = _process_test_case(
            test_case=test_case,
            baseline=baseline,
            topology=topology,
            settings=settings,
            devices=devices,
            mapping_path=mapping_path,
            apply_to_eve=apply_to_eve,
            llm_provider=selected_provider,
        )
        logger.append_result(record, csv_path=csv_path, jsonl_path=jsonl_path)
        records.append(record)
        print(
            f"[{record['test_id']}] baseline={baseline} "
            f"provider={selected_provider} "
            f"decision={record['final_decision']} "
            f"eve_applied={str(record['eve_applied']).lower()} "
            f"eve_validation={record['eve_validation_pass']}"
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
    parser.add_argument(
        "--apply-to-eve",
        action="store_true",
        help="Apply accepted guarded configurations to EVE-NG.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["mock", "openai"],
        default=None,
        help="LLM provider to use. Overrides config/settings.yaml llm_provider.",
    )
    args = parser.parse_args(argv)

    run_experiment(
        baseline=args.baseline,
        testcases_path=args.testcases,
        apply_to_eve=args.apply_to_eve,
        llm_provider=args.llm_provider,
    )


if __name__ == "__main__":
    main()
