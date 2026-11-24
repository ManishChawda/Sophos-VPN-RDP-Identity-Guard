# Sophos VPN – RDP Identity Guard

A Windows-based client/server utility that compares the username authenticated by Sophos Connect VPN with the username used to establish an RDP session. When a VPN-associated RDP session uses a different username, the server logs off that specific RDP session and sends a notification to the VPN client.

> **Portfolio / security notice:** This repository contains sanitized source code and example configuration only. It is not a turnkey security product. Review, harden, and validate it in an isolated environment before deployment. The original shared token and internal server address have been removed. Generate a new secret for any real deployment.

## Project objective

Enforce a consistent identity between a Sophos VPN login and an RDP login originating from that VPN connection, while leaving RDP sessions without a registered Sophos VPN identity outside this tool's enforcement scope.

## Architecture

```text
HOME / REMOTE WINDOWS PC                         WINDOWS RDP SERVER
┌──────────────────────────────┐                ┌─────────────────────────────┐
│ Sophos Connect               │                │ rdp_vpn_identity_guard.py   │
│                              │                │                             │
│ openvpn.log                  │                │ TCP listener                │
│       │                      │   TCP / JSON   │       │                     │
│       ▼                      │ ─────────────► │       ▼                     │
│ sophos_vpn_identity_agent.py │                │ VPN identity registry       │
│       │                      │ ◄───────────── │       │                     │
│       └── identity + heartbeat│  popup message │       ▼                     │
│                              │                │ Windows WTS session checks │
└──────────────────────────────┘                │       │                     │
                                                │       ▼                     │
                                                │ Compare VPN and RDP names   │
                                                │       │                     │
                                                │ Match: leave session        │
                                                │ Mismatch: log off session  │
                                                └─────────────────────────────┘
```

## Components

| Component | File | Responsibility |
|---|---|---|
| VPN client agent | `client/sophos_vpn_identity_agent.py` | Reads Sophos Connect log state, extracts VPN username/IP, sends identity heartbeats and displays server notifications |
| RDP server guard | `server/rdp_vpn_identity_guard.py` | Receives VPN identity, enumerates RDP sessions through Windows WTS APIs, compares usernames and logs off mismatched VPN-associated sessions |

## Enforcement behaviour

| VPN identity | RDP username | Behaviour |
|---|---|---|
| Present and username matches | Same username | Session is left connected |
| Present and username differs | Different username | That RDP session is logged off; notification is sent to the client |
| No registered VPN identity for the RDP client IP | Any username | Session is ignored by this utility |

The username is **not hardcoded**. The comparison uses the username received from the active Sophos VPN connection and the username reported by Windows for the RDP session.

### Why sessions without a VPN identity are ignored

The server may also host legitimate office LAN or thin-client RDP sessions. The current implementation intentionally skips sessions for which it has no registered Sophos VPN identity. It does not automatically log off a session merely because the VPN identity is absent or has expired.

## Repository layout

```text
client/          Home/remote PC agent and example configuration
server/          Windows RDP server guard and example configuration
deployment/      Scheduled-task deployment guidance
documentation/   Architecture, behaviour, security and troubleshooting notes
screenshots/     Sanitized demonstration screenshots (add before publishing)
```

## Configuration

The scripts load a local `config.json` placed beside each script. The repository includes `config.example.json` files. Copy the appropriate example to `config.json` on each machine and edit the values locally.

- Client: `client/config.example.json`
- Server: `server/config.example.json`

The real `config.json` files are excluded by `.gitignore`. Use a newly generated, long, random shared secret in both local configuration files. Never commit the real configuration files or secrets.

The client `server_host` must be an address reachable through the intended VPN/network path. The server `bind_host` controls the local interface on which the TCP listener accepts connections. Restrict access to the listener using host/network firewall rules.

## Requirements and platform

- Windows on both endpoints
- Python 3
- Sophos Connect client on the client PC
- Permission to read the Sophos Connect log
- Permission to query and log off Windows RDP sessions on the server
- TCP connectivity to the configured listener port (default example: `5001`)

The code uses Python standard-library modules and Windows Terminal Services (WTS) APIs via `ctypes`. It is Windows-specific.

## Security considerations and limitations

- The shared token is an application-level identity check; **the current TCP protocol does not provide TLS encryption**. Do not expose the listener to untrusted networks. A production-ready deployment should use authenticated TLS or another protected transport.
- The sample bind address `0.0.0.0` listens on all IPv4 interfaces. Restrict inbound access to the expected VPN/client source addresses using Windows Firewall and network controls.
- The server trusts the client-reported VPN username after token validation. This design should be reviewed before use as a high-assurance security control.
- Protect local `config.json` files with appropriate Windows ACLs.
- The client agent reads a Sophos log file whose format/path may vary by Sophos Connect version.
- RDP session enforcement depends on Windows WTS API behaviour and the permissions of the account running the server process.
- A missing VPN identity causes the RDP session to be ignored; it does not cause automatic logoff.
- This repository documents the supplied implementation. It does not claim independent security certification or production validation.

## Deployment overview

See [Installation and deployment](documentation/Installation.md) and [Scheduled tasks](deployment/Scheduled-Tasks.md). Do not deploy the sanitized files over a working installation without reviewing local paths, account permissions, firewall rules, and configuration first.

## Disclaimer

This project is provided for learning, demonstration, and portfolio purposes. The operator is responsible for testing and securing any deployment.
