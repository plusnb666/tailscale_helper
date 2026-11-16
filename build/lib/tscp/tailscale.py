from dataclasses import dataclass
import json
import shutil
import subprocess

from .errors import TscpError


@dataclass(frozen=True)
class TailscaleDevice:
    name: str
    dns_name: str
    online: bool
    operating_system: str


def discover_devices() -> list[TailscaleDevice]:
    if shutil.which("tailscale") is None:
        raise TscpError(
            "tailscale was not found; install Tailscale or use a configured alias"
        )
    try:
        completed = subprocess.run(
            ["tailscale", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise TscpError(f"could not start tailscale: {exc}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise TscpError(f"tailscale status failed: {message}")
    try:
        payload = json.loads(completed.stdout)
        records = [payload["Self"], *payload.get("Peer", {}).values()]
        return [_device_from_record(record) for record in records]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TscpError("tailscale returned invalid status JSON") from exc


def find_device(devices: list[TailscaleDevice], value: str) -> TailscaleDevice:
    normalized = value.rstrip(".").lower()
    matches = [
        device
        for device in devices
        if normalized in {device.name.lower(), device.dns_name.rstrip(".").lower()}
    ]
    if not matches:
        available = ", ".join(device.name for device in devices) or "none"
        raise TscpError(f"device not found: {value}; available devices: {available}")
    if len(matches) > 1:
        raise TscpError(f"device name is ambiguous: {value}")
    return matches[0]


def _device_from_record(record: dict) -> TailscaleDevice:
    dns_name = str(record["DNSName"]).rstrip(".")
    return TailscaleDevice(
        name=str(record["HostName"]),
        dns_name=dns_name,
        online=bool(record["Online"]),
        operating_system=str(record.get("OS", "unknown")),
    )
