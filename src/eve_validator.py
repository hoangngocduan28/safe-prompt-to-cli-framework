from dataclasses import dataclass

from src.netmiko_runner import run_show_command
from src.prompt_builder import TestCase


@dataclass
class EveValidationResult:
    eve_validation_pass: bool
    validation_details: dict
    show_outputs: dict
    error: str | None = None


def _result_from_show_error(command: str, output: str, error: str) -> EveValidationResult:
    """Build a failed validation result for a show-command error."""
    return EveValidationResult(
        eve_validation_pass=False,
        validation_details={"command": command},
        show_outputs={command: output},
        error=error,
    )


def _run_show(device_name: str, command: str, devices: dict):
    """Run one show command through the Netmiko runner."""
    return run_show_command(device_name, command, devices)


def _validate_vlan_create(test_case: TestCase, devices: dict) -> EveValidationResult:
    """Validate that a VLAN exists in show vlan brief output."""
    command = "show vlan brief"
    show_result = _run_show(test_case.device, command, devices)
    show_outputs = {command: show_result.output}

    if show_result.error:
        return _result_from_show_error(command, show_result.output, show_result.error)

    output = show_result.output
    vlan_found = bool(test_case.vlan_id and test_case.vlan_id in output)
    vlan_name_found = True
    if test_case.vlan_name:
        vlan_name_found = test_case.vlan_name in output

    return EveValidationResult(
        eve_validation_pass=vlan_found and vlan_name_found,
        validation_details={
            "vlan_id_found": vlan_found,
            "vlan_name_found": vlan_name_found,
        },
        show_outputs=show_outputs,
    )


def _validate_vlan_access(test_case: TestCase, devices: dict) -> EveValidationResult:
    """Validate that an interface is configured for the expected access VLAN."""
    command = f"show running-config interface {test_case.interface}"
    show_result = _run_show(test_case.device, command, devices)
    show_outputs = {command: show_result.output}

    if show_result.error:
        return _result_from_show_error(command, show_result.output, show_result.error)

    output = show_result.output.lower()
    access_mode_found = "switchport mode access" in output
    access_vlan_found = f"switchport access vlan {test_case.vlan_id}".lower() in output

    return EveValidationResult(
        eve_validation_pass=access_mode_found and access_vlan_found,
        validation_details={
            "access_mode_found": access_mode_found,
            "access_vlan_found": access_vlan_found,
        },
        show_outputs=show_outputs,
    )


def _validate_stp_root(test_case: TestCase, devices: dict) -> EveValidationResult:
    """Validate STP root status using Cisco IOS show output."""
    command = f"show spanning-tree vlan {test_case.vlan_id}"
    show_result = _run_show(test_case.device, command, devices)
    show_outputs = {command: show_result.output}

    if show_result.error:
        return _result_from_show_error(command, show_result.output, show_result.error)

    output = show_result.output
    root_phrases = ("This bridge is the root", "This bridge is root")
    root_phrase_found = any(phrase in output for phrase in root_phrases)
    stp_output_found = root_phrase_found or "Root ID" in output or "Bridge ID" in output
    details = {
        "root_phrase_found": root_phrase_found,
        "stp_output_found": stp_output_found,
    }

    if stp_output_found and not root_phrase_found:
        details["note"] = "STP output found; root status should be manually verified."

    return EveValidationResult(
        eve_validation_pass=stp_output_found,
        validation_details=details,
        show_outputs=show_outputs,
    )


def validate_task_in_eve(test_case: TestCase, devices: dict) -> EveValidationResult:
    """Validate an applied task against EVE-NG device state."""
    task_type = test_case.expected_task_type

    if task_type == "vlan_create":
        return _validate_vlan_create(test_case, devices)

    if task_type == "vlan_access":
        return _validate_vlan_access(test_case, devices)

    if task_type == "stp_root":
        return _validate_stp_root(test_case, devices)

    if task_type == "risky":
        return EveValidationResult(
            eve_validation_pass=False,
            validation_details={"task_type": task_type},
            show_outputs={},
            error="Risky test case should not be applied to EVE-NG.",
        )

    return EveValidationResult(
        eve_validation_pass=False,
        validation_details={"task_type": task_type},
        show_outputs={},
        error=f"Unsupported task type for EVE-NG validation: {task_type}",
    )
