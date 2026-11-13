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
