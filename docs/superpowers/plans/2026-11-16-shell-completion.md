# Shell Tab Completion Implementation Plan

> **For agentic workers:** REQUIRED: Load and follow `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PowerShell and Bash completion script generation with static command completion and dynamic alias/Tailscale device candidates.

**Architecture:** Add a pure completion module that renders shell-specific scripts from one shared command vocabulary. The generated scripts invoke a lightweight `tscp completion candidates` command at Tab time; that command reads local aliases and Tailscale status without exposing secrets. The existing CLI behavior remains unchanged.

**Tech Stack:** Python 3.10+, `argparse`, `json`, `shlex`, existing `ConfigStore` and Tailscale discovery module, pytest, PowerShell `Register-ArgumentCompleter`, and Bash `complete`.

---

## File map

- Create: `src/tscp/completion.py` — shared candidates, PowerShell/Bash rendering, and shell validation.
- Create: `tests/test_completion.py` — rendering, escaping, candidate, and unsupported-shell tests.
- Modify: `src/tscp/cli.py` — add `completion powershell`, `completion bash`, and hidden/internal `completion candidates`.
- Modify: `tests/test_cli.py` — test CLI script output and candidate output.
- Modify: `README.md` — document enabling completion in PowerShell and Bash in both languages.

## Task 1: Implement safe completion script generation

**Files:**
- Create: `src/tscp/completion.py`
- Create: `tests/test_completion.py`

- [ ] **Step 1: Write failing renderer and escaping tests**

Create `tests/test_completion.py`:

```python
import pytest

from tscp.completion import (
    BASH_COMMANDS,
    POWERSHELL_COMMANDS,
    render_bash,
    render_powershell,
    shell_candidates,
)


def test_powershell_script_registers_completer_and_static_commands():
    script = render_powershell()

    assert "Register-ArgumentCompleter" in script
    for command in POWERSHELL_COMMANDS:
        assert command in script
    assert "tscp completion candidates" in script


def test_bash_script_registers_completer_and_static_commands():
    script = render_bash()

    assert "complete -F" in script
    for command in BASH_COMMANDS:
        assert command in script
    assert "tscp completion candidates" in script


def test_shell_candidates_combines_aliases_and_devices():
    aliases = ["rocky"]
    devices = ["rocky-server", "laptop.tail123.ts.net"]

    assert shell_candidates(aliases, devices) == [
        "config",
        "device",
        "send",
        "get",
        "completion",
        "--config",
        "--user",
        "--path",
        "--port",
        "--recursive",
        "rocky",
        "rocky-server",
        "laptop.tail123.ts.net",
    ]


def test_shell_candidates_removes_duplicates():
    assert shell_candidates(["rocky"], ["rocky"]) == [
        "config",
        "device",
        "send",
        "get",
        "completion",
        "--config",
        "--user",
        "--path",
        "--port",
        "--recursive",
        "rocky",
    ]


def test_renderers_escape_shell_sensitive_candidate_values():
    script = render_powershell()
    assert "Invoke-Expression" not in script
    assert "Get-Content" not in script


def test_unknown_shell_is_rejected():
    with pytest.raises(ValueError, match="unsupported shell"):
        shell_candidates([], [], shell="zsh")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_completion.py -q
```

Expected: FAIL because `tscp.completion` does not exist.

- [ ] **Step 3: Implement the completion module**

Create `src/tscp/completion.py`:

```python
from collections.abc import Iterable


POWERSHELL_COMMANDS = ("config", "device", "send", "get", "completion")
BASH_COMMANDS = POWERSHELL_COMMANDS
OPTIONS = ("--config", "--user", "--path", "--port", "--recursive")


def shell_candidates(
    aliases: Iterable[str],
    devices: Iterable[str],
    shell: str = "powershell",
) -> list[str]:
    if shell not in {"powershell", "bash"}:
        raise ValueError(f"unsupported shell: {shell}")
    values = [*POWERSHELL_COMMANDS, *OPTIONS]
    for value in [*aliases, *devices]:
        if value not in values:
            values.append(value)
    return values


def render_powershell() -> str:
    return r'''Register-ArgumentCompleter -Native -CommandName tscp -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $static = @('config', 'device', 'send', 'get', 'completion', '--config', '--user', '--path', '--port', '--recursive')
    $dynamic = @()
    try {
        $dynamic = & tscp completion candidates --shell powershell 2>$null
    } catch {
        $dynamic = @()
    }
    ($static + $dynamic | Sort-Object -Unique) |
        Where-Object { $_ -like "$wordToComplete*" } |
        ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
}'''


def render_bash() -> str:
    return r'''_tscp_completion() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local static="config device send get completion --config --user --path --port --recursive"
    local dynamic
    dynamic="$(tscp completion candidates --shell bash 2>/dev/null || true)"
    COMPREPLY=( $(compgen -W "$static $dynamic" -- "$cur") )
}
complete -F _tscp_completion tscp'''
```

The renderer must keep dynamic values outside the generated script. Dynamic
values are returned at runtime by the candidate command, one value per line,
and must exclude values containing carriage returns or newlines.

- [ ] **Step 4: Run completion module tests**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_completion.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/tscp/completion.py tests/test_completion.py
git commit -m "feat: generate shell completion scripts"
```

## Task 2: Add completion commands and dynamic candidates

**Files:**
- Modify: `src/tscp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
def test_completion_powershell_prints_script(capsys):
    assert main(["completion", "powershell"]) == 0
    assert "Register-ArgumentCompleter" in capsys.readouterr().out


def test_completion_bash_prints_script(capsys):
    assert main(["completion", "bash"]) == 0
    assert "complete -F" in capsys.readouterr().out


def test_completion_candidates_prints_aliases_and_devices(
    tmp_path, monkeypatch, capsys
):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "rocky",
        "--user", "root", "--host", "rocky-server", "--path", "/data",
    ])
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [
            TailscaleDevice(
                "rocky-server", "rocky-server.tail123.ts.net", True, "linux"
            )
        ],
    )

    assert main([
        "--config", str(config), "completion", "candidates",
        "--shell", "powershell",
    ]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "rocky" in output
    assert "rocky-server" in output
    assert "rocky-server.tail123.ts.net" in output


def test_completion_candidates_survives_tailscale_failure(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: (_ for _ in ()).throw(TscpError("tailscale unavailable")),
    )

    assert main([
        "--config", str(tmp_path / "config.json"), "completion", "candidates",
        "--shell", "bash",
    ]) == 0
    assert "config" in capsys.readouterr().out.splitlines()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest tests/test_cli.py -q
```

Expected: FAIL because the CLI has no completion subcommands.

- [ ] **Step 3: Extend `cli.py`**

Import `render_bash`, `render_powershell`, and `shell_candidates`. Add this
parser structure:

```python
completion = commands.add_parser("completion")
completion_commands = completion.add_subparsers(
    dest="completion_command", required=True
)
completion_commands.add_parser("powershell")
completion_commands.add_parser("bash")
candidates = completion_commands.add_parser("candidates", help=argparse.SUPPRESS)
candidates.add_argument("--shell", choices=("powershell", "bash"), required=True)
```

Handle completion before transfer handling:

```python
def _handle_completion(args: argparse.Namespace, store: ConfigStore) -> int:
    if args.completion_command == "powershell":
        print(render_powershell())
        return 0
    if args.completion_command == "bash":
        print(render_bash())
        return 0

    aliases = [alias.name for alias in store.list_aliases()]
    devices = []
    try:
        discovered = discover_devices()
    except TscpError:
        discovered = []
    for device in discovered:
        devices.extend((device.name, device.dns_name))
    for value in shell_candidates(aliases, devices, shell=args.shell):
        if "\r" not in value and "\n" not in value:
            print(value)
    return 0
```

In `main()`, dispatch `args.command == "completion"` to
`_handle_completion(args, store)`. The script-generation commands must not
read the configuration or invoke Tailscale; only `candidates` does so.
Discovery failures for candidates are intentionally treated as no dynamic
devices, while static candidates still print.

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
git commit -m "feat: add completion CLI commands"
```

## Task 3: Document and validate shell completion

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add bilingual README documentation**

Add:

```text
## Tab completion / Tab 自动补全

PowerShell:
tscp completion powershell | Out-String | Invoke-Expression

Bash:
eval "$(tscp completion bash)"

The completion script provides static commands and dynamically suggests saved
aliases plus Tailscale device names. Dynamic candidates are queried when Tab
is pressed. If Tailscale is unavailable, static completion still works.

补全脚本提供静态命令，并动态提示已保存的 alias 和 Tailscale 设备名。
动态候选会在按下 Tab 时查询。如果 Tailscale 不可用，静态补全仍然可用。
```

Explain that the PowerShell command applies to the current session and can be
added to the user's PowerShell profile for persistence; Bash can be added to
`~/.bashrc`.

- [ ] **Step 2: Validate generated scripts and installed CLI**

Run:

```text
& "$HOME\miniconda3\python.exe" -m pytest -q
& "$HOME\miniconda3\python.exe" -m pip install .
& "$HOME\miniconda3\Scripts\tscp.exe" completion powershell
& "$HOME\miniconda3\Scripts\tscp.exe" completion bash
& "$HOME\miniconda3\Scripts\tscp.exe" completion candidates --shell powershell
```

Expected: all tests pass, installation succeeds, both scripts contain their
shell registration code, and candidate output contains command names plus any
available alias/device names.

- [ ] **Step 3: Commit documentation**

```text
git add README.md
git commit -m "docs: explain shell tab completion"
```

## Final verification checklist

- [ ] PowerShell script uses `Register-ArgumentCompleter`.
- [ ] Bash script uses `complete -F`.
- [ ] Static commands and options are available.
- [ ] Configured aliases and discovered Tailscale names are candidates.
- [ ] Tailscale failures do not remove static candidates.
- [ ] Generated scripts do not contain passwords, private keys, or config contents.
- [ ] `python -m pytest -q` passes.
