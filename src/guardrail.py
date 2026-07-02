from dataclasses import dataclass
import re


@dataclass
class GuardrailResult:
    syntax_pass: bool
    security_pass: bool
    policy_pass: bool
    decision: str
    reasons: list[str]


DANGEROUS_PATTERNS = (
    r"^reload$",
    r"^write\s+erase$",
    r"^erase\s+startup-config$",
    r"^erase\s+nvram:$",
    r"^delete\s+flash:",
    r"^format\s+flash:",
    r"^debug\s+all$",
    r"^no\s+spanning-tree\s+vlan\s+1-4094$",
)

OUT_OF_SCOPE_PATTERNS = (
    r"^router\s+ospf\b",
    r"^router\s+bgp\b",
    r"^ip\s+route\b",
    r"^access-list\b",
    r"^ip\s+nat\b",
    r"^crypto\s+map\b",
    r"^tunnel\s+interface\b",
    r"^interface\s+tunnel\b",
)

INTERFACE_PATTERN = re.compile(r"^interface\s+(GigabitEthernet\d+(?:/\d+)+)$", re.IGNORECASE)
VLAN_LINE_PATTERN = re.compile(r"^vlan\s+(\d+)$", re.IGNORECASE)
SWITCHPORT_ACCESS_PATTERN = re.compile(
    r"^switchport\s+access\s+vlan\s+(\d+)$",
    re.IGNORECASE,
)
STP_ROOT_PATTERN = re.compile(
    r"^spanning-tree\s+vlan\s+(\d+)\s+root\s+primary$",
    re.IGNORECASE,
)
STP_PRIORITY_PATTERN = re.compile(
    r"^spanning-tree\s+vlan\s+(\d+)\s+priority\s+(\d+)$",
    re.IGNORECASE,
)
VLAN_REFERENCE_PATTERN = re.compile(r"\bvlan\s+(\d+)\b", re.IGNORECASE)


def _normalize_lines(cli: str) -> list[str]:
    """Return non-empty stripped CLI lines."""
    return [line.strip() for line in cli.splitlines() if line.strip()]


def _is_wrapper_command(line: str) -> bool:
    """Return True for harmless shell/config wrapper commands."""
    lowered = line.lower()
    return (
        lowered in {"conf t", "configure terminal", "end", "exit"}
        or lowered.startswith("do show ")
    )


def _is_vlan_id_valid(vlan_id: str) -> bool:
    """Return True when a VLAN ID is within Cisco's standard VLAN range."""
    return 1 <= int(vlan_id) <= 4094


def _get_inventory_interfaces(topology: dict) -> set[str]:
    """Return all known interfaces from the topology device inventory."""
    interfaces: set[str] = set()
    for device in topology.get("devices", {}).values():
        interfaces.update(device.get("interfaces", []))
    return interfaces


def _matches_any_pattern(line: str, patterns: tuple[str, ...]) -> bool:
    """Return True when a CLI line matches any regex in the pattern list."""
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)


def _validate_syntax(lines: list[str]) -> tuple[bool, list[str]]:
    """Validate Cisco-style CLI syntax for the VLAN/STP research scope."""
    reasons: list[str] = []

    for line in lines:
        if _is_wrapper_command(line):
            continue

        lowered = line.lower()

        if VLAN_LINE_PATTERN.fullmatch(line):
            vlan_id = VLAN_LINE_PATTERN.fullmatch(line).group(1)
            if not _is_vlan_id_valid(vlan_id):
                reasons.append(f"Invalid VLAN ID: {vlan_id}")
            continue

        if lowered.startswith("vlan "):
            reasons.append(f"Invalid VLAN syntax: {line}")
            continue

        if re.fullmatch(r"name\s+\S.*", line, re.IGNORECASE):
            continue

        if INTERFACE_PATTERN.fullmatch(line):
            continue

        if lowered.startswith("interface "):
            reasons.append(f"Invalid interface syntax: {line}")
            continue

        if re.fullmatch(r"switchport\s+mode\s+access", line, re.IGNORECASE):
            continue

        if SWITCHPORT_ACCESS_PATTERN.fullmatch(line):
            vlan_id = SWITCHPORT_ACCESS_PATTERN.fullmatch(line).group(1)
            if not _is_vlan_id_valid(vlan_id):
                reasons.append(f"Invalid VLAN ID: {vlan_id}")
            continue

        if lowered.startswith("switchport "):
            reasons.append(f"Invalid switchport syntax: {line}")
            continue

        if STP_ROOT_PATTERN.fullmatch(line):
            vlan_id = STP_ROOT_PATTERN.fullmatch(line).group(1)
            if not _is_vlan_id_valid(vlan_id):
                reasons.append(f"Invalid VLAN ID: {vlan_id}")
            continue

        if STP_PRIORITY_PATTERN.fullmatch(line):
            vlan_id = STP_PRIORITY_PATTERN.fullmatch(line).group(1)
            priority = int(STP_PRIORITY_PATTERN.fullmatch(line).group(2))
            if not _is_vlan_id_valid(vlan_id):
                reasons.append(f"Invalid VLAN ID: {vlan_id}")
            if priority < 0 or priority > 61440 or priority % 4096 != 0:
                reasons.append(f"Invalid STP priority: {priority}")
            continue

        if re.fullmatch(r"spanning-tree\s+portfast", line, re.IGNORECASE):
            continue

        if re.fullmatch(r"spanning-tree\s+bpduguard\s+enable", line, re.IGNORECASE):
            continue

        if lowered.startswith("spanning-tree "):
            reasons.append(f"Invalid spanning-tree syntax: {line}")
            continue

        if lowered in {"shutdown", "no shutdown", "write memory"}:
            continue

        if lowered == "copy running-config startup-config":
            continue

        if _matches_any_pattern(line, DANGEROUS_PATTERNS + OUT_OF_SCOPE_PATTERNS):
            continue

        reasons.append(f"Unsupported command syntax: {line}")

    return not reasons, reasons


def _validate_security(lines: list[str]) -> tuple[bool, list[str]]:
    """Reject destructive or dangerous CLI commands."""
    reasons: list[str] = []

    for line in lines:
        if _is_wrapper_command(line):
            continue
        if _matches_any_pattern(line, DANGEROUS_PATTERNS):
            reasons.append(f"Dangerous command detected: {line}")

    return not reasons, reasons


def _validate_policy(lines: list[str], topology: dict, settings: dict) -> tuple[bool, list[str]]:
    """Validate project scope, topology inventory, and local safety settings."""
    reasons: list[str] = []
    known_interfaces = _get_inventory_interfaces(topology)
    allow_shutdown = bool(settings.get("allow_shutdown", False))

    for line in lines:
        if _is_wrapper_command(line):
            continue

        if _matches_any_pattern(line, OUT_OF_SCOPE_PATTERNS):
            reasons.append(f"Out-of-scope command detected: {line}")

        interface_match = INTERFACE_PATTERN.fullmatch(line)
        if interface_match:
            interface_name = interface_match.group(1)
            if interface_name not in known_interfaces:
                reasons.append(f"Interface not found in topology: {interface_name}")

        for vlan_id in VLAN_REFERENCE_PATTERN.findall(line):
            if not _is_vlan_id_valid(vlan_id):
                reasons.append(f"VLAN ID outside allowed range: {vlan_id}")

        if line.lower() == "shutdown" and not allow_shutdown:
            reasons.append("Shutdown command is not allowed by settings")

    return not reasons, reasons


def validate_cli(cli: str, topology: dict, settings: dict) -> GuardrailResult:
    """Validate generated Cisco CLI with syntax, security, and policy checks."""
    lines = _normalize_lines(cli)

    syntax_pass, syntax_reasons = _validate_syntax(lines)
    security_pass, security_reasons = _validate_security(lines)
    policy_pass, policy_reasons = _validate_policy(lines, topology, settings)
    reasons = syntax_reasons + security_reasons + policy_reasons

    if not syntax_pass or not security_pass or not policy_pass:
        decision = "Reject"
    else:
        decision = "Accept"

    return GuardrailResult(
        syntax_pass=syntax_pass,
        security_pass=security_pass,
        policy_pass=policy_pass,
        decision=decision,
        reasons=reasons,
    )
