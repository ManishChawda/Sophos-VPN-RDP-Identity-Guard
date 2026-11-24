# Security notes

- The token embedded in the originally supplied source has been removed from the repository version. Treat that old token as exposed and rotate it in any active deployment.
- The internal server address has been replaced by a configuration placeholder.
- Local `config.json` files are ignored by Git.
- Use a newly generated high-entropy shared secret on both endpoints.
- The current TCP transport is not encrypted. A shared token does not prevent network observers from reading or replaying traffic. Restrict the listener to a trusted VPN path and firewall allowlist; consider adding TLS before broader use.
- Do not publish production logs, real hostnames, usernames, IP addresses, certificates, or screenshots containing internal details.
- The sample `0.0.0.0` bind listens on all IPv4 interfaces. Narrow the bind address where practical and apply firewall restrictions.
