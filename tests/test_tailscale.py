import json
from unittest.mock import patch

import pytest

from tscp.errors import TscpError
from tscp.tailscale import TailscaleDevice, discover_devices, find_device


STATUS = {
    "BackendState": "Running",
    "MagicDNSSuffix": "tail123.ts.net",
    "Self": {
        "HostName": "laptop",
        "DNSName": "laptop.tail123.ts.net.",
        "Online": True,
        "OS": "windows",
    },
    "Peer": {
        "node-1": {
            "HostName": "rocky-server",
            "DNSName": "rocky-server.tail123.ts.net.",
            "Online": True,
            "OS": "linux",
        },
        "node-2": {
            "HostName": "phone",
            "DNSName": "phone.tail123.ts.net.",
            "Online": False,
            "OS": "android",
        },
    },
}


def test_discover_devices_includes_self_and_peers():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps(STATUS),
                "stderr": "",
            })(),
        ):
            devices = discover_devices()

    assert devices == [
        TailscaleDevice("laptop", "laptop.tail123.ts.net", True, "windows"),
        TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux"),
        TailscaleDevice("phone", "phone.tail123.ts.net", False, "android"),
    ]


def test_find_device_matches_short_name_and_magicdns_name():
    devices = [
        TailscaleDevice("rocky-server", "rocky-server.tail123.ts.net", True, "linux")
    ]

    assert find_device(devices, "rocky-server") == devices[0]
    assert find_device(devices, "rocky-server.tail123.ts.net.") == devices[0]


def test_find_device_reports_unknown_name():
    with pytest.raises(TscpError, match="device not found"):
        find_device([], "missing")


def test_find_device_reports_ambiguous_name():
    devices = [
        TailscaleDevice("rocky", "rocky.tail123.ts.net", True, "linux"),
        TailscaleDevice("rocky", "rocky-alt.tail123.ts.net", True, "linux"),
    ]

    with pytest.raises(TscpError, match="ambiguous"):
        find_device(devices, "rocky")


def test_missing_tailscale_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value=None):
        with pytest.raises(TscpError, match="tailscale was not found"):
            discover_devices()


def test_invalid_status_json_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 0,
                "stdout": "{not-json",
                "stderr": "",
            })(),
        ):
            with pytest.raises(TscpError, match="invalid status JSON"):
                discover_devices()


def test_failed_status_command_is_reported():
    with patch("tscp.tailscale.shutil.which", return_value="tailscale"):
        with patch(
            "tscp.tailscale.subprocess.run",
            return_value=type("Completed", (), {
                "returncode": 1,
                "stdout": "",
                "stderr": "Tailscale is stopped",
            })(),
        ):
            with pytest.raises(TscpError, match="status failed"):
                discover_devices()
