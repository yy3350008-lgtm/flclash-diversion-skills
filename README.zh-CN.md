# FlClash Diversion Skills

[English](README.md) | 简体中文

一个隐私安全的命令行工具，同时也是一个 Codex/Claude 技能，用于将 FlClash/Mihomo
代理配置合并为一个文件，并实现精确的域名分流。

## 为什么需要这个工具？

FlClash 同一时间只能激活一个配置文件。如果你有一个辅助配置，其中的某些节点在特定
服务（例如 NotebookLM）上表现更好，你无法同时使用两个配置。本工具将两个配置合并
为一个输出文件：

- 辅助配置中的所有节点会被添加到主配置中。
- 自动创建一个辅助节点组，并插入到主选择组中。
- 创建一个分流组，将指定域名路由到指定节点。
- 宽泛域名规则（google.com 等）默认被阻止，避免劫持某个服务商的全部流量。

## 功能特性

- **精确域名分流** — 仅路由已确认的目标域名，而非整个顶级域名。
- **目标节点验证** — 如果指定的目标节点在合并后的节点列表中不存在，脚本会拒绝写入。
- **宽泛域名阻止** — google.com、googleapis.com、gstatic.com 的规则默认被拒绝，
  除非显式设置 `--allow-broad-domain`。
- **写入后验证** — 输出文件写入后会从磁盘重新读取并验证；验证失败则删除文件。
- **不暴露凭据** — 脚本仅打印组名、域名和节点数量，不打印 IP、UUID、令牌或密码。
- **隐私安全的示例** — 所有示例配置使用 `type: direct` 代理桩，不包含任何端点或
  凭据字段。

## 安全与隐私

本项目设计为可安全发布：

- **脚本和配置中不包含硬编码路径、IP、UUID、令牌或密码。**
- **不包含用户特定的本地路径或用户名。**
- **示例使用 `type: direct` 代理桩**，不包含端点或凭据字段。
- **输出摘要不打印配置内容或凭据。**
- `.gitignore` 屏蔽了 `output.yaml`、`*.local.yaml`、`*.secret.yaml` 和 `.env`，
  防止意外提交凭据。

## 安装

### 环境要求

- Python 3.10+
- `ruamel.yaml` >= 0.18

### 安装步骤

```bash
pip install ruamel.yaml
```

如需安装开发依赖（用于运行测试）：

```bash
pip install -e ".[dev]"
```

### 作为 Codex/Claude 技能使用

将 `SKILL.md` 文件以及 `agents/` 和 `scripts/` 目录复制到你的技能路径中。
`SKILL.md` 中的技能描述会被 Codex/Claude 自动识别。

## 命令行用法

```bash
python scripts/merge_flclash_configs.py \
  --base examples/generic-main.yaml \
  --secondary examples/generic-secondary.yaml \
  --output output.yaml \
  --main-group Main \
  --secondary-group Secondary-Main \
  --target-group NotebookLM \
  --target-domain notebooklm.google \
  --target-node Proxy-B
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--base` | 是 | — | 基础配置 YAML 路径 |
| `--secondary` | 是 | — | 辅助配置 YAML 路径 |
| `--output` | 是 | — | 合并输出 YAML 路径 |
| `--main-group` | 是 | — | 基础配置中的主选择组名称 |
| `--secondary-group` | 是 | — | 新建辅助代理组的名称 |
| `--target-group` | 是 | — | 新建分流组的名称 |
| `--target-domain` | 是 | — | 要分流的域名（可重复指定） |
| `--target-node` | 是 | — | 分流组中的指定节点名称（可重复指定） |
| `--target-group-type` | 否 | `select` | 组类型：`select` 或 `url-test` |
| `--allow-broad-domain` | 否 | `false` | 允许宽泛域名规则 |

### 脚本工作流程

1. 加载基础配置和辅助配置的 YAML 文件。
2. 将辅助节点追加到基础配置中（跳过重复项和流量/到期提醒等元条目）。
3. 使用所有辅助真实节点创建辅助组。
4. 将辅助组插入到主选择组的第 0 位。
5. 验证每个 `--target-node` 是否存在于合并后的节点列表中；不存在则以非零状态退出。
6. 使用指定的目标节点创建分流组。
7. 移除目标域名已有的 DOMAIN-SUFFIX 规则，然后在规则列表前端插入新规则。
8. 除非设置了 `--allow-broad-domain`，否则阻止宽泛域名规则。
9. 写入前在内存中验证；写入后从磁盘重新读取并验证。

## FlClash 操作步骤

1. 打开 FlClash，进入 **配置** 页面。
2. 将输出的 YAML 文件添加为本地配置。
3. 启用该配置。
4. 进入 **代理** 页面，验证各组中的节点。
5. 测试目标域名是否通过分流组路由。

如需回退，只需在 FlClash 中重新加载原始配置文件即可。

## 测试

```bash
pytest
```

测试覆盖范围：

- 成功合并并验证正确的组结构和规则顺序。
- 目标节点验证（缺失节点导致非零退出）。
- `--target-group-type url-test` 标志。
- 宽泛域名阻止和 `--allow-broad-domain` 覆盖。
- 域名规范化（前导点号、空白字符）。
- 隐私检查（输出中不包含本地路径或用户目录）。

## 局限性

- 脚本假设输入的 YAML 是合法的 FlClash/Mihomo 配置语法。
- `url-test` 组使用 `https://www.gstatic.com/generate_204` 作为测试 URL。
- 脚本不会修改输入文件，始终写入新的输出文件。
- 宽泛域名阻止仅检查最常见的三个 Google 域名。

## 贡献指南

1. Fork 本仓库。
2. 创建功能分支。
3. 为新功能添加测试。
4. 运行 `pytest` 确保所有测试通过。
5. 提交 Pull Request。

请确保所有提交中不包含真实凭据、IP 地址或用户特定路径。

## 许可证

[MIT](LICENSE) — Copyright 2026 FlClash Diversion Skills contributors.
