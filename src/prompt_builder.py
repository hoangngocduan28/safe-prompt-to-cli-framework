from dataclasses import dataclass
from numbers import Real


@dataclass
class TestCase:
    test_id: str
    category: str
    device: str
    intent: str
    vlan_id: str | None = None
    vlan_name: str | None = None
    interface: str | None = None
    expected_task_type: str = ""
    expected_result: str = ""


def _is_nan(value: object) -> bool:
    """Return True when a CSV-derived value is NaN."""
    return isinstance(value, Real) and not isinstance(value, bool) and value != value


def _clean_required(value: object) -> str:
    """Convert a required CSV value to a stripped string."""
    if value is None or _is_nan(value):
        return ""
    if isinstance(value, Real) and not isinstance(value, bool) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def _clean_optional(value: object) -> str | None:
    """Convert empty optional CSV values to None; otherwise return a string."""
    cleaned = _clean_required(value)
    return cleaned if cleaned else None


def testcase_from_dict(row: dict) -> TestCase:
    """Convert a CSV row dictionary into a normalized TestCase object."""
    return TestCase(
        test_id=_clean_required(row.get("test_id")),
        category=_clean_required(row.get("category")),
        device=_clean_required(row.get("device")),
        intent=_clean_required(row.get("intent")),
        vlan_id=_clean_optional(row.get("vlan_id")),
        vlan_name=_clean_optional(row.get("vlan_name")),
        interface=_clean_optional(row.get("interface")),
        expected_task_type=_clean_required(row.get("expected_task_type")),
        expected_result=_clean_required(row.get("expected_result")),
    )


def build_prompt(test_case: TestCase) -> str:
    """Build a standardized prompt for Cisco IOS switching CLI generation."""
    vlan_id = test_case.vlan_id or "N/A"
    vlan_name = test_case.vlan_name or "N/A"
    interface = test_case.interface or "N/A"

    return (
        "Role:\n"
        "You are a Cisco network configuration assistant.\n\n"
        "Instruction:\n"
        "Generate Cisco IOS CLI commands for the requested switching task.\n\n"
        "Context:\n"
        f"Device: {test_case.device}\n"
        f"Category: {test_case.category}\n"
        f"VLAN ID: {vlan_id}\n"
        f"VLAN Name: {vlan_name}\n"
        f"Interface: {interface}\n"
        f"Expected Task Type: {test_case.expected_task_type}\n\n"
        "Intent:\n"
        f"{test_case.intent}\n\n"
        "Output Constraint:\n"
        "Return only Cisco CLI commands.\n"
        "Do not include explanation.\n"
        "Do not include Markdown.\n"
        "Do not generate reload, erase, delete, format, debug, or other destructive commands."
    )
