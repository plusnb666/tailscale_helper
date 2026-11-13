# Tailscale SCP Automation Implementation Plan

> **For agentic workers:** REQUIRED: Load and follow `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI named `tscp` that transfers files through configured Tailscale MagicDNS hostnames without requiring users to inspect IP addresses.

**Architecture:** Keep four focused layers: a JSON-backed alias repository, an `alias:/path` target resolver, a subprocess-based SCP runner, and an `argparse` CLI. The runner receives an argument list rather than a shell command string, so Windows paths and spaces are safe and shell injection is avoided. Device aliases contain SSH metadata only; credentials remain under the user's existing SSH configuration.

**Tech Stack:** Python 3.10+, standard library (`argparse`, `json`, `pathlib`, `subprocess`, `shutil`, `dataclasses`), pytest, and the system OpenSSH `scp` executable.

---

## File map

- Create: `pyproject.toml` — package metadata, `tscp` console entry point, and pytest configuration.
- Create: `src/tscp/__init__.py` — package version.
- Create: `src/tscp/errors.py` — user-facing exception types.
- Create: `src/tscp/config.py` — alias data model and user-local JSON persistence.
- Create: `src/tscp/targets.py` — alias and remote-path parsing.
- Create: `src/tscp/transfer.py` — safe SCP command construction and execution.
- Create: `src/tscp/cli.py` — command parser, validation, and exit-code mapping.
- Create: `tests/test_config.py` — configuration persistence tests.
- Create: `tests/test_targets.py` — alias/path parsing tests.
- Create: `tests/test_transfer.py` — SCP command and subprocess tests.
- Create: `tests/test_cli.py` — CLI behavior tests.
- Create: `README.md` — installation, SSH/Tailscale prerequisites, and examples.

## Task 1: Scaffold the package and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/tscp/__init__.py`
- Create: `src/tscp/errors.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing package smoke test**

Create `tests/test_config.py` with:

```python
from tscp import __version__


def test_package_exposes_version():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```text
python -m pytest tests/test_config.py::test_package_exposes_version -q
```

Expected: FAIL because the `tscp` package does not exist yet.

- [ ] **Step 3: Add the minimal package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "tailscale-scp-helper"
version = "0.1.0"
description = "Alias-based SCP transfers over Tailscale MagicDNS"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
tscp = "tscp.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `src/tscp/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/tscp/errors.py`:

```python
class TscpError(Exception):
    """Base class for expected command errors."""


class ConfigError(TscpError):
    """Raised when alias configuration is missing or invalid."""


class TargetError(TscpError):
    """Raised when an alias target cannot be parsed or resolved."""


class TransferError(TscpError):
    """Raised when SCP cannot be started or fails."""
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run:

```text
python -m pytest tests/test_config.py::test_package_exposes_version -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add pyproject.toml src/tscp/__init__.py src/tscp/errors.py tests/test_config.py
git commit -m "build: scaffold tscp package"
```

## Task 2: Implement alias configuration persistence

**Files:**
- Modify: `tests/test_config.py`
- Create: `src/tscp/config.py`

- [ ] **Step 1: Write failing configuration tests**

Append to `tests/test_config.py`:

```python
import json

import pytest

from tscp.config import Alias, ConfigStore
from tscp.errors import ConfigError


def test_add_and_load_alias(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.save_alias(
        Alias(name="rocky", user="root", host="rocky-server", default_path="/data/transfer")
    )

    loaded = ConfigStore(tmp_path / "config.json").get_alias("rocky")

    assert loaded == Alias(
        name="rocky",
        user="root",
        host="rocky-server",
        default_path="/data/transfer",
    )


def test_duplicate_alias_is_rejected(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    alias = Alias(name="rocky", user="root", host="rocky-server", default_path="/data")
    store.save_alias(alias)

    with pytest.raises(ConfigError, match="already exists"):
        store.save_alias(alias)


def test_invalid_config_is_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"aliases": {"rocky": {"user": "root"}}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid"):
        ConfigStore(path).list_aliases()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```text
python -m pytest tests/test_config.py -q
```

Expected: FAIL because `tscp.config` does not exist.

- [ ] **Step 3: Implement the JSON-backed store**

Create `src/tscp/config.py` with:

```python
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class Alias:
    name: str
    user: str
    host: str
    default_path: str
    port: int | None = None


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path

    def list_aliases(self) -> list[Alias]:
        data = self._read()
        try:
            return [
                Alias(name=name, **value)
                for name, value in data.get("aliases", {}).items()
            ]
        except (TypeError, ValueError) as exc:
            raise ConfigError("invalid alias configuration") from exc

    def get_alias(self, name: str) -> Alias:
        for alias in self.list_aliases():
            if alias.name == name:
                return alias
        raise ConfigError(f"unknown alias: {name}")

    def save_alias(self, alias: Alias, replace: bool = False) -> None:
        aliases = {item.name: asdict(item) for item in self.list_aliases()}
        if alias.name in aliases and not replace:
            raise ConfigError(f"alias already exists: {alias.name}")
        values = asdict(alias)
        values.pop("name")
        aliases[alias.name] = values
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"aliases": aliases}, indent=2) + "\n",
            encoding="utf-8",
        )

    def remove_alias(self, name: str) -> None:
        aliases = {item.name: asdict(item) for item in self.list_aliases()}
        if name not in aliases:
            raise ConfigError(f"unknown alias: {name}")
        del aliases[name]
        serialized = {}
        for key, value in aliases.items():
            value.pop("name", None)
            serialized[key] = {k: v for k, v in value.items() if v is not None}
        self.path.write_text(
            json.dumps({"aliases": serialized}, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read(self) -> dict:
        if not self.path.exists():
            return {"aliases": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"invalid configuration file: {self.path}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("aliases", {}), dict):
            raise ConfigError("invalid alias configuration")
        return data
```

The implementation must treat `None` ports as absent in JSON, preserve
existing aliases during updates, and never write secret material.

- [ ] **Step 4: Run the configuration tests**

Run:

```text
python -m pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/config.py tests/test_config.py
git commit -m "feat: persist Tailscale device aliases"
```

## Task 3: Resolve aliases and remote paths

**Files:**
- Create: `src/tscp/targets.py`
- Create: `tests/test_targets.py`

- [ ] **Step 1: Write failing resolver tests**

Create `tests/test_targets.py`:

```python
import pytest

from tscp.config import Alias
from tscp.errors import TargetError
from tscp.targets import resolve_remote, split_remote


def test_split_remote_requires_alias_and_path():
    assert split_remote("rocky:/data/report.zip") == ("rocky", "/data/report.zip")


def test_split_remote_rejects_local_path():
    with pytest.raises(TargetError, match="alias:/path"):
        split_remote("report.zip")


def test_resolve_remote_uses_user_host_and_default_path():
    alias = Alias("rocky", "root", "rocky-server", "/data/transfer")

    assert resolve_remote(alias, "/report.zip") == "root@rocky-server:/report.zip"
    assert resolve_remote(alias, "") == "root@rocky-server:/data/transfer"


def test_resolve_remote_includes_non_default_port():
    alias = Alias("rocky", "root", "rocky-server", "/data", port=2222)

    assert resolve_remote(alias, "/report.zip") == "root@rocky-server:/report.zip"
```

The port is returned separately by the command builder; it must not be encoded
into the remote path string.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```text
python -m pytest tests/test_targets.py -q
```

Expected: FAIL because `tscp.targets` does not exist.

- [ ] **Step 3: Implement pure target parsing**

Create `src/tscp/targets.py`:

```python
from .config import Alias
from .errors import TargetError


def split_remote(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise TargetError("remote path must use alias:/path syntax")
    alias_name, path = value.split(":", 1)
    if not alias_name or not path.startswith("/"):
        raise TargetError("remote path must use alias:/path syntax")
    return alias_name, path


def resolve_remote(alias: Alias, path: str) -> str:
    remote_path = path or alias.default_path
    if not remote_path.startswith("/"):
        raise TargetError("remote path must start with /")
    return f"{alias.user}@{alias.host}:{remote_path}"
```

- [ ] **Step 4: Run the resolver tests**

Run:

```text
python -m pytest tests/test_targets.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/targets.py tests/test_targets.py
git commit -m "feat: resolve alias-based remote paths"
```

## Task 4: Build and test the safe SCP runner

**Files:**
- Create: `src/tscp/transfer.py`
- Create: `tests/test_transfer.py`

- [ ] **Step 1: Write failing command-construction tests**

Create `tests/test_transfer.py`:

```python
from tscp.config import Alias
from tscp.transfer import build_scp_command


def test_send_command_uses_argument_list():
    alias = Alias("rocky", "root", "rocky-server", "/data", port=2222)

    assert build_scp_command(
        operation="send",
        alias=alias,
        source="C:\\Users\\me\\a file.txt",
        remote_path="/data/",
        recursive=False,
    ) == [
        "scp",
        "-P",
        "2222",
        "C:\\Users\\me\\a file.txt",
        "root@rocky-server:/data/",
    ]


def test_get_directory_adds_recursive_flag():
    alias = Alias("rocky", "root", "rocky-server", "/data")

    assert build_scp_command(
        operation="get",
        alias=alias,
        source="/data/archive",
        remote_path="C:\\tmp",
        recursive=True,
    ) == [
        "scp",
        "-r",
        "root@rocky-server:/data/archive",
        "C:\\tmp",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```text
python -m pytest tests/test_transfer.py -q
```

Expected: FAIL because `tscp.transfer` does not exist.

- [ ] **Step 3: Implement command construction and execution**

Create `src/tscp/transfer.py`:

```python
from pathlib import Path
import shutil
import subprocess

from .config import Alias
from .errors import TransferError
from .targets import resolve_remote


def build_scp_command(
    operation: str,
    alias: Alias,
    source: str,
    remote_path: str,
    recursive: bool,
) -> list[str]:
    command = ["scp"]
    if recursive:
        command.append("-r")
    if alias.port is not None:
        command.extend(["-P", str(alias.port)])
    if operation == "send":
        command.extend([source, resolve_remote(alias, remote_path)])
    elif operation == "get":
        command.extend([resolve_remote(alias, source), remote_path])
    else:
        raise ValueError(f"unsupported transfer operation: {operation}")
    return command


def run_transfer(command: list[str]) -> None:
    if shutil.which("scp") is None:
        raise TransferError("scp was not found; install OpenSSH and try again")
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        raise TransferError(f"could not start scp: {exc}") from exc
    if completed.returncode != 0:
        raise TransferError(f"scp failed with exit code {completed.returncode}")
```

Do not use `shell=True`, `os.system`, or a single interpolated command string.
The child process should inherit the terminal so SCP's normal progress output
and SSH prompts remain visible.

- [ ] **Step 4: Add subprocess failure coverage**

Append to `tests/test_transfer.py`:

```python
from unittest.mock import patch

import pytest

from tscp.errors import TransferError
from tscp.transfer import run_transfer


def test_run_transfer_reports_missing_scp():
    with patch("tscp.transfer.shutil.which", return_value=None):
        with pytest.raises(TransferError, match="scp was not found"):
            run_transfer(["scp", "source", "target"])


def test_run_transfer_reports_nonzero_exit():
    completed = type("Completed", (), {"returncode": 7})()
    with patch("tscp.transfer.shutil.which", return_value="scp"):
        with patch("tscp.transfer.subprocess.run", return_value=completed):
            with pytest.raises(TransferError, match="exit code 7"):
                run_transfer(["scp", "source", "target"])
```

- [ ] **Step 5: Run the transfer tests**

Run:

```text
python -m pytest tests/test_transfer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add src/tscp/transfer.py tests/test_transfer.py
git commit -m "feat: run safe SCP transfers"
```

## Task 5: Add the CLI commands

**Files:**
- Create: `src/tscp/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
from tscp.cli import main


def test_config_add_and_list(tmp_path, capsys):
    config = tmp_path / "config.json"

    assert main(["--config", str(config), "config", "add", "rocky",
                 "--user", "root", "--host", "rocky-server",
                 "--path", "/data"]) == 0
    assert main(["--config", str(config), "config", "list"]) == 0

    assert "rocky" in capsys.readouterr().out


def test_config_update_replaces_alias(tmp_path, capsys):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "old-host", "--path", "/data"])

    assert main(["--config", str(config), "config", "update", "rocky",
                 "--user", "root", "--host", "new-host",
                 "--path", "/new-data"]) == 0
    assert main(["--config", str(config), "config", "list"]) == 0
    assert "new-host" in capsys.readouterr().out


def test_send_resolves_alias_and_runs_scp(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "rocky-server", "--path", "/data"])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "send", "report.zip",
                 "rocky:/data/"]) == 0
    assert calls == [["scp", "report.zip", "root@rocky-server:/data/"]]


def test_get_resolves_alias_and_runs_scp(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "rocky-server", "--path", "/data"])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "get", "rocky:/data/report.zip",
                 "downloaded.zip"]) == 0
    assert calls == [["scp", "root@rocky-server:/data/report.zip", "downloaded.zip"]]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```text
python -m pytest tests/test_cli.py -q
```

Expected: FAIL because `tscp.cli` does not exist.

- [ ] **Step 3: Implement the argparse CLI**

Create `src/tscp/cli.py` with these interfaces:

```python
import argparse
from pathlib import Path
import sys

from .config import Alias, ConfigStore
from .errors import TscpError
from .targets import split_remote
from .transfer import build_scp_command, run_transfer


def default_config_path() -> Path:
    return Path.home() / ".config" / "tscp" / "config.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tscp")
    parser.add_argument("--config", type=Path, default=default_config_path())
    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    add = config_commands.add_parser("add")
    add.add_argument("name")
    add.add_argument("--user", required=True)
    add.add_argument("--host", required=True)
    add.add_argument("--path", default="/")
    add.add_argument("--port", type=int)
    update = config_commands.add_parser("update")
    update.add_argument("name")
    update.add_argument("--user", required=True)
    update.add_argument("--host", required=True)
    update.add_argument("--path", default="/")
    update.add_argument("--port", type=int)
    config_commands.add_parser("list")
    remove = config_commands.add_parser("remove")
    remove.add_argument("name")

    send = commands.add_parser("send")
    send.add_argument("source")
    send.add_argument("destination")
    send.add_argument("-r", "--recursive", action="store_true")
    get = commands.add_parser("get")
    get.add_argument("source")
    get.add_argument("destination")
    get.add_argument("-r", "--recursive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ConfigStore(args.config)
    try:
        if args.command == "config":
            return _handle_config(args, store)
        return _handle_transfer(args, store)
    except TscpError as exc:
        print(f"tscp: {exc}", file=sys.stderr)
        return 2


def _handle_config(args: argparse.Namespace, store: ConfigStore) -> int:
    if args.config_command in {"add", "update"}:
        store.save_alias(
            Alias(args.name, args.user, args.host, args.path, args.port),
            replace=args.config_command == "update",
        )
        print(f"{args.config_command}d alias: {args.name}")
    elif args.config_command == "list":
        for alias in store.list_aliases():
            port = f":{alias.port}" if alias.port else ""
            print(f"{alias.name}\t{alias.user}@{alias.host}{port}\t{alias.default_path}")
    else:
        store.remove_alias(args.name)
        print(f"removed alias: {args.name}")
    return 0


def _handle_transfer(args: argparse.Namespace, store: ConfigStore) -> int:
    remote_value = args.destination if args.command == "send" else args.source
    alias_name, remote_path = split_remote(remote_value)
    alias = store.get_alias(alias_name)
    transfer_source = args.source if args.command == "send" else remote_path
    transfer_destination = remote_path if args.command == "send" else args.destination
    command = build_scp_command(
        args.command,
        alias,
        transfer_source,
        transfer_destination,
        args.recursive,
    )
    run_transfer(command)
    return 0
```

The CLI must keep `argparse` usage errors standard, print expected operational
errors to stderr, and return nonzero for configuration, parsing, or SCP
failures.

- [ ] **Step 4: Run the CLI tests**

Run:

```text
python -m pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the full unit suite**

Run:

```text
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```text
git add src/tscp/cli.py tests/test_cli.py
git commit -m "feat: add alias-based tscp CLI"
```

## Task 6: Document installation and perform platform validation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Document prerequisites and commands**

Document these exact requirements and examples:

```text
Prerequisites:
- Python 3.10 or newer
- Tailscale connected on both machines
- MagicDNS enabled, or a resolvable Tailscale hostname
- OpenSSH client (`scp`) installed
- SSH public-key authentication configured

Install:
python -m pip install .

Configure:
tscp config add rocky --user root --host rocky-server --path /data/transfer

Transfer:
tscp send ./report.zip rocky:/data/transfer/
tscp get rocky:/data/transfer/report.zip ./
tscp send -r ./folder rocky:/data/transfer/
```

Explain that the tool does not store passwords or keys and that `host` should
be the MagicDNS hostname, not a manually copied IP.

- [ ] **Step 2: Validate the installed CLI on Windows**

Run from PowerShell:

```text
python -m pip install .
tscp --help
tscp config add rocky --user <ssh-user> --host <magicdns-host> --path /data/transfer
tscp config list
```

Expected: help renders, the alias is listed, and no IP lookup is required.
Run a real `tscp send` and `tscp get` only after SSH connectivity is confirmed
with `ssh <ssh-user>@<magicdns-host>`.

- [ ] **Step 3: Validate on Rocky Linux**

Run:

```text
python3 -m pip install .
tscp config add windows --user <ssh-user> --host <magicdns-host> --path /tmp/transfer
tscp config list
tscp send ./report.txt windows:/tmp/transfer/
tscp get windows:/tmp/transfer/report.txt ./downloaded-report.txt
```

Expected: both transfers complete through the Tailscale hostname and the
downloaded file matches the source.

- [ ] **Step 4: Commit documentation**

```text
git add README.md
git commit -m "docs: explain Tailscale SCP setup"
```

## Final verification checklist

- [ ] `python -m pytest -q` passes.
- [ ] `python -m pip install .` succeeds on Windows and Rocky Linux.
- [ ] `tscp config list` displays aliases without secrets.
- [ ] A Windows-to-Rocky upload succeeds using a MagicDNS hostname.
- [ ] A Rocky-to-Windows download succeeds using a MagicDNS hostname.
- [ ] Missing aliases, missing `scp`, invalid paths, and SSH failures produce
      nonzero exit codes and actionable stderr messages.
