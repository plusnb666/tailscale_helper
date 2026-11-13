import pytest

from tscp.config import Alias
from tscp.errors import TargetError
from tscp.targets import resolve_remote, split_remote


def test_split_remote_requires_alias_and_path():
    assert split_remote("rocky:/data/report.zip") == ("rocky", "/data/report.zip")


def test_split_remote_rejects_local_path():
    with pytest.raises(TargetError, match="alias:/path"):
        split_remote("report.zip")


def test_resolve_remote_uses_user_host_and_default_path():
    alias = Alias("rocky", "root", "rocky-server", "/data/transfer")

    assert resolve_remote(alias, "/report.zip") == "root@rocky-server:/report.zip"
    assert resolve_remote(alias, "") == "root@rocky-server:/data/transfer"


def test_resolve_remote_includes_non_default_port():
    alias = Alias("rocky", "root", "rocky-server", "/data", port=2222)

    assert resolve_remote(alias, "/report.zip") == "root@rocky-server:/report.zip"
