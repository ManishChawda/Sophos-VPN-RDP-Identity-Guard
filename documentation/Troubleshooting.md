# Troubleshooting guide

| Symptom | Areas to inspect |
|---|---|
| Client reports missing configuration | Copy `config.example.json` to `config.json` beside the client script and complete required values |
| Server reports missing configuration | Copy server example configuration to `config.json` beside the server script |
| Client cannot connect | Check server address, port, VPN routing, listener status, and Windows Firewall |
| VPN username is not detected | Confirm Sophos Connect log path, file permissions, and whether the installed log format matches the parser |
| No RDP session is evaluated | Confirm it is an active/connected RDP session, the client IP matches the registered VPN peer address, and a live VPN identity is registered |
| Mismatched session is not logged off | Check server process privileges and Windows WTS API access |
| Popup is not visible | Check that the client agent runs in the interactive user's session and that the TCP connection is active |

The current implementation suppresses several exceptions to keep its background loops running. For a future hardened release, add structured logging and observable error reporting.
