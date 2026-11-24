# Architecture and workflow

## Client workflow

1. `sophos_vpn_identity_agent.py` reads the configured Sophos Connect `openvpn.log`.
2. It extracts the most recent authenticated username, connection state, and VPN-assigned address using the log patterns present in the supplied implementation.
3. While connected, it sends a JSON message containing the configured shared token, username, and VPN IP to the configured server and port.
4. It checks for server notification messages and displays a Windows message box when a popup command is received.
5. When the VPN is disconnected or the TCP connection ends, it reconnects using the existing retry loop.

## Server workflow

1. `rdp_vpn_identity_guard.py` listens for client TCP connections.
2. It validates the shared token on received JSON messages.
3. It registers the reported VPN username against the TCP peer IP and tracks the last-seen time.
4. It enumerates active/connected RDP sessions using Windows WTS APIs.
5. For each RDP session, it retrieves the username and RDP client address.
6. If a VPN identity is registered for that client address, it compares the two usernames.
7. A match leaves the session alone. A mismatch triggers a logoff of that specific session and a popup notification to the client.
8. VPN identities expire after the configured timeout when heartbeats stop.

## Scope boundary

A session without a registered VPN identity is skipped. This is intentional in the supplied implementation so that ordinary LAN/thin-client RDP sessions are not subjected to the VPN identity comparison.
