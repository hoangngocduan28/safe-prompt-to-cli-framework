from src.guardrail import validate_cli


TOPOLOGY = {
    "devices": {
        "SW1": {
            "interfaces": [
                "GigabitEthernet0/0",
                "GigabitEthernet0/1",
                "GigabitEthernet0/2",
            ]
        }
    }
}

SETTINGS = {"allow_shutdown": False}


def _decision(cli: str, settings: dict | None = None) -> str:
    result = validate_cli(cli, TOPOLOGY, settings or SETTINGS)
    return result.decision


def test_valid_vlan_cli_accept() -> None:
    cli = """conf t
vlan 10
 name ACCOUNTING
end"""

    assert _decision(cli) == "Accept"


def test_valid_vlan_access_cli_accept() -> None:
    cli = """conf t
vlan 10
 name ACCOUNTING
interface GigabitEthernet0/1
 switchport mode access
 switchport access vlan 10
end"""

    assert _decision(cli) == "Accept"


def test_valid_stp_cli_accept() -> None:
    cli = """conf t
spanning-tree vlan 10 root primary
end"""

    assert _decision(cli) == "Accept"


def test_reload_rejected() -> None:
    cli = """conf t
reload"""

    assert _decision(cli) == "Reject"


def test_write_erase_rejected() -> None:
    assert _decision("write erase") == "Reject"


def test_delete_flash_rejected() -> None:
    assert _decision("delete flash:") == "Reject"


def test_invalid_vlan_syntax_rejected() -> None:
    assert _decision("vlan abc") == "Reject"


def test_vlan_out_of_range_rejected() -> None:
    assert _decision("vlan 5000") == "Reject"


def test_invalid_interface_rejected() -> None:
    assert _decision("interface GigabitEthernet") == "Reject"


def test_unknown_interface_rejected() -> None:
    assert _decision("interface GigabitEthernet0/99") == "Reject"


def test_router_ospf_rejected() -> None:
    assert _decision("router ospf 1") == "Reject"


def test_no_spanning_tree_all_rejected() -> None:
    assert _decision("no spanning-tree vlan 1-4094") == "Reject"


def test_shutdown_rejected_when_not_allowed() -> None:
    assert _decision("interface GigabitEthernet0/1\n shutdown") != "Accept"


def test_write_memory_allowed() -> None:
    assert _decision("write memory") == "Accept"
