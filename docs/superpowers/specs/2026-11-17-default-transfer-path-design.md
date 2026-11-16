# 主机默认传输目录设计

## 目标

允许用户为传输主机配置默认远程目录，使发送文件时只需要写主机名：

```powershell
tscp send .\test.zip linux
```

上面的命令应传输到：

```text
nbplus@linux:/home/user/nbplus/Downloads
```

## 配置方式

使用现有 alias 配置命令保存 SSH 用户、主机名和默认目录：

```powershell
tscp config add linux `
  --user nbplus `
  --host linux `
  --path /home/user/nbplus/Downloads
```

配置继续保存在现有的本地 JSON 配置文件中，不保存密码或私钥。

## 命令行为

- `tscp send .\file.zip linux` 使用 `linux` alias 的默认目录；
- `tscp send .\file.zip linux:/other/path/` 临时覆盖默认目录；
- `tscp get linux:/file.zip .\` 继续要求明确远程文件路径；
- 已配置 alias 优先于 Tailscale 自动发现；
- 未配置的自动发现设备继续支持 `--user`，但不能直接使用默认目录；
- 现有的 `alias:/path` 发送和下载行为保持兼容。

## 解析规则

发送命令的目标参数分为三种：

1. `host`：仅包含主机名，查找 alias 并使用其默认目录；
2. `host:/path`：查找 alias 或自动发现设备，使用明确路径；
3. 其他格式：报告明确的目标格式错误。

默认目录只允许配置为绝对远程路径，并且必须通过参数列表传递给
`scp`，不能拼接成 Shell 命令。

## 错误处理

- 仅写主机名但 alias 不存在：提示需要配置 alias，或改用
  `host:/path --user user`；
- alias 默认目录无效：配置时拒绝保存；
- alias 不存在：保留现有明确错误；
- 本地路径和远程目标混用：保留现有路径解析错误。

## 测试

- 测试仅主机名发送时使用配置的默认目录；
- 测试 `host:/path` 覆盖默认目录；
- 测试下载仍然要求明确远程路径；
- 测试自动发现设备不能在没有 alias 时猜测默认目录；
- 测试默认目录必须是绝对路径；
- 测试现有 alias 和完整远程路径行为不回归。
