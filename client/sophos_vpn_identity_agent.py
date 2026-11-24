import json
import os
import re
import socket
import time
import ctypes
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("config.json")

def load_config():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        raise SystemExit(
            "Missing config.json. Copy config.example.json to config.json "
            "and configure the local Sophos log path, server address, and shared token."
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Unable to read client configuration: {exc}")

    required = ("sophos_log_file", "server_host", "server_port", "token")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit("Missing required client configuration: " + ", ".join(missing))
    return config

CONFIG = load_config()
LOG_FILE = CONFIG["sophos_log_file"]
SERVER_IP = CONFIG["server_host"]
SERVER_PORT = int(CONFIG["server_port"])
TOKEN = CONFIG["token"]
HEARTBEAT = int(CONFIG.get("heartbeat_seconds", 5))


def get_vpn_info():

    if not os.path.exists(LOG_FILE):
        return None

    username = None
    state = None
    result = None
    vpn_ip = None

    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as file:

            for line in file:

                # Latest Sophos VPN username
                match = re.search(
                    r'MANAGEMENT:\s+CMD\s+\'username\s+"Auth"\s+([^\\\']+)\'',
                    line,
                    re.IGNORECASE
                )

                if match:
                    username = match.group(1).strip()

                # Latest OpenVPN connection state
                match = re.search(
                    r'MANAGEMENT:\s+>STATE:\s*[^,]+,([^,]+),([^,]+),([^,]+),',
                    line,
                    re.IGNORECASE
                )

                if match:
                    state = match.group(1).strip().upper()
                    result = match.group(2).strip().upper()
                    vpn_ip = match.group(3).strip()

    except Exception:
        return None

    if (
        state == "CONNECTED"
        and result == "SUCCESS"
        and username
        and vpn_ip
    ):
        return username.lower(), vpn_ip

    return None


def show_popup(message):

    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            message,
            "RDP Login Blocked",
            0x10
        )
    except Exception:
        pass


def connect_to_server():

    while True:

        try:

            sock = socket.create_connection(
                (SERVER_IP, SERVER_PORT),
                timeout=10
            )

            sock.settimeout(1)

            while True:

                vpn_info = get_vpn_info()

                if vpn_info:

                    username, vpn_ip = vpn_info

                    data = {
                        "token": TOKEN,
                        "username": username,
                        "vpn_ip": vpn_ip
                    }

                    message = json.dumps(data) + "\n"

                    sock.sendall(message.encode())

                else:

                    # VPN disconnected
                    break

                # Check for messages from server
                try:

                    response = sock.recv(4096)

                    if not response:
                        break

                    for line in response.decode(
                        "utf-8",
                        errors="ignore"
                    ).splitlines():

                        try:

                            command = json.loads(line)

                            if command.get("action") == "popup":

                                show_popup(
                                    command.get(
                                        "message",
                                        "RDP login blocked."
                                    )
                                )

                        except Exception:
                            pass

                except socket.timeout:
                    pass

                time.sleep(HEARTBEAT)

            sock.close()

        except Exception:
            time.sleep(5)


connect_to_server()