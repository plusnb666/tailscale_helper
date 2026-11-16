# Tailscale Device Discovery Implementation Plan

> **For agentic workers:** REQUIRED: Load and follow `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tailscale device discovery so `tscp device list` shows configured network devices and `send`/`get` can resolve an unknown device name with an explicit SSH user.

**Architecture:** Add a focused `src/tscp/tailscale.py` module that invokes `tailscale status --json`, validates and normalizes device data, and exposes deterministic name matching. Extend the CLI with `device list` and optional discovery resolution for transfers while preserving local alias precedence and existing commands.

**Tech Stack:** Python 3.10+, standard library (`json`, `shutil`, `subprocess`, `dataclasses`, `argparse`), pytest, and the system Tailscale CLI.

---

## File map

- Create: `src/tscp/tailscale.py` — Tailscale subprocess execution, JSON parsing, device records, and name matching.
- Create: `tests/test_tailscale.py` — discovery parsing, matching, and subprocess error tests.
- Modify: `src/tscp/errors.py` — add an `UnknownAliasError` subtype so invalid configuration is not mistaken for a missing alias.
- Modify: `src/tscp/config.py` — raise `UnknownAliasError` only when an alias is absent.
- Modify: `src/tscp/cli.py` — add `device list`, `--user`, and alias-first discovery fallback.
- Modify: `tests/test_cli.py` — test discovery listing and transfer fallback.
- Modify: `src/tscp/errors.py` — add discovery-specific error types only if needed for clear messages.
- Modify: `README.md` — document automatic discovery and `--user`.
- Modify: `docs/superpowers/progress/brainstorm-tailscale-device-discovery.md` — mark planning complete.

## Task 1: Implement the Tailscale discovery module

**Files:**
- Create: `src/tscp/tailscale.py`
- Create: `tests/test_tailscale.py`

- [ ] **Step 1: Write failing parser and matcher tests**

Create `tests/test_tailscale.py`:

```python
import json
from unittest.mock import patch

import pytest

from tscp.errors import TscpError
from tscp.tailscale import TailscaleDevice, discover_devices, find_device


STATUS = {
    "BackendState": "Running",
    "MagicDNSSuffix": "tail123.ts.net",
    "Self": {
        "HostName": "laptop",
        "DNSName": "laptop.tail123.ts.net.",
        "Online": True,
        "OS": "windows",
    },
    "Peer": {
        "node-1": {
            "HostName": "rocky-server",
            "DNSName": "rocky-server.tail123.ts.net.",
            "Online": True,
            "OS": "linux",
        },
        "node-2": {
            "HostName": "phone",
            "DNSName": "phone.tail123.ts.net.",
            "Online": False,
            "OS": "android",
        },
    },
}


def test_discover_devices_includes_self_and_peers():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps(STATUS),
                "stderr": "",
            })(),
        ):
            devices = discover_devices()

    assert devices == [
        TailscaleDevice("laptop", "laptop.tail123.ts.net", True, "windows"),
        TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux"),
        TailscaleDevice("phone", "phone.tail123.ts.net", False, "android"),
    ]


def test_find_device_matches_short_name_and_magicdns_name():
    devices = [
        TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux")
    ]

    assert find_device(devices, "rocky-server") == devices[0]
    assert find_device(devices, "rocky-server.tail123.ts.net.") == devices[0]


def test_find_device_reports_unknown_name():
    with pytest.raises(TscpError, match="device not found"):
        find_device([], "missing")


def test_find_device_reports_ambiguous_name():
    devices = [
        TailscaleDevice("rocky", "rocky.tail123.ts.net", True, "linux"),
        TailscaleDevice("rocky", "rocky-alt.tail123.ts.net", True, "linux"),
    ]

    with pytest.raises(TscpError, match="ambiguous"):
        find_device(devices, "rocky")


def test_missing_tailscale_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value=None):
        with pytest.raises(TscpError, match="tailscale was not found"):
            discover_devices()


def test_invalid_status_json_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 0,
                "stdout": "{not-json",
                "stderr": "",
            })(),
        ):
            with pytest.raises(TscpError, match="invalid status JSON"):
                discover_devices()


def test_failed_status_command_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 1,
                "stdout": "",
                "stderr": "Tailscale is stopped",
            })(),
        ):
            with pytest.raises(TscpError, match="status failed"):
                discover_devices()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_tailscale.py -q
```

Expected: FAIL because `tscp.tailscale` does not exist.

- [ ] **Step 3: Implement typed discovery and safe subprocess handling**

Create `src/tscp/tailscale.py`:

```python
from dataclasses import dataclass
import json
import shutil
import subprocess

from .errors import TscpError


@dataclass(frozen=True)
class TailscaleDevice:
    name: str
    dns_name: str
    online: bool
    operating_system: str


def discover_devices() -> list[TailscaleDevice]:
    if shutil.which("tailscale") is None:
        raise TscpError("tailscale was not found; install Tailscale or use a configured alias")
    try:
        completed = subprocess.run(
            ["tailscale", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise TscpError(f"could not start tailscale: {exc}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise TscpError(f"tailscale status failed: {message}")
    try:
        payload = json.loads(completed.stdout)
        records = [payload["Self"], *payload.get("Peer", {}).values()]
        return [_device_from_record(record) for record in records]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TscpError("tailscale returned invalid status JSON") from exc


def find_device(devices: list[TailscaleDevice], value: str) -> TailscaleDevice:
    normalized = value.rstrip(".").lower()
    matches = [
        device
        for device in devices
        if normalized in {device.name.lower(), device.dns_name.rstrip(".").lower()}
    ]
    if not matches:
        available = ", ".join(device.name for device in devices) or "none"
        raise TscpError(f"device not found: {value}; available devices: {available}")
    if len(matches) > 1:
        raise TscpError(f"device name is ambiguous: {value}")
    return matches[0]


def _device_from_record(record: dict) -> TailscaleDevice:
    dns_name = str(record["DNSName"]).rstrip(".")
    return TailscaleDevice(
        name=str(record["HostName"]),
        dns_name=dns_name,
        online=bool(record["Online"]),
        operating_system=str(record.get("OS", "unknown")),
    )
```

Do not use `shell=True`; keep the command as an argument list. Preserve
offline devices in the result and let SCP report any eventual connection failure.

- [ ] **Step 4: Run discovery tests**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_tailscale.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/tailscale.py tests/test_tailscale.py
git commit -m "feat: discover Tailscale devices"
```

## Task 2: Add device listing and discovery transfer fallback

**Files:**
- Modify: `src/tscp/errors.py`
- Modify: `src/tscp/config.py`
- Modify: `src/tscp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
from tscp.errors import UnknownAliasError
from tscp.tailscale import TailscaleDevice


def test_device_list_prints_discovered_devices(monkeypatch, capsys):
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux")],
    )

    assert main(["device", "list"]) == 0
    output = capsys.readouterr().out
    assert "rocky-server" in output
    assert "online" in output


def test_send_discovers_unknown_device_with_user(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    calls = []
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux")],
    )
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main([
        "--config", str(config), "send", "report.zip", "rocky-server:/data/",
        "--user", "root",
    ]) == 0
    assert calls == [[
        "scp", "report.zip", "root@rocky-server.tail123.ts.net:/data/",
    ]]


def test_discovery_transfer_requires_user(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.json"
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux")],
    )

    assert main(["--config", str(config), "send", "report.zip", "rocky-server:/data/"]) == 2
    assert "--user" in capsys.readouterr().err
```

The existing alias-based send/get tests must continue passing without `--user`.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_cli.py -q
```

Expected: FAIL because the CLI has no `device` command and no discovery fallback.

- [ ] **Step 3: Extend the CLI**

In `src/tscp/cli.py`, import `discover_devices`, `find_device`, and
`TailscaleDevice`. Add the following parser arguments:

```python
device = commands.add_parser("device")
device_commands = device.add_subparsers(dest="device_command", required=True)
device_commands.add_parser("list")

send.add_argument("--user")
get.add_argument("--user")
```

Use these handlers:

```python
def _handle_device(args: argparse.Namespace) -> int:
    if args.device_command == "list":
        for device in discover_devices():
            state = "online" if device.online else "offline"
            print(f"{device.name}\t{device.dns_name}\t{device.operating_system}\t{state}")
    return 0


def _resolve_alias(
    name: str,
    store: ConfigStore,
    user: str | None,
) -> Alias:
    try:
        return store.get_alias(name)
    except UnknownAliasError:
        if not user:
            raise TscpError(
                f"unknown alias: {name}; discovery transfers require --user"
            )
        device = find_device(discover_devices(), name)
        return Alias(name=name, user=user, host=device.dns_name, default_path="/")
```

In `src/tscp/errors.py`, add:

```python
class UnknownAliasError(ConfigError):
    """Raised when a requested alias does not exist."""
```

In `src/tscp/config.py`, import `UnknownAliasError` and change only the
missing-alias branch in `get_alias` to:

```python
raise UnknownAliasError(f"unknown alias: {name}")
```

Do not catch all `TscpError` values in `_resolve_alias`; malformed configuration
must remain a configuration error and must not trigger device discovery.

Update `main()` so `device` calls `_handle_device(args)` before creating or
using transfer arguments. In `_handle_transfer`, call `_resolve_alias` instead
of `store.get_alias(alias_name)`. Keep the existing alias result unchanged and
pass the discovered alias into `build_scp_command`.

- [ ] **Step 4: Run CLI and full tests**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_cli.py -q
& "$HOME\miniconda3\python.exe" -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/cli.py tests/test_cli.py
git commit -m "feat: use discovered devices in transfers"
```

## Task 3: Document discovery and validate the installed CLI

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/progress/brainstorm-tailscale-device-discovery.md`

- [ ] **Step 1: Add bilingual documentation**

Add this section to `README.md`:

```text
## Automatic device discovery / 自动发现设备

List Tailscale devices / 查看 Tailscale 设备：

tscp device list

Use a discovered device for transfers / 使用自动发现的设备传输：

tscp send .\report.zip rocky-server:/data/ --user root
tscp get rocky-server:/data/report.zip .\ --user root

The command reads `tailscale status --json` and uses the device's MagicDNS
hostname. Discovery-based transfers require `--user` because Tailscale does
not provide the remote SSH account. Existing configured aliases continue to
work without `--user`.

命令通过 `tailscale status --json` 读取设备，并使用设备的 MagicDNS 主机名。
自动发现传输必须提供 `--user`，因为 Tailscale 不提供远程 SSH 用户名。
已有的配置别名仍然可以不带 `--user` 使用。
```

Document that missing Tailscale, stopped Tailscale, invalid JSON, unknown
devices, and ambiguous names produce explicit errors.

- [ ] **Step 2: Run tests and install validation**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest -q
& "$HOME\miniconda3\python.exe" -m pip install .
& "$HOME\miniconda3\Scripts\tscp.exe" device list
```

Expected: unit tests pass, package installation succeeds, and `device list`
either prints discovered devices or reports an actionable Tailscale error.

- [ ] **Step 3: Commit documentation**

```text
git add README.md docs/superpowers/progress/brainstorm-tailscale-device-discovery.md
git commit -m "docs: explain Tailscale device discovery"
```

## Final verification checklist

- [ ] `python -m pytest -q` passes.
- [ ] Existing configured-alias transfers still work without `--user`.
- [ ] `tscp device list` displays name, MagicDNS hostname, OS, and state.
- [ ] Unknown devices can transfer with `--user`.
- [ ] Discovery transfers without `--user` fail clearly.
- [ ] Missing Tailscale, invalid JSON, failed status commands, unknown devices,
      and ambiguous names produce nonzero exit codes.
- [ ] README documents both manual aliases and automatic discovery in Chinese
      and English.
