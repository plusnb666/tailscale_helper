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
