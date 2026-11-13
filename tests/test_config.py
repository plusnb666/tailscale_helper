from tscp import __version__
import json

import pytest

from tscp.config import Alias, ConfigStore
from tscp.errors import ConfigError


def test_package_exposes_version():
    assert __version__ == "0.1.0"


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
    assert "port" not in json.loads(
        (tmp_path / "config.json").read_text(encoding="utf-8")
    )["aliases"]["rocky"]


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
