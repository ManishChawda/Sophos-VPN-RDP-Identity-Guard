import socket
import json
import threading
import time
import ctypes
from pathlib import Path
from ctypes import wintypes


# =================================================
# CONFIGURATION
# =================================================

CONFIG_FILE = Path(__file__).with_name("config.json")

def load_config():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        raise SystemExit(
            "Missing config.json. Copy config.example.json to config.json "
            "and configure the bind address, port, and shared token."
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Unable to read server configuration: {exc}")

    required = ("bind_host", "port", "token")
    missing = [key for key in required if config.get(key) in (None, "")]
    if missing:
        raise SystemExit("Missing required server configuration: " + ", ".join(missing))
    return config

CONFIG = load_config()
HOST = CONFIG["bind_host"]
PORT = int(CONFIG["port"])
TOKEN = CONFIG["token"]
VPN_TIMEOUT = int(CONFIG.get("vpn_identity_timeout_seconds", 15))
CHECK_INTERVAL = float(CONFIG.get("rdp_check_interval_seconds", 0.5))


# =================================================
# STORAGE
# =================================================

vpn_users = {}
vpn_connections = {}

blocked_sessions = set()

lock = threading.Lock()


# =================================================
# WINDOWS WTS CONSTANTS
# =================================================

WTS_CURRENT_SERVER_HANDLE = ctypes.c_void_p(0)

WTS_ACTIVE = 0
WTS_CONNECTED = 1

WTS_USER_NAME = 5

# IMPORTANT:
# This is the numeric WTS information class.
WTS_CLIENT_ADDRESS_INFO = 14

WTS_CLIENT_PROTOCOL_TYPE = 16

RDP_PROTOCOL = 2


# =================================================
# WTS STRUCTURES
# =================================================

class WTS_SESSION_INFO(ctypes.Structure):

    _fields_ = [
        ("SessionId", wintypes.DWORD),
        ("pWinStationName", wintypes.LPWSTR),
        ("State", wintypes.DWORD),
    ]


class WTS_CLIENT_ADDRESS_STRUCT(ctypes.Structure):

    _fields_ = [
        # IMPORTANT:
        # AddressFamily is DWORD, not USHORT.
        ("AddressFamily", wintypes.DWORD),

        ("Address", ctypes.c_ubyte * 20),
    ]


# =================================================
# LOAD WTS API
# =================================================

WTS = ctypes.WinDLL(
    "wtsapi32",
    use_last_error=True
)


WTS.WTSEnumerateSessionsW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(
        ctypes.POINTER(WTS_SESSION_INFO)
    ),
    ctypes.POINTER(wintypes.DWORD)
]

WTS.WTSEnumerateSessionsW.restype = wintypes.BOOL


WTS.WTSQuerySessionInformationW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.DWORD)
]

WTS.WTSQuerySessionInformationW.restype = wintypes.BOOL


WTS.WTSFreeMemory.argtypes = [
    ctypes.c_void_p
]

WTS.WTSFreeMemory.restype = None


WTS.WTSLogoffSession.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.BOOL
]

WTS.WTSLogoffSession.restype = wintypes.BOOL


# =================================================
# QUERY WTS STRING
# =================================================

def query_wts_string(
    session_id,
    info_class
):

    buffer = ctypes.c_void_p()
    returned = wintypes.DWORD()

    success = WTS.WTSQuerySessionInformationW(
        WTS_CURRENT_SERVER_HANDLE,
        session_id,
        info_class,
        ctypes.byref(buffer),
        ctypes.byref(returned)
    )

    if not success or not buffer.value:

        return ""


    try:

        return ctypes.wstring_at(
            buffer.value
        ).strip()


    finally:

        WTS.WTSFreeMemory(
            buffer
        )


# =================================================
# QUERY RDP CLIENT IP
# =================================================

def query_client_ip(
    session_id
):

    buffer = ctypes.c_void_p()
    returned = wintypes.DWORD()


    success = WTS.WTSQuerySessionInformationW(

        WTS_CURRENT_SERVER_HANDLE,

        session_id,

        WTS_CLIENT_ADDRESS_INFO,

        ctypes.byref(buffer),

        ctypes.byref(returned)
    )


    if not success or not buffer.value:

        return ""


    try:

        address = ctypes.cast(

            buffer,

            ctypes.POINTER(
                WTS_CLIENT_ADDRESS_STRUCT
            )

        ).contents


        # -----------------------------
        # IPv4
        # -----------------------------

        if address.AddressFamily == socket.AF_INET:

            return socket.inet_ntoa(

                bytes(
                    address.Address[2:6]
                )

            )


        # -----------------------------
        # IPv6
        # -----------------------------

        if address.AddressFamily == socket.AF_INET6:

            return socket.inet_ntop(

                socket.AF_INET6,

                bytes(
                    address.Address[2:18]
                )

            )


        return ""


    finally:

        WTS.WTSFreeMemory(
            buffer
        )


# =================================================
# QUERY RDP PROTOCOL
# =================================================

def query_protocol(
    session_id
):

    buffer = ctypes.c_void_p()
    returned = wintypes.DWORD()


    success = WTS.WTSQuerySessionInformationW(

        WTS_CURRENT_SERVER_HANDLE,

        session_id,

        WTS_CLIENT_PROTOCOL_TYPE,

        ctypes.byref(buffer),

        ctypes.byref(returned)
    )


    if not success or not buffer.value:

        return 0


    try:

        return ctypes.cast(

            buffer,

            ctypes.POINTER(
                wintypes.USHORT
            )

        ).contents.value


    finally:

        WTS.WTSFreeMemory(
            buffer
        )


# =================================================
# GET CURRENT RDP SESSIONS
# =================================================

def get_rdp_sessions():

    sessions = ctypes.POINTER(
        WTS_SESSION_INFO
    )()

    count = wintypes.DWORD()


    success = WTS.WTSEnumerateSessionsW(

        WTS_CURRENT_SERVER_HANDLE,

        0,

        1,

        ctypes.byref(sessions),

        ctypes.byref(count)
    )


    if not success:

        return []


    result = []


    try:

        for index in range(
            count.value
        ):

            session = sessions[index]


            # Only active/connected sessions

            if session.State not in (

                WTS_ACTIVE,

                WTS_CONNECTED

            ):

                continue


            # Only RDP

            if query_protocol(

                session.SessionId

            ) != RDP_PROTOCOL:

                continue


            username = query_wts_string(

                session.SessionId,

                WTS_USER_NAME

            ).strip().lower()


            client_ip = query_client_ip(

                session.SessionId

            ).strip()


            if not username:

                continue


            if not client_ip:

                continue


            result.append({

                "session_id":
                    session.SessionId,

                "username":
                    username,

                "ip":
                    client_ip

            })


    finally:

        WTS.WTSFreeMemory(
            sessions
        )


    return result


# =================================================
# SEND POPUP TO HOME PC
# =================================================

def send_popup(
    source_ip
):

    message = {

        "action":
            "popup",

        "message":

            (
                "Your RDP login was blocked.\n\n"

                "The Windows RDP username does not "
                "match the Sophos VPN username.\n\n"

                "Please use the same username for "
                "Sophos VPN and RDP."
            )
    }


    with lock:

        connection = vpn_connections.get(
            source_ip
        )


    if connection:

        try:

            connection.sendall(

                (
                    json.dumps(message)

                    + "\n"

                ).encode()

            )

        except Exception:

            pass


# =================================================
# LOGOFF EXACT RDP SESSION
# =================================================

def force_logoff(
    session_id
):

    try:

        success = WTS.WTSLogoffSession(

            WTS_CURRENT_SERVER_HANDLE,

            session_id,

            True

        )

        return bool(success)


    except Exception:

        return False


# =================================================
# ENFORCE ONLY VPN RDP SESSIONS
# =================================================

def enforce_sessions():

    last_report = 0


    while True:

        try:

            sessions = get_rdp_sessions()

            active_session_ids = set()


            for session in sessions:

                session_id = session[
                    "session_id"
                ]

                username = session[
                    "username"
                ]

                source_ip = session[
                    "ip"
                ]


                active_session_ids.add(
                    session_id
                )


                # =================================
                # FIND SOPHOS VPN IDENTITY
                # =================================

                with lock:

                    vpn_info = vpn_users.get(
                        source_ip
                    )


                # =================================
                # CRITICAL RULE
                #
                # NO SOPHOS VPN IDENTITY
                # = IGNORE THE RDP SESSION
                #
                # This protects:
                #
                # - GRKL Thin Clients
                # - GRKL LAN PCs
                # - Any other LAN RDP
                # =================================

                if not vpn_info:

                    continue


                # =================================
                # SOPHOS VPN SESSION FOUND
                # =================================

                vpn_username = vpn_info[
                    "username"
                ]


                mismatch = (

                    vpn_username
                    != username

                )


                # =================================
                # MATCH
                # =================================

                if not mismatch:

                    with lock:

                        blocked_sessions.discard(
                            session_id
                        )

                    continue


                # =================================
                # MISMATCH
                # =================================

                with lock:

                    first_block = (

                        session_id
                        not in blocked_sessions

                    )

                    blocked_sessions.add(
                        session_id
                    )


                if first_block:

                    send_popup(
                        source_ip
                    )


                # =================================
                # LOGOFF EXACT VPN RDP SESSION
                # =================================

                force_logoff(
                    session_id
                )


            # Remove old session IDs

            with lock:

                blocked_sessions.intersection_update(

                    active_session_ids

                )


        except Exception:

            pass


        time.sleep(
            CHECK_INTERVAL
        )


# =================================================
# RECEIVE SOPHOS VPN IDENTITY
# =================================================

def handle_client(
    connection,
    address
):

    source_ip = address[0]


    with lock:

        old_connection = vpn_connections.get(
            source_ip
        )

        vpn_connections[
            source_ip
        ] = connection


    if (

        old_connection

        and

        old_connection
        is not connection

    ):

        try:

            old_connection.close()

        except Exception:

            pass


    try:

        buffer = ""


        while True:

            data = connection.recv(
                4096
            )


            if not data:

                break


            buffer += data.decode(

                "utf-8",

                errors="ignore"

            )


            while "\n" in buffer:

                line, buffer = (

                    buffer.split(
                        "\n",
                        1
                    )

                )


                try:

                    info = json.loads(
                        line
                    )


                    # =========================
                    # TOKEN CHECK (shared secret; transport is not encrypted by this implementation)
                    # =========================

                    if (

                        info.get("token")
                        != TOKEN

                    ):

                        continue


                    username = str(

                        info.get(
                            "username",
                            ""
                        )

                    ).strip().lower()


                    vpn_ip = str(

                        info.get(
                            "vpn_ip",
                            ""
                        )

                    ).strip()


                    if not username:

                        continue


                    # =========================
                    # SOURCE IP VALIDATION
                    # =========================

                    if (

                        vpn_ip

                        and

                        vpn_ip
                        != source_ip

                    ):

                        continue


                    # =========================
                    # REGISTER VPN IDENTITY
                    # =========================

                    with lock:

                        vpn_users[
                            source_ip
                        ] = {

                            "username":
                                username,

                            "last_seen":
                                time.time()

                        }


                except Exception:

                    pass


    except Exception:

        pass


    finally:

        with lock:

            if (

                vpn_connections.get(
                    source_ip
                )

                is connection

            ):

                del vpn_connections[
                    source_ip
                ]


            vpn_users.pop(
                source_ip,
                None
            )


        try:

            connection.close()

        except Exception:

            pass


# =================================================
# CLEANUP OLD VPN IDENTITIES
# =================================================

def cleanup_vpn_users():

    while True:

        time.sleep(
            3
        )


        now = time.time()


        with lock:

            for ip in list(
                vpn_users.keys()
            ):

                if (

                    now
                    - vpn_users[ip][
                        "last_seen"
                    ]

                    >

                    VPN_TIMEOUT

                ):

                    vpn_users.pop(
                        ip,
                        None
                    )


# =================================================
# TCP SERVER
# =================================================

def start_server():

    server = socket.socket(

        socket.AF_INET,

        socket.SOCK_STREAM

    )


    server.setsockopt(

        socket.SOL_SOCKET,

        socket.SO_REUSEADDR,

        1

    )


    server.bind(

        (
            HOST,
            PORT
        )

    )


    server.listen(
        20
    )


    while True:

        connection, address = (

            server.accept()

        )


        threading.Thread(

            target=handle_client,

            args=(

                connection,

                address

            ),

            daemon=True

        ).start()


# =================================================
# START
# =================================================

threading.Thread(

    target=start_server,

    daemon=True

).start()


threading.Thread(

    target=cleanup_vpn_users,

    daemon=True

).start()


threading.Thread(

    target=enforce_sessions,

    daemon=True

).start()


# =================================================
# KEEP PROCESS ALIVE
# =================================================

while True:

    time.sleep(
        60
    )