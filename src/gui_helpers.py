from src import llm_client
from src.anonymizer import (
    DEVICE_NAMES,
    INTERFACE_PATTERN,
    IP_PATTERN,
    SUBNET_PATTERN,
    VLAN_NAMES,
    _replace_known_values,
    _replace_pattern,
)
from src.de_anonymizer import deanonymize_text
from src.guardrail import validate_cli
from src.prompt_builder import TestCase, build_prompt


def _optional_text(value: object) -> str | None:
    """Normalize blank optional GUI input to None."""
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None


def _normalize_vlan_id(value: str | int | None) -> int | str | None:
    """Return an int VLAN ID when possible, otherwise a cleaned value."""
    cleaned = _optional_text(value)
    if cleaned is None:
        return None

    try:
        return int(cleaned)
    except ValueError:
        return cleaned


def _category_for_task(expected_task_type: str) -> str:
    """Map demo task types to the existing testcase category field."""
    if expected_task_type == "risky":
        return "RISKY"
    if expected_task_type.startswith("stp"):
        return "STP"
    return "VLAN"


def _anonymize_prompt_in_memory(prompt: str) -> tuple[str, dict]:
    """Anonymize prompt text without writing the mapping to disk."""
    mapping: dict = {}
    anonymized = prompt
    anonymized = _replace_pattern(anonymized, SUBNET_PATTERN, mapping, "SUBNET")
    anonymized = _replace_pattern(anonymized, IP_PATTERN, mapping, "IP")
    anonymized = _replace_pattern(anonymized, INTERFACE_PATTERN, mapping, "INTERFACE")
    anonymized = _replace_known_values(anonymized, DEVICE_NAMES, mapping, "DEVICE")
    anonymized = _replace_known_values(anonymized, VLAN_NAMES, mapping, "VLAN_NAME")
    return anonymized, mapping


def build_demo_test_case(
    test_id: str,
    device: str,
    intent: str,
    vlan_id: str | int | None,
    vlan_name: str | None,
    interface: str | None,
    expected_task_type: str,
) -> TestCase:
    """Build a prompt-builder-compatible TestCase from GUI fields."""
    cleaned_task_type = str(expected_task_type).strip()

    return TestCase(
        test_id=str(test_id).strip(),
        category=_category_for_task(cleaned_task_type),
        device=str(device).strip(),
        intent=str(intent).strip(),
        vlan_id=_normalize_vlan_id(vlan_id),
        vlan_name=_optional_text(vlan_name),
        interface=_optional_text(interface),
        expected_task_type=cleaned_task_type,
        expected_result="reject" if cleaned_task_type == "risky" else "accept",
    )


def run_mock_pipeline_for_gui(test_case: TestCase, settings: dict, topology: dict) -> dict:
    """Run the secure demo pipeline locally with the mock LLM only."""
    standardized_prompt = build_prompt(test_case)
    anonymized_prompt, mapping = _anonymize_prompt_in_memory(standardized_prompt)
    llm_output = llm_client.generate_cli(
        anonymized_prompt,
        test_case,
        mode="mock",
        settings=settings,
    )
    de_anonymized_cli = deanonymize_text(llm_output, mapping)
    guardrail_result = validate_cli(de_anonymized_cli, topology, settings)

    return {
        "test_id": test_case.test_id,
        "device": test_case.device,
        "intent": test_case.intent,
        "expected_task_type": test_case.expected_task_type,
        "standardized_prompt": standardized_prompt,
        "anonymized_prompt": anonymized_prompt,
        "llm_output": llm_output,
        "de_anonymized_cli": de_anonymized_cli,
        "syntax_pass": guardrail_result.syntax_pass,
        "security_pass": guardrail_result.security_pass,
        "policy_pass": guardrail_result.policy_pass,
        "guardrail_decision": guardrail_result.decision,
        "guardrail_reasons": guardrail_result.reasons,
        "final_decision": guardrail_result.decision,
    }
