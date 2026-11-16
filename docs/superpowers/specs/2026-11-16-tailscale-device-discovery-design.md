# Tailscale 设备自动发现设计

## 目标

通过 `tailscale status --json` 自动发现 Tailscale 设备，使用户可以直接
使用 Tailscale 设备名传输文件，不需要手动添加别名或查询 IP 地址。

## 使用方式

查看设备列表：

```powershell
tscp device list
```

使用自动发现的设备发送和下载文件：

```powershell
tscp send .\file.zip rocky:/data/ --user root
tscp get rocky:/data/file.zip .\ --user root
```

由于 Tailscale 信息不能可靠地提供远程 SSH 用户名，自动发现模式必须
通过 `--user` 明确指定 SSH 用户。

现有的别名配置方式继续支持：

```powershell
tscp send .\file.zip rocky:/data/
```

## 架构

新增独立的 `tailscale` 模块，负责调用 `tailscale status --json`、验证
子进程结果，并将 JSON 转换为类型化的设备记录。

命令行层先查询现有的 `ConfigStore`。如果目标别名不存在，再调用
Tailscale 设备发现模块，根据设备信息和命令行提供的 SSH 用户构造
`Alias`，最后复用现有 SCP 传输逻辑。

设备发现模块不依赖配置存储和 SCP 执行模块。测试通过模拟子进程边界
完成，不要求测试环境连接真实 Tailscale。

## 设备解析规则

1. 优先在本地 alias 配置中查找目标名称。
2. 如果没有找到，再执行 `tailscale status --json`。
3. 按短设备名、主机名或 MagicDNS 完整主机名匹配。
4. 使用发现到的 MagicDNS 完整主机名作为 SCP 主机地址。
5. 允许离线设备完成名称解析，最终连接失败由 SCP/SSH 报告。

如果一个名称匹配多个设备，程序必须报错，不能自行猜测。
如果设备不存在，错误信息应列出可用设备名称。

## 命令行行为

- 新增 `device list`，显示短设备名、MagicDNS 主机名、操作系统和在线状态。
- 为 `send` 和 `get` 增加 `--user` 参数；只有目标不是已配置 alias 时才要求该参数。
- 保留 `config add`、`config update`、`config list` 和 `config remove`。
- 保留 alias 优先的解析行为，确保现有脚本不需要修改。

## 错误处理

以下情况必须显示明确错误：

- 未安装 `tailscale`；
- Tailscale 未运行；
- Tailscale 输出的 JSON 无效；
- 找不到指定设备；
- 设备名称匹配多个设备；
- 自动发现模式缺少 `--user`。

程序不能静默回退到 Tailscale IP，也不能猜测 SSH 用户名。

## 测试

- 测试代表性的 `tailscale status --json` 输出解析；
- 测试设备列表格式以及在线/离线状态；
- 测试按设备名、主机名和 MagicDNS 名称匹配；
- 测试未知设备和名称冲突错误；
- 测试 alias 优先的传输解析；
- 测试自动发现传输必须提供 `--user`，并使用发现到的完整主机名；
- 测试找不到可执行文件、子进程失败和无效 JSON；
- 在不连接真实 Tailscale 的情况下运行完整测试套件。
