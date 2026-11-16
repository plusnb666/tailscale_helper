# Default Transfer Path Implementation Plan

> **For agentic workers:** REQUIRED: Load and follow `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow `tscp send FILE HOST` to use a configured alias's default remote directory while preserving explicit `HOST:/path` transfers.

**Architecture:** Keep remote parsing explicit by adding a send-only parser that accepts either a bare host or `host:/path`; keep download parsing strict because downloads need an explicit remote source path. Reuse the existing alias resolver, `resolve_remote`, and SCP command builder. Validate default directories when aliases are saved so malformed configuration cannot silently produce invalid targets.

**Tech Stack:** Python 3.10+, standard library, pytest, existing alias configuration and SCP transfer modules.

---

## File map

- Modify: `src/tscp/targets.py` — add send-target parsing for bare hosts and explicit paths.
- Modify: `tests/test_targets.py` — test bare host, explicit path, and invalid target behavior.
- Modify: `src/tscp/config.py` — reject aliases whose default path is not absolute.
- Modify: `tests/test_config.py` — test default-path validation.
- Modify: `src/tscp/cli.py` — use the send parser only for `send`; keep `get` strict.
- Modify: `tests/test_cli.py` — test default-directory sends and path overrides.
- Modify: `README.md` — document configuring and using a default directory in Chinese and English.

## Task 1: Parse bare send hosts and validate default paths

**Files:**
- Modify: `src/tscp/targets.py`
- Modify: `tests/test_targets.py`
- Modify: `src/tscp/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing target and configuration tests**

Append to `tests/test_targets.py`:

```python
from tscp.targets import split_send_target


def test_split_send_target_accepts_bare_host():
    assert split_send_target("linux") == ("linux", "")


def test_split_send_target_accepts_explicit_path():
    assert split_send_target("linux:/tmp/files") == ("linux", "/tmp/files")


def test_split_send_target_rejects_empty_host():
    with pytest.raises(TargetError, match="host"):
        split_send_target("")


def test_split_send_target_rejects_relative_path():
    with pytest.raises(TargetError, match="absolute"):
        split_send_target("linux:relative/path")
```

Append to `tests/test_config.py`:

```python
def test_save_alias_rejects_relative_default_path(tmp_path):
    store = ConfigStore(tmp_path / "config.json")

    with pytest.raises(ConfigError, match="absolute"):
        store.save_alias(
            Alias(
                name="linux",
                user="nbplus",
                host="linux",
                default_path="Downloads",
            )
        )
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_targets.py tests/test_config.py -q
```

Expected: FAIL because `split_send_target` and default-path validation do not
exist.

- [ ] **Step 3: Implement parsing and validation**

In `src/tscp/targets.py`, add:

```python
def split_send_target(value: str) -> tuple[str, str]:
    if not value:
        raise TargetError("send target must contain a host")
    if ":" not in value:
        return value, ""
    host, path = value.split(":", 1)
    if not host:
        raise TargetError("send target must contain a host")
    if not path.startswith("/"):
        raise TargetError("send target path must be absolute")
    return host, path
```

Keep `split_remote` unchanged so `get` continues to require `alias:/path`.

In `src/tscp/config.py`, add validation before writing an alias:

```python
if not alias.default_path.startswith("/"):
    raise ConfigError("default path must be absolute")
```

The validation must run for both new aliases and replacements.

- [ ] **Step 4: Run focused tests**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_targets.py tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/targets.py tests/test_targets.py src/tscp/config.py tests/test_config.py
git commit -m "feat: support bare send hosts and validate paths"
```

## Task 2: Use alias default directories for sends

**Files:**
- Modify: `src/tscp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
def test_send_bare_alias_uses_configured_default_path(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "send", "test.zip", "linux"]) == 0
    assert calls == [[
        "scp",
        "test.zip",
        "nbplus@linux:/home/user/nbplus/Downloads",
    ]]


def test_send_explicit_path_overrides_default_path(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main([
        "--config", str(config), "send", "test.zip", "linux:/tmp",
    ]) == 0
    assert calls == [["scp", "test.zip", "nbplus@linux:/tmp"]]


def test_get_requires_explicit_remote_path(tmp_path, capsys):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])

    assert main(["--config", str(config), "get", "linux", "."]) == 2
    assert "alias:/path" in capsys.readouterr().err
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_cli.py -q
```

Expected: FAIL because `_handle_transfer` currently requires `alias:/path`
for both send and get.

- [ ] **Step 3: Update transfer target parsing**

In `src/tscp/cli.py`, import `split_send_target` and change
`_handle_transfer` to branch by operation:

```python
def _handle_transfer(args: argparse.Namespace, store: ConfigStore) -> int:
    if args.command == "send":
        alias_name, remote_path = split_send_target(args.destination)
        alias = _resolve_alias(alias_name, store, args.user)
        transfer_source = args.source
        transfer_destination = remote_path
    else:
        alias_name, remote_path = split_remote(args.source)
        alias = _resolve_alias(alias_name, store, args.user)
        transfer_source = remote_path
        transfer_destination = args.destination

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

`build_scp_command` already delegates an empty send path to
`resolve_remote`, which uses `alias.default_path`; do not duplicate that
fallback in the CLI.

- [ ] **Step 4: Run CLI and full tests**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_cli.py -q
& "$HOME\miniconda3\python.exe" -m pytest -q
```

Expected: all tests PASS, including existing alias and discovery tests.

- [ ] **Step 5: Commit**

```text
git add src/tscp/cli.py tests/test_cli.py
git commit -m "feat: use alias default paths for sends"
```

## Task 3: Document and validate the default directory workflow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add bilingual documentation**

Add:

```text
## Default transfer directory / 默认传输目录

Configure a host with its default remote directory:

配置主机及其默认远程目录：

tscp config add linux --user nbplus --host linux --path /home/user/nbplus/Downloads

Send using only the host name:

发送时只写主机名：

tscp send .\test.zip linux

Override the default for one transfer:

单次传输可以覆盖默认目录：

tscp send .\test.zip linux:/tmp

The bare-host form uses the configured alias default path. Download commands
still use `host:/path` because the remote source file must be explicit.

仅主机名格式会使用 alias 配置的默认目录。下载命令仍使用 `host:/path`，
因为远程源文件必须明确指定。
```

- [ ] **Step 2: Run final validation**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest -q
& "$HOME\miniconda3\python.exe" -m pip install .
& "$HOME\miniconda3\Scripts\tscp.exe" --config "$env:TEMP\tscp-default-path.json" config add linux --user nbplus --host linux --path /home/user/nbplus/Downloads
& "$HOME\miniconda3\Scripts\tscp.exe" --config "$env:TEMP\tscp-default-path.json" config list
Remove-Item "$env:TEMP\tscp-default-path.json" -ErrorAction SilentlyContinue
```

Expected: tests pass, installation succeeds, and `config list` shows the
configured Linux alias and default directory.

- [ ] **Step 3: Commit documentation**

```text
git add README.md
git commit -m "docs: explain default transfer directories"
```

## Final verification checklist

- [ ] `tscp send FILE linux` uses Linux alias `default_path`.
- [ ] `tscp send FILE linux:/tmp` overrides the default path.
- [ ] `tscp get linux DEST` remains invalid.
- [ ] Relative default directories are rejected.
- [ ] Existing explicit-path, alias, and discovery transfers pass.
- [ ] README documents the workflow in Chinese and English.
- [ ] `python -m pytest -q` passes.
