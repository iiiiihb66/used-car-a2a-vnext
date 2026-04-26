# Project Handoff

更新时间：2026-04-26

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
2. 通过 Skill / OpenAPI 给 Qclaw、WorkBuddy 等外部 Agent 调用。
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

最近相关提交：

```text
c6a7286 feat: support sqlite-first cloudbase mvp with backup script
```

该提交完成：

1. `models/database.py` 支持 `DB_DIR` 和 `SQLITE_FILENAME` 配置 SQLite 路径。
2. 新增 `scripts/backup_sqlite.py`，可创建 SQLite 一致性备份。
3. `.env.example` 增加 SQLite 相关配置。
4. `README.md`、`DEPLOY_CLOUDBASE.md`、`GITHUB_ACTIONS.md`、`CODEX_CLOUD_HANDOFF.md` 更新为免费版 SQLite-first 路线。

后续补充：

1. `GET /api/v1/admin/database/backup` 支持从线上下载 SQLite 备份。
2. `POST /api/v1/admin/database/restore` 支持必要时恢复 SQLite 备份。
3. `scripts/cloud_sqlite_backup.py` 提供本地下载/恢复入口。
4. `SQLITE_OPERATIONS.md` 固化部署前后操作流程。

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
4. 部署前后定期执行 `python scripts/backup_sqlite.py`。

重要限制：

1. SQLite 适合 MVP 单实例验证。
2. SQLite 不适合作为多实例在线主库。
3. 重部署仍可能导致容器内数据丢失，必须补备份流程。

## 下一步优先级

1. 把 `MVP_AGENT_TEST_PROMPTS.md` 里的两套提示词分别发给 Qclaw 和 WorkBuddy。
2. 收集两个 Agent 写入的 `/api/v1/agent/events`。
3. 根据真实测试卡点修最小阻塞问题。
4. 增强 Hermes-lite，让它总结 Qclaw / WorkBuddy 测试中的卡点和下一轮提示词。
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
- 最近相关提交是 c6a7286

当前任务：
[填写要继续做的具体任务]
```
