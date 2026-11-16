from tscp.cli import main
from tscp.errors import TscpError
from tscp.tailscale import TailscaleDevice


def test_config_add_and_list(tmp_path, capsys):
    config = tmp_path / "config.json"

    assert main(["--config", str(config), "config", "add", "rocky",
                 "--user", "root", "--host", "rocky-server",
                 "--path", "/data"]) == 0
    assert main(["--config", str(config), "config", "list"]) == 0

    assert "rocky" in capsys.readouterr().out


def test_config_update_replaces_alias(tmp_path, capsys):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "old-host", "--path", "/data"])

    assert main(["--config", str(config), "config", "update", "rocky",
                 "--user", "root", "--host", "new-host",
                 "--path", "/new-data"]) == 0
    assert main(["--config", str(config), "config", "list"]) == 0
    assert "new-host" in capsys.readouterr().out


def test_send_resolves_alias_and_runs_scp(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "rocky-server", "--path", "/data"])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "send", "report.zip",
                 "rocky:/data/"]) == 0
    assert calls == [["scp", "report.zip", "root@rocky-server:/data/"]]


def test_get_resolves_alias_and_runs_scp(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main(["--config", str(config), "config", "add", "rocky",
          "--user", "root", "--host", "rocky-server", "--path", "/data"])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "get", "rocky:/data/report.zip",
                 "downloaded.zip"]) == 0
    assert calls == [["scp", "root@rocky-server:/data/report.zip", "downloaded.zip"]]


def test_device_list_prints_discovered_devices(monkeypatch, capsys):
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [
            TailscaleDevice(
                "rocky-server", "rocky-server.tail123.ts.net", True, "linux"
            )
        ],
    )

    assert main(["device", "list"]) == 0
    output = capsys.readouterr().out
    assert "rocky-server" in output
    assert "online" in output


def test_send_discovers_unknown_device_with_user(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    calls = []
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [
            TailscaleDevice(
                "rocky-server", "rocky-server.tail123.ts.net", True, "linux"
            )
        ],
    )
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main([
        "--config", str(config), "send", "report.zip", "rocky-server:/data/",
        "--user", "root",
    ]) == 0
    assert calls == [[
        "scp", "report.zip", "root@rocky-server.tail123.ts.net:/data/",
    ]]


def test_discovery_transfer_requires_user(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.json"
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [
            TailscaleDevice(
                "rocky-server", "rocky-server.tail123.ts.net", True, "linux"
            )
        ],
    )

    assert main([
        "--config", str(config), "send", "report.zip", "rocky-server:/data/"
    ]) == 2
    assert "--user" in capsys.readouterr().err


def test_completion_powershell_prints_script(capsys):
    assert main(["completion", "powershell"]) == 0
    assert "Register-ArgumentCompleter" in capsys.readouterr().out


def test_completion_bash_prints_script(capsys):
    assert main(["completion", "bash"]) == 0
    assert "complete -F" in capsys.readouterr().out


def test_completion_candidates_prints_aliases_and_devices(
    tmp_path, monkeypatch, capsys
):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "rocky",
        "--user", "root", "--host", "rocky-server", "--path", "/data",
    ])
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: [
            TailscaleDevice(
                "rocky-server", "rocky-server.tail123.ts.net", True, "linux"
            )
        ],
    )

    assert main([
        "--config", str(config), "completion", "candidates",
        "--shell", "powershell",
    ]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "rocky" in output
    assert "rocky-server" in output
    assert "rocky-server.tail123.ts.net" in output


def test_completion_candidates_survives_tailscale_failure(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        "tscp.cli.discover_devices",
        lambda: (_ for _ in ()).throw(TscpError("tailscale unavailable")),
    )

    assert main([
        "--config", str(tmp_path / "config.json"), "completion", "candidates",
        "--shell", "bash",
    ]) == 0
    assert "config" in capsys.readouterr().out.splitlines()


def test_send_bare_alias_uses_configured_default_path(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main(["--config", str(config), "send", "test.zip", "linux"]) == 0
    assert calls == [[
        "scp",
        "test.zip",
        "nbplus@linux:/home/user/nbplus/Downloads",
    ]]


def test_send_explicit_path_overrides_default_path(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])
    calls = []
    monkeypatch.setattr("tscp.cli.run_transfer", lambda command: calls.append(command))

    assert main([
        "--config", str(config), "send", "test.zip", "linux:/tmp",
    ]) == 0
    assert calls == [["scp", "test.zip", "nbplus@linux:/tmp"]]


def test_get_requires_explicit_remote_path(tmp_path, capsys):
    config = tmp_path / "config.json"
    main([
        "--config", str(config), "config", "add", "linux",
        "--user", "nbplus", "--host", "linux",
        "--path", "/home/user/nbplus/Downloads",
    ])

    assert main(["--config", str(config), "get", "linux", "."]) == 2
    assert "alias:/path" in capsys.readouterr().err
