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
