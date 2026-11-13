from unittest.mock import patch

import pytest

from tscp.config import Alias
from tscp.errors import TransferError
from tscp.transfer import build_scp_command, run_transfer


def test_send_command_uses_argument_list():
    alias = Alias("rocky", "root", "rocky-server", "/data", port=2222)

    assert build_scp_command(
        operation="send",
        alias=alias,
        source="C:\\Users\\me\\a file.txt",
        remote_path="/data/",
        recursive=False,
    ) == [
        "scp",
        "-P",
        "2222",
        "C:\\Users\\me\\a file.txt",
        "root@rocky-server:/data/",
    ]


def test_get_directory_adds_recursive_flag():
    alias = Alias("rocky", "root", "rocky-server", "/data")

    assert build_scp_command(
        operation="get",
        alias=alias,
        source="/data/archive",
        remote_path="C:\\tmp",
        recursive=True,
    ) == [
        "scp",
        "-r",
        "root@rocky-server:/data/archive",
        "C:\\tmp",
    ]


def test_run_transfer_reports_missing_scp():
    with patch("tscp.transfer.shutil.which", return_value=None):
        with pytest.raises(TransferError, match="scp was not found"):
            run_transfer(["scp", "source", "target"])


def test_run_transfer_reports_nonzero_exit():
    completed = type("Completed", (), {"returncode": 7})()
    with patch("tscp.transfer.shutil.which", return_value="scp"):
        with patch("tscp.transfer.subprocess.run", return_value=completed):
            with pytest.raises(TransferError, match="exit code 7"):
                run_transfer(["scp", "source", "target"])
