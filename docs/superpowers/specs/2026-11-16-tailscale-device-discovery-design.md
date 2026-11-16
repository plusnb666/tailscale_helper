# Tailscale device discovery design

## Goal

Allow `tscp` to discover Tailscale devices from `tailscale status --json` so
users can transfer files by Tailscale device name without manually adding an
alias or looking up an IP address.

## User experience

List devices:

```powershell
tscp device list
```

Send and retrieve files using a discovered device:

```powershell
tscp send .\file.zip rocky:/data/ --user root
tscp get rocky:/data/file.zip .\ --user root
```

The SSH user is required for discovery-based transfers because Tailscale
metadata does not reliably identify the remote SSH account. Existing commands
using configured aliases remain supported:

```powershell
tscp send .\file.zip rocky:/data/
```

## Architecture

Add a focused `tailscale` module that invokes `tailscale status --json`,
validates the subprocess result, and converts the JSON into typed device
records. The CLI uses the existing `ConfigStore` first; if an alias is not
configured, it asks the Tailscale discovery layer to resolve the name and
constructs an `Alias` using the discovered MagicDNS hostname plus the
user-supplied SSH username.

The discovery layer is independent of configuration and SCP execution. Tests
mock the subprocess boundary, so unit tests do not require a live Tailscale
connection.

## Resolution behavior

1. Look up the requested name in the local alias configuration.
2. If no alias exists, run `tailscale status --json`.
3. Match a device by its short device name, hostname, or MagicDNS hostname.
4. Use the discovered MagicDNS FQDN as the SCP host.
5. Permit offline devices to resolve; SCP/SSH reports the eventual connection
   failure.

If multiple devices match, resolution fails instead of guessing. If the
device does not exist, the error includes available device names.

## CLI behavior

- Add `device list` to display short name, MagicDNS hostname, operating system,
  and online state.
- Add `--user` to `send` and `get`; it is required only when the target is not
  already a configured alias.
- Preserve `config add`, `config update`, `config list`, and `config remove`.
- Preserve alias-first behavior so existing scripts do not change.

## Error handling

Report explicit errors when `tailscale` is not installed, Tailscale is not
running, the JSON output is invalid, a device cannot be found, a name is
ambiguous, or a discovery transfer omits `--user`. Do not silently fall back
to an IP address or infer an SSH username.

## Testing

- Parse representative `tailscale status --json` output.
- Verify device listing formatting and online/offline states.
- Verify name, hostname, and MagicDNS matching.
- Verify unknown and ambiguous device errors.
- Verify alias-first transfer resolution.
- Verify discovery transfer requires `--user` and uses the discovered FQDN.
- Verify missing executable, nonzero exit status, and invalid JSON errors.
- Run the existing full test suite without a live Tailscale dependency.
