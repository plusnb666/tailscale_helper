# Tailscale SCP Helper

`tscp` provides alias-based SCP transfers over a Tailscale network. Configure a
device's MagicDNS hostname once, then use its alias instead of looking up a
Tailscale IP for every transfer.

## Prerequisites

- Python 3.10 or newer
- Tailscale connected on both machines
- Tailscale MagicDNS enabled, or another resolvable Tailscale hostname
- OpenSSH client (`scp`) installed
- SSH public-key authentication configured

The tool does not store passwords or private keys. It uses the user's existing
SSH configuration and credentials.

## Install

```text
python -m pip install .
```

## Configure a device

Use the device's Tailscale MagicDNS hostname as `--host`:

```text
tscp config add rocky --user root --host rocky-server --path /data/transfer
tscp config list
```

Update or remove an alias:

```text
tscp config update rocky --user root --host rocky-server --path /data/transfer
tscp config remove rocky
```

## Transfer files

Send a file:

```text
tscp send ./report.zip rocky:/data/transfer/
```

Retrieve a file:

```text
tscp get rocky:/data/transfer/report.zip ./
```

Transfer a directory recursively:

```text
tscp send --recursive ./folder rocky:/data/transfer/
tscp get --recursive rocky:/data/transfer/folder ./folder
```

If SSH uses a non-standard port, configure it with `--port`:

```text
tscp config update rocky --user root --host rocky-server --port 2222 --path /data/transfer
```

## Configuration location

By default, configuration is stored at:

```text
~/.config/tscp/config.json
```

Use `--config PATH` before the command to select another file. The file
contains aliases and connection metadata only; it never contains passwords or
private-key contents.
