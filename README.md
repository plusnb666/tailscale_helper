# Tailscale SCP Helper

`tscp` is a small command-line tool for transferring files over a Tailscale
network with SCP. Configure a device's MagicDNS hostname once, then use a
friendly alias instead of looking up a Tailscale IP for every transfer.

`tscp` 是一个基于命令行的 Tailscale 文件传输工具，底层使用 SCP。首次
配置设备的 MagicDNS 主机名后，日常传输只需要使用设备别名，不需要反复
查询 Tailscale IP。

## Features / 功能

- Alias-based file and directory transfers / 使用设备别名传输文件和目录
- Tailscale MagicDNS hostnames instead of manually copied IPs / 使用 MagicDNS
  主机名，避免手动复制 IP
- Upload and download support / 支持上传和下载
- Recursive directory transfers / 支持递归传输目录
- Uses the system OpenSSH client and existing SSH keys / 使用系统 OpenSSH
  和现有 SSH 密钥
- Does not store passwords or private keys / 不保存密码和私钥

## Requirements / 环境要求

- Python 3.10 or newer / Python 3.10 或更高版本
- Tailscale connected on both machines / 两台设备都已连接 Tailscale
- Tailscale MagicDNS enabled, or another resolvable Tailscale hostname /
  已启用 Tailscale MagicDNS，或使用其他可解析的 Tailscale 主机名
- OpenSSH client (`scp`) installed / 已安装 OpenSSH 客户端（`scp`）
- SSH public-key authentication configured / 已配置 SSH 公钥认证

The tool is designed for Windows and Rocky Linux, but any system with Python
and OpenSSH can be used.

本工具主要面向 Windows 和 Rocky Linux，但只要系统安装了 Python 和
OpenSSH，其他系统也可以使用。

## Installation / 安装

Run this command from the project directory / 在项目目录中执行：

```powershell
python -m pip install .
```

Verify the installation / 验证安装：

```powershell
tscp --help
```

If Windows cannot find `tscp`, run the executable directly / 如果 Windows
提示找不到 `tscp`，可以直接运行：

```powershell
& "$HOME\miniconda3\Scripts\tscp.exe" --help
```

## SSH connectivity / SSH 连接

Before using `tscp`, verify that SSH can reach the remote device through its
Tailscale hostname / 使用 `tscp` 前，先确认可以通过 Tailscale 主机名连接：

```powershell
ssh root@rocky-server
```

Replace `root` and `rocky-server` with your SSH username and MagicDNS hostname.

请将 `root` 和 `rocky-server` 替换为实际的 SSH 用户名和 MagicDNS 主机名。

## Configure a device / 配置设备

Add a device alias / 添加设备别名：

```powershell
tscp config add rocky `
  --user root `
  --host rocky-server `
  --path /data/transfer
```

List configured aliases / 查看已配置的别名：

```powershell
tscp config list
```

Update or remove an alias / 更新或删除别名：

```powershell
tscp config update rocky `
  --user root `
  --host rocky-server `
  --path /data/transfer

tscp config remove rocky
```

Use the Tailscale MagicDNS hostname with `--host`; do not use an IP address
unless DNS is unavailable.

`--host` 应填写 Tailscale MagicDNS 主机名。除非 DNS 不可用，否则不需要
填写 IP 地址。

## Transfer files / 传输文件

### Send a file / 发送文件

```powershell
tscp send .\report.zip rocky:/data/transfer/
```

### Download a file / 下载文件

```powershell
tscp get rocky:/data/transfer/report.zip .\
```

### Transfer a directory / 传输目录

```powershell
tscp send --recursive .\folder rocky:/data/transfer/
tscp get --recursive rocky:/data/transfer/folder .\folder
```

The remote path format is `alias:/path`.

远程路径格式为 `alias:/path`。

## Custom SSH port / 自定义 SSH 端口

Configure a non-standard SSH port with `--port`:

使用 `--port` 配置非标准 SSH 端口：

```powershell
tscp config update rocky `
  --user root `
  --host rocky-server `
  --port 2222 `
  --path /data/transfer
```

## Configuration file / 配置文件

By default, aliases are stored at:

默认配置文件位置：

```text
~/.config/tscp/config.json
```

Use `--config PATH` before the command to select another file:

可以在命令前使用 `--config PATH` 指定其他配置文件：

```powershell
tscp --config .\tscp-config.json config list
```

The configuration contains connection metadata only. It never contains
passwords or private-key contents.

配置文件只包含连接信息，不会保存密码或私钥内容。

## Troubleshooting / 常见问题

### `tscp` is not recognized / 找不到 `tscp`

Ensure the Python environment is activated, or run the executable directly:

请确认已激活 Python 环境，或直接运行：

```powershell
& "$HOME\miniconda3\Scripts\tscp.exe" --help
```

### `scp was not found` / 找不到 `scp`

Install the OpenSSH client and ensure `scp` is available in `PATH`.

安装 OpenSSH 客户端，并确认 `scp` 已加入系统 `PATH`。

### SSH authentication fails / SSH 认证失败

First test the connection directly:

先直接测试 SSH 连接：

```powershell
ssh <user>@<magicdns-host>
```

Check the SSH username, public key, and Tailscale connectivity before retrying
the `tscp` command.

检查 SSH 用户名、公钥和 Tailscale 连接状态后，再重试 `tscp` 命令。

### Hostname cannot be resolved / 主机名无法解析

Check that Tailscale is connected and MagicDNS is enabled. The configured
hostname must be the device name available in your Tailscale network.

确认 Tailscale 已连接并启用 MagicDNS。配置的主机名必须是 Tailscale
网络中实际可用的设备名。
