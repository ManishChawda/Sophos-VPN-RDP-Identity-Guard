# Installation and deployment

> These are sanitized, generic instructions. Replace example paths and values locally. Do not commit real `config.json` files.

## 1. Client PC

1. Install Python 3 and Sophos Connect.
2. Copy `client/sophos_vpn_identity_agent.py` to the client machine.
3. Copy `client/config.example.json` to `config.json` in the same directory.
4. Set `sophos_log_file` to the local Sophos Connect log path.
5. Set `server_host` to the server address reachable through the intended VPN path.
6. Set `server_port` to the server listener port.
7. Set `token` to a newly generated random secret. Use the same secret in the server configuration.
8. Ensure the account running the agent can read the Sophos log. If the popup must be visible to the interactive desktop user, run the agent in that user's session.

## 2. RDP server

1. Copy `server/rdp_vpn_identity_guard.py` to the Windows RDP server.
2. Copy `server/config.example.json` to `config.json` in the same directory.
3. Configure `bind_host`, `port`, and the same newly generated `token`.
4. Review the Windows Firewall rule and permit only the intended client/VPN source addresses.
5. Run the server process under an account with the required rights to enumerate and log off RDP sessions.

## 3. Scheduled tasks

See [Scheduled-Tasks.md](../deployment/Scheduled-Tasks.md) for generic examples. The task account must be selected deliberately:
- Client agent: use an account that can read the Sophos log; use an interactive logon context if visible popups are required.
- Server guard: use an appropriately privileged account. The supplied deployment notes used `SYSTEM` on the server.

## 4. Important

The repository version has not been tested in your environment. These instructions are a sanitized documentation template, not confirmation of a successful deployment. Preserve your existing working deployment until you separately choose to migrate it.
