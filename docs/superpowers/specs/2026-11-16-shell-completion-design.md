# Shell Tab 补全设计

## 目标

为 `tscp` 增加 PowerShell 和 Bash 的 Tab 自动补全，减少输入子命令、
设备名和参数的重复工作。

## 使用方式

生成 PowerShell 补全脚本：

```powershell
tscp completion powershell
```

当前会话启用：

```powershell
tscp completion powershell | Out-String | Invoke-Expression
```

生成 Bash 补全脚本：

```bash
tscp completion bash
```

当前会话启用：

```bash
eval "$(tscp completion bash)"
```

## 补全内容

静态补全：

- 顶层命令：`config`、`device`、`send`、`get`、`completion`；
- 子命令：`config add`、`config update`、`config list`、
  `config remove`、`device list`；
- 选项：`--config`、`--user`、`--path`、`--port`、`--recursive`。

动态补全：

- 本地配置中的 alias；
- Tailscale 当前设备名；
- Tailscale MagicDNS 主机名。

动态设备补全调用 `tailscale status --json`。如果 Tailscale 不可用，
补全仍提供静态命令和选项，不让 Tab 补全整体失败，也不隐藏错误。

## 架构

新增独立的 `completion` 模块，负责生成 PowerShell 和 Bash 脚本。
该模块复用现有 `ConfigStore` 和 Tailscale 发现模块的数据规则，但不
执行文件传输。

CLI 新增 `completion <shell>` 命令，将脚本输出到标准输出。用户可以
把输出保存为脚本文件，或直接通过 Shell 命令加载。

补全器本身在用户按 Tab 时执行动态查询，因此不能把设备列表固化到
安装时生成的脚本中。脚本应调用 `tscp` 的轻量设备/alias 查询接口，
并将错误视为“没有动态候选”，继续提供静态候选。

## 兼容性与安全

- 不改变现有 `send`、`get`、`config` 和 `device` 命令行为；
- 不把密码、私钥或配置文件内容写入补全脚本；
- 动态候选必须经过安全的参数列表调用，禁止 Shell 字符串拼接；
- 设备名和 alias 中包含空格、引号或 Shell 特殊字符时，必须正确转义
  或过滤，避免生成可执行的用户输入；
- PowerShell 和 Bash 脚本分别使用各自的转义规则。

## 测试

- 测试 PowerShell 脚本包含注册补全器和静态命令；
- 测试 Bash 脚本包含 `complete` 注册和静态命令；
- 测试脚本生成不包含密码、私钥和配置文件内容；
- 测试 alias 和 Tailscale 设备名候选；
- 测试 Tailscale 不可用时仍能生成脚本并保留静态补全；
- 测试未知 Shell 返回明确错误；
- 运行完整测试套件。
