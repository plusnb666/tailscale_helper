from tscp.cli import main


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
