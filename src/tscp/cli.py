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
