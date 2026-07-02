import re

from src.prompt_builder import TestCase


def _prompt_value(prompt: str, label: str) -> str | None:
    """Extract a value from the standardized prompt context."""
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(prompt)
    if not match:
        return None

    value = match.group(1).strip()
    return None if value == "N/A" else value


def _value_from_prompt_or_testcase(
    prompt: str,
    label: str,
    fallback: str | None,
) -> str | None:
    """Prefer prompt context values, falling back to the TestCase object."""
    return _prompt_value(prompt, label) or fallback


def _risky_command(intent: str) -> str:
    """Return the risky command requested by the test intent."""
    lowered = intent.lower()
    if "reload" in lowered:
        return "reload"
    if "write erase" in lowered:
        return "write erase"
    if "delete flash" in lowered:
        return "delete flash:"
    return "debug all"


def generate_cli(prompt: str, test_case: TestCase, mode: str = "mock") -> str:
    """Generate Cisco-style CLI using a deterministic mock LLM."""
    if mode != "mock":
        raise NotImplementedError("Only mock LLM mode is implemented.")

    vlan_id = _value_from_prompt_or_testcase(prompt, "VLAN ID", test_case.vlan_id)
    vlan_name = _value_from_prompt_or_testcase(prompt, "VLAN Name", test_case.vlan_name)
    interface = _value_from_prompt_or_testcase(prompt, "Interface", test_case.interface)
    task_type = test_case.expected_task_type

    if task_type == "vlan_create":
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {vlan_name}",
                "end",
            ]
        )

    if task_type == "vlan_access":
        resolved_vlan_name = vlan_name or f"VLAN_{vlan_id}"
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {resolved_vlan_name}",
                f"interface {interface}",
                "switchport mode access",
                f"switchport access vlan {vlan_id}",
                "end",
            ]
        )

    if task_type == "stp_root":
        return "\n".join(
            [
                "conf t",
                f"spanning-tree vlan {vlan_id} root primary",
                "end",
            ]
        )

    if task_type == "risky":
        resolved_vlan_name = vlan_name or f"VLAN_{vlan_id}"
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {resolved_vlan_name}",
                "end",
                _risky_command(test_case.intent),
            ]
        )

    return ""
