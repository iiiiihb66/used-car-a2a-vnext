# Project Handoff

更新时间：2026-04-27 10:52 Asia/Shanghai

## 用途

这份文件用于替代已经接近上下文上限、无法正常 compact 的旧 Codex 对话。

新对话接管项目时，优先读取：

1. `PROJECT_HANDOFF.md`
2. `CODEX_CLOUD_HANDOFF.md`
3. `README.md`
4. `DEPLOY_CLOUDBASE.md`
5. `SQLITE_OPERATIONS.md`
6. `MVP_AGENT_TEST_PROMPTS.md`

## 项目目标

`used-car-a2a-vnext` 是二手车 A2A Agent 协商后端。

当前 MVP 目标：

1. 让买家 Agent 和卖家 Agent 自动完成询价、议价、达成意向。
2. 通过 Skill / OpenAPI 给任意外部 Agent 调用。
3. 用 Hermes-lite 记录事件，后续复盘测试过程。
4. 尽量使用免费或低成本云资源跑通验证。

说明：

- Qclaw 和 WorkBuddy 只是当前手头的两个测试 Agent。
- 系统不绑定特定 Agent 名称。
- 任意支持 Skill / OpenAPI / HTTP JSON 调用的 Agent 都可以接入。
- `buyer_agent_name`、`seller_agent_name`、`actor_agent` 只是记录来源名称。

## 旧对话中的关键转折

旧对话最初判断：

1. 最大短板是线上仍使用容器内 SQLite。
2. CloudBase 重部署会导致测试用户、车源、会话、Hermes-lite 复盘数据丢失。
3. 因此建议优先接 CloudBase SQL / MySQL，把 `DATABASE_URL` 配到 CloudBase 环境变量。

后续实际验证发现：

1. CloudBase SQL / MySQL 需要私有网络等能力。
2. 当前控制台截图显示私有网络是标准版能力，套餐约 179.10 元/月。
3. 这与“尽量用免费资源跑通 MVP”的目标冲突。

因此策略已更新：

1. 不升级套餐。
2. 不点任何付费能力。
3. 不走 CloudBase SQL / MySQL + 私有网络。
4. 当前先采用 CloudBase 云托管 + SQLite-first + 备份。
5. 后续如仍需免费/个人版持久化，再评估 CloudBase 文档型数据库 HTTP API。

## 当前已完成

最近关键提交：

```text
c6a7286 feat: support sqlite-first cloudbase mvp with backup script
ed4a63e docs: add project handoff for codex recovery
2259384 feat: add cloud sqlite backup and restore workflow
cbfd53f docs: add mvp test prompts for qclaw and workbuddy
3f8efb2 docs: clarify generic agent integration support
```

这些提交完成：

1. `models/database.py` 支持 `DB_DIR` 和 `SQLITE_FILENAME` 配置 SQLite 路径。
2. 新增 `scripts/backup_sqlite.py`，可创建 SQLite 一致性备份。
3. `.env.example` 增加 SQLite 相关配置。
4. `README.md`、`DEPLOY_CLOUDBASE.md`、`GITHUB_ACTIONS.md`、`CODEX_CLOUD_HANDOFF.md` 更新为免费版 SQLite-first 路线。
5. `GET /api/v1/admin/database/backup` 支持从线上下载 SQLite 备份。
6. `POST /api/v1/admin/database/restore` 支持必要时恢复 SQLite 备份。
7. `scripts/cloud_sqlite_backup.py` 提供本地下载/恢复入口。
8. `SQLITE_OPERATIONS.md` 固化部署前后操作流程。
9. `MVP_AGENT_TEST_PROMPTS.md` 提供 Qclaw、WorkBuddy 和通用 Agent 测试提示词。
10. Skill / OpenAPI 文案已明确支持任意外部 Agent，不绑定 Qclaw / WorkBuddy。
11. 新增 `scripts/online_smoke_test.py`，把线上业务闭环验证固化成可重复脚本，带有 CloudRun 冷启动超时控制。

## GitHub 与线上状态

GitHub 仓库：

```text
https://github.com/iiiiihb66/used-car-a2a-vnext
```

当前 `main` 已推送到：

```text
3f8efb2 docs: clarify generic agent integration support
```

CloudBase 已部署并完成切流。

线上确认：

1. `GET /openapi.json` 中 `buyer_agent_name` 默认值为 `buyer-agent`。
2. `GET /openapi.json` 中 `seller_agent_name` 默认值为 `seller-agent`。
3. `GET /skill.md` 已包含“不绑定特定 Agent 客户端”和“记录任意外部 Agent”的通用接入说明。
4. 混元模型链路已在线上跑通，最近一次自动协商事件中 `agent_response.mock=false`。
5. 线上自动协商 MVP 已跑通：创建买家、卖家、车源、session、run、查询 conversations/events。

最近线上备份：

```text
backups/cloud_sqlite_20260426_100440.db
backups/cloud_sqlite_20260426_100824.db
```

这些备份在本地 `backups/`，已被 `.gitignore` 排除，不会上传 GitHub。

## Antigravity 接手前恢复点

目标：

1. 给 Antigravity / 官网 ChatGPT / 其他 AI 一个明确接手基线。
2. 避免不同 AI 基于过期上下文重复走错方向。
3. 后续如果改坏，可以回到这个 Git 状态重新接手。

恢复点名称：

```text
antigravity-handoff-20260427
```

该恢复点应对应：

```text
main @ 3a75f7a 或之后包含本段 handoff 更新的提交
```

接手方式：

1. 拉取 GitHub `main`。
2. 先阅读 `AGENTS.md` 和 `PROJECT_HANDOFF.md`。
3. 按 `AGENTS.md` 的 Handoff Rule，在每次提交前维护 `PROJECT_HANDOFF.md`。

## 当前部署策略

CloudBase 环境：

```text
car-assistant-prod-3dqle77ef680c
```

CloudBase 服务：

```text
used-car-a2a-vnext
```

当前推荐配置：

1. `DATABASE_URL` 留空。
2. 使用默认 SQLite。
3. CloudBase 云托管实例数保持为 1。
4. 部署前后执行 `python scripts/cloud_sqlite_backup.py download --output-dir ./backups`。

重要限制：

1. SQLite 适合 MVP 单实例验证。
2. SQLite 不适合作为多实例在线主库。
3. 重部署仍可能导致容器内数据丢失，必须补备份流程。

## 下一步优先级

1. 把 `MVP_AGENT_TEST_PROMPTS.md` 里的测试提示词发给 Qclaw、WorkBuddy 或其他外部 Agent。
2. 收集外部 Agent 写入的 `/api/v1/agent/events`。
3. 根据真实测试卡点修最小阻塞问题。
4. 增强 Hermes-lite，让它总结外部 Agent 测试中的卡点和下一轮提示词。
5. 只有在免费方案仍能满足时，才评估 CloudBase 文档型数据库 HTTP API。

## 新对话接管提示词

如果旧对话继续报 compact 错误，可以在新对话中使用：

```text
请接管这个项目：
/Users/fuhongbo/Documents/Antigravity/项目对比/used-car-a2a-vnext

先阅读：
- PROJECT_HANDOFF.md
- CODEX_CLOUD_HANDOFF.md
- README.md
- DEPLOY_CLOUDBASE.md
- SQLITE_OPERATIONS.md
- MVP_AGENT_TEST_PROMPTS.md

关键决策：
- 不升级 CloudBase 套餐
- 不走 CloudBase SQL / MySQL + 私有网络
- 当前采用 SQLite-first
- 系统不绑定 Qclaw / WorkBuddy，任意支持 Skill / OpenAPI / HTTP JSON 的 Agent 都可以接入
- 最近线上已部署提交是 3f8efb2

当前任务：
[填写要继续做的具体任务]
```

## 给其他 AI 的接管要求

接管后先执行：

```bash
git status --short
git log -5 --oneline
```

如果要部署 CloudBase：

1. 先执行线上 SQLite 备份。
2. 再运行 `scripts/deploy_cloudbase_clean.sh`。
3. 部署后检查 `/openapi.json` 和 `/skill.md` 是否为新版本。
4. 部署后再下载一次 SQLite 备份。

不要做：

1. 不要提交 `.secrets/`。
2. 不要提交 `.env`。
3. 不要提交 `data/*.db` 或 `backups/`。
4. 不要重新引导用户开 CloudBase MySQL / 私有网络付费能力。
5. 不要把当前 SQLite 方案误认为生产级长期数据库方案。
