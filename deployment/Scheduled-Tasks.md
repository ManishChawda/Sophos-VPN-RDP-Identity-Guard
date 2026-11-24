# Scheduled task deployment notes

The following are templates. Adjust paths, account names, and permissions for the target Windows environment. Do not copy the original internal paths into public documentation.

## Client agent (interactive user context recommended for visible popup)

```powershell
$Python = "C:\Path\To\pythonw.exe"
$Script = "C:\Path\To\client\sophos_vpn_identity_agent.py"

schtasks /Create /TN "Sophos VPN Identity Agent" `
  /TR "`"$Python`" `"$Script`"" `
  /SC ONLOGON /F
```

Run and verify:

```powershell
schtasks /Run /TN "Sophos VPN Identity Agent"
schtasks /Query /TN "Sophos VPN Identity Agent" /V /FO LIST
```

Choose the task's run-as account through Task Scheduler based on Sophos log access and whether a visible notification is required. A task running as SYSTEM in session 0 may not display a popup on the signed-in user's desktop.

## Server guard (SYSTEM example)

```powershell
$Python = "C:\Path\To\pythonw.exe"
$Script = "C:\Path\To\server\rdp_vpn_identity_guard.py"

schtasks /Create /TN "Sophos RDP Identity Guard" `
  /TR "`"$Python`" `"$Script`"" `
  /SC ONSTART /RU SYSTEM /RL HIGHEST /F

schtasks /Run /TN "Sophos RDP Identity Guard"
schtasks /Query /TN "Sophos RDP Identity Guard" /V /FO LIST
```

## Remove tasks

```powershell
schtasks /Delete /TN "Sophos VPN Identity Agent" /F
schtasks /Delete /TN "Sophos RDP Identity Guard" /F
```

Stop only the relevant process after confirming its command line and process ID. Avoid terminating every `pythonw.exe` process because other Python applications may be running.
