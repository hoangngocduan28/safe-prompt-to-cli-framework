import re


TOKEN_PATTERN = re.compile(
    r"\b(?:DEVICE_[A-Z]|IP_\d+|SUBNET_\d+|VLAN_NAME_\d+|INTERFACE_\d+)\b"
)


def deanonymize_text(text: str, mapping: dict) -> str:
    """Restore anonymized tokens to their original values."""
    restored = text
    for token, original in mapping.items():
        restored = restored.replace(token, str(original))
    return restored


def find_unresolved_tokens(text: str) -> list[str]:
    """Return unresolved anonymization tokens found in text."""
    unresolved_tokens: list[str] = []
    seen: set[str] = set()

    for match in TOKEN_PATTERN.finditer(text):
        token = match.group(0)
        if token not in seen:
            unresolved_tokens.append(token)
            seen.add(token)

    return unresolved_tokens
