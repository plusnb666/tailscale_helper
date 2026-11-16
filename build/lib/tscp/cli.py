import argparse
from pathlib import Path
import sys

from .config import Alias, ConfigStore
from .completion import render_bash, render_powershell, shell_candidates
from .errors import TscpError, UnknownAliasError
from .targets import split_remote, split_send_target
from .tailscale import discover_devices, find_device
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

    device = commands.add_parser("device")
    device_commands = device.add_subparsers(dest="device_command", required=True)
    device_commands.add_parser("list")

    completion = commands.add_parser("completion")
    completion_commands = completion.add_subparsers(
        dest="completion_command", required=True
    )
    completion_commands.add_parser("powershell")
    completion_commands.add_parser("bash")
    candidates = completion_commands.add_parser(
        "candidates", help=argparse.SUPPRESS
    )
    candidates.add_argument("--shell", choices=("powershell", "bash"), required=True)

    send = commands.add_parser("send")
    send.add_argument("source")
    send.add_argument("destination")
    send.add_argument("-r", "--recursive", action="store_true")
    send.add_argument("--user")
    get = commands.add_parser("get")
    get.add_argument("source")
    get.add_argument("destination")
    get.add_argument("-r", "--recursive", action="store_true")
    get.add_argument("--user")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ConfigStore(args.config)
    try:
        if args.command == "config":
            return _handle_config(args, store)
        if args.command == "device":
            return _handle_device(args)
        if args.command == "completion":
            return _handle_completion(args, store)
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
        verb = "added" if args.config_command == "add" else "updated"
        print(f"{verb} alias: {args.name}")
    elif args.config_command == "list":
        for alias in store.list_aliases():
            port = f":{alias.port}" if alias.port else ""
            print(f"{alias.name}\t{alias.user}@{alias.host}{port}\t{alias.default_path}")
    else:
        store.remove_alias(args.name)
        print(f"removed alias: {args.name}")
    return 0


def _handle_device(args: argparse.Namespace) -> int:
    if args.device_command == "list":
        for device in discover_devices():
            state = "online" if device.online else "offline"
            print(f"{device.name}\t{device.dns_name}\t{device.operating_system}\t{state}")
    return 0


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
