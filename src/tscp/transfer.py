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
