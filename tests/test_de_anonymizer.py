from src.de_anonymizer import deanonymize_text, find_unresolved_tokens


def test_deanonymize_text() -> None:
    mapping = {
        "DEVICE_A": "CoreSW01",
        "VLAN_NAME_001": "ACCOUNTING",
        "INTERFACE_001": "GigabitEthernet0/1",
    }

    output = deanonymize_text(
        "vlan 10\n name VLAN_NAME_001\ninterface INTERFACE_001",
        mapping,
    )

    assert "ACCOUNTING" in output
    assert "GigabitEthernet0/1" in output


def test_find_unresolved_tokens() -> None:
    unresolved_tokens = find_unresolved_tokens(
        "interface INTERFACE_999\n ip address IP_999"
    )

    assert unresolved_tokens == ["INTERFACE_999", "IP_999"]


def test_no_unresolved_tokens() -> None:
    unresolved_tokens = find_unresolved_tokens("vlan 10\n name ACCOUNTING")

    assert unresolved_tokens == []
