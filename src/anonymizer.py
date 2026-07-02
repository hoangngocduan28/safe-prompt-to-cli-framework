from pathlib import Path
import json
import re


DEVICE_NAMES = ("SW1", "SW2", "SW3", "CoreSW01", "DistSW02")
VLAN_NAMES = ("ACCOUNTING", "HR", "STUDENT", "SALES")

SUBNET_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\b")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
INTERFACE_PATTERN = re.compile(r"\bGigabitEthernet\d+(?:/\d+)+\b")


def load_mapping(mapping_path: str | Path) -> dict:
    """Load an anonymization mapping, returning an empty mapping if missing."""
    path = Path(mapping_path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        content = file.read().strip()

    if not content:
        return {}

    mapping = json.loads(content)
    if not isinstance(mapping, dict):
        raise ValueError(f"Anonymization mapping must be a JSON object: {path}")

    return mapping


def save_mapping(mapping: dict, mapping_path: str | Path) -> None:
    """Save an anonymization mapping as local JSON."""
    path = Path(mapping_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(mapping, file, indent=2)


def _boundary_pattern(value: str) -> re.Pattern:
    """Build a pattern that matches a complete sensitive value."""
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])")


def _find_existing_token(mapping: dict, value: str, token_prefix: str) -> str | None:
    """Return the token already assigned to a value, if present."""
    for token, original in mapping.items():
        if token.startswith(token_prefix) and original == value:
            return token
    return None


def _next_device_token(mapping: dict) -> str:
    """Return the next available device token."""
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        token = f"DEVICE_{letter}"
        if token not in mapping:
            return token
    raise ValueError("No DEVICE tokens available")


def _next_numbered_token(mapping: dict, token_prefix: str) -> str:
    """Return the next available numbered token for a prefix."""
    number = 1
    while True:
        token = f"{token_prefix}_{number:03d}"
        if token not in mapping:
            return token
        number += 1


def _get_or_create_token(mapping: dict, value: str, token_prefix: str) -> str:
    """Return a stable token for the original value."""
    existing_token = _find_existing_token(mapping, value, token_prefix)
    if existing_token:
        return existing_token

    if token_prefix == "DEVICE":
        token = _next_device_token(mapping)
    else:
        token = _next_numbered_token(mapping, token_prefix)

    mapping[token] = value
    return token


def _replace_pattern(text: str, pattern: re.Pattern, mapping: dict, token_prefix: str) -> str:
    """Replace all regex matches with stable anonymization tokens."""
    def replace_match(match: re.Match) -> str:
        value = match.group(0)
        return _get_or_create_token(mapping, value, token_prefix)

    return pattern.sub(replace_match, text)


def _replace_known_values(
    text: str,
    values: tuple[str, ...],
    mapping: dict,
    token_prefix: str,
) -> str:
    """Replace known sensitive values with stable anonymization tokens."""
    for value in values:
        pattern = _boundary_pattern(value)
        if not pattern.search(text):
            continue
        token = _get_or_create_token(mapping, value, token_prefix)
        text = pattern.sub(token, text)
    return text


def anonymize_text(
    text: str,
    mapping_path: str | Path = "data/anonymization_map.json",
) -> tuple[str, dict]:
    """Anonymize sensitive network values and persist the token mapping."""
    mapping = load_mapping(mapping_path)

    anonymized = text
    anonymized = _replace_pattern(anonymized, SUBNET_PATTERN, mapping, "SUBNET")
    anonymized = _replace_pattern(anonymized, IP_PATTERN, mapping, "IP")
    anonymized = _replace_pattern(anonymized, INTERFACE_PATTERN, mapping, "INTERFACE")
    anonymized = _replace_known_values(anonymized, DEVICE_NAMES, mapping, "DEVICE")
    anonymized = _replace_known_values(anonymized, VLAN_NAMES, mapping, "VLAN_NAME")

    save_mapping(mapping, mapping_path)
    return anonymized, mapping
