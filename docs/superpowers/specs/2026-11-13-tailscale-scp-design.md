# Tailscale SCP automation design

## Goal

Provide a small command-line tool for Windows and Rocky Linux that sends and
retrieves files over the existing Tailscale and SSH setup without requiring the
user to look up Tailscale IP addresses.

## User experience

Users define a friendly device alias once:

```text
tscp config add rocky --user root --host rocky-server --path /data/transfer
```

They then transfer files by alias:

```text
tscp send ./report.zip rocky:/data/transfer/
tscp get rocky:/data/transfer/report.zip ./
tscp config list
```

The exact command names may follow the selected Python CLI framework, but the
alias-based send/get behavior is required.

## Architecture

- **CLI layer** parses commands, validates arguments, and formats user-facing
  errors.
- **Configuration layer** stores aliases, SSH users, MagicDNS hostnames, and
  default remote directories. It must not store passwords or private-key
  contents.
- **Target resolver** expands `alias:/path` into an SSH target such as
  `user@rocky-server:/path`. MagicDNS hostnames are preferred; a configured
  Tailscale IP is an optional fallback.
- **Transfer runner** invokes the system `scp` executable, preserving the
  user's existing SSH keys, SSH config, port settings, and permissions.

The tool targets Python and must run on Windows and Rocky Linux. It does not
replace Tailscale, SSH, or SSH key management.

## Supported behavior

- Add, list, update, and remove device aliases.
- Send a file or directory to an alias.
- Retrieve a file or directory from an alias.
- Support recursive directory transfer and common `scp` options where the
  underlying platform supports them.
- Use MagicDNS names so normal operation does not require IP lookup.
- Report actionable failures for unknown aliases, missing `scp`, unavailable
  Tailscale targets, SSH authentication failures, and invalid paths.

## Explicit non-goals

- No GUI.
- No password storage or private-key management.
- No synchronization, watch mode, or resumable transfers.
- No automatic device discovery or transfer history in the first version.

## Configuration and security

Configuration is user-local and contains connection metadata only. File paths
and command arguments must be passed to `scp` without shell string
interpolation, so paths containing spaces are handled safely and shell
injection is avoided. The implementation must surface subprocess failures
instead of converting them into success-shaped results.

## Validation

- Unit tests cover configuration persistence, alias resolution, local/remote
  path parsing, and error mapping.
- CLI-level tests verify send/get command construction without requiring a live
  transfer.
- Manual acceptance on Windows uses the current Tailscale MagicDNS setup; a
  Rocky Linux host verifies both upload and download over SSH.
