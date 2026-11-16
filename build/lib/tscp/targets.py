from .config import Alias
from .errors import TargetError


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
