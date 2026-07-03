from netmiko import ConnectHandler

devices = {
    "SW1": {
        "device_type": "cisco_ios",
        "host": "192.168.137.101",
        "username": "admin",
        "password": "cisco",
        "secret": "cisco",
        "port": 22,
    },
    "SW2": {
        "device_type": "cisco_ios",
        "host": "192.168.137.102",
        "username": "admin",
        "password": "cisco",
        "secret": "cisco",
        "port": 22,
    },
    "SW3": {
        "device_type": "cisco_ios",
        "host": "192.168.137.103",
        "username": "admin",
        "password": "cisco",
        "secret": "cisco",
        "port": 22,
    },
}

for name, device in devices.items():
    print(f"\n===== Testing {name} =====")
    try:
        conn = ConnectHandler(**device)
        conn.enable()

        print("Connected successfully.")
        print(conn.send_command("show ip interface brief"))
        print(conn.send_command("show vlan brief"))

        conn.disconnect()
    except Exception as e:
        print("Connection failed:")
        print(e)