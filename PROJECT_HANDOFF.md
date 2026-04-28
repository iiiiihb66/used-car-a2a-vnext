# Project Handoff

更新时间：2026-04-27 12:00 Asia/Shanghai

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
12. **Agent 核心优化 (Antigravity)**:
    - **买家 (Qclaw-buyer)**: 支持 `proposed_price` 动态递增出价（参考评估价与展示价差），支持批量品牌匹配，增加 `deal_ready` 后的主动确认流程。
    - **卖家 (WorkBuddy-seller)**: 实现结构化车况模板（外观、内饰、机械、历史），引用市场平均价数据支撑出价，增加报价一致性纠错。
    - **专用 Agent 分离**: 新增 `agents/qclaw_buyer.py`，将买家定价逻辑抽离，支持非线性动态出价博弈。
    - **工具化**: 新增 `utils/price_tools.py` 提供估价引擎和描述模板。
    - **API 优化**: 修复 `POST /api/v1/cars` 字段冗余，统一支持 `owner_id` 在 Body 传输。

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
backups/cloud_sqlite_20260427_134603.db (最新，部署前备份)
```

这些备份在本地 `backups/`，已被 `.gitignore` 排除，不会上传 GitHub。

## Antigravity 接手后成果 (2026-04-27)

1. **核心 Bug 修复**: 修复了 `app.py` 中缺失 `_calculate_offer_price` 函数定义的问题，解决了自动协商 session run 时的 NameError。
2. **测试脚本增强**:
   - 增强了 `scripts/online_smoke_test.py`，增加了对 CloudRun 冷启动 (503) 的容错重试逻辑。
   - 增加了更丰富的进度日志输出。
3. **线上验证**:
   - 成功执行了线上 SQLite 备份 (`backups/cloud_sqlite_20260427_134603.db`)。
   - 完成了代码热修复后的线上重新部署。
   - 通过 `online_smoke_test.py` 验证了线上业务闭环（买家/卖家创建、车源发布、自动协商达成交）。
4. **MVP Agent 验证**:
   - 扮演 Antigravity-test-agent 执行了 `MVP_AGENT_TEST_PROMPTS.md` 中的全流程。
   - 成功在 `/api/v1/agent/events` 中记录了测试观察。
5. **Hermes-lite 增强**:
   - 增强了 `memory/growth_engine.py`，支持识别 `validation` 和 `smoke_test` 事件。
   - 增加了针对测试卡点（如 503 错误）的自动动作建议。
6. **Agent 深度优化 (2026-04-27)**:
   - **Buyer (Qclaw)**: 实现了非线性动态出价逻辑；支持批量品牌匹配工具；增加了成交前的“最终确认”闭环。
   - **Seller (WorkBuddy)**: 引入结构化车况模板（外观/内饰/机械/历史）；增加了基于市场数据的价格依据支持；实现了口头报价与系统参数的自动纠错机制。
   - **通用能力**: 强化了 Prompt 约束以隐藏内部指令，并增强了理解纠错能力。

## 当前部署策略

7. **Orchestration & 隐私优化 (2026-04-28)**:
   - **防止指令泄露**: 在 `A2AMessage` 和 `Conversation` 中引入 `is_system` 标识，自动隐藏调度器 Prompt 及其回复。
   - **消除重复记录**: 修复了 `UserAgent` 和 `A2ABus` 之间的冗余存储逻辑，解决了对话历史翻倍的问题。
   - **议价逻辑优化**: 精简 `_is_deal_ready` 关键词匹配，排除了“促成交易”等语义误伤，提升了自动撮合的准确性。
9. **P0 修复: 内部指令泄露防护 (2026-04-28)**:
   - **问题**: 虽然数据已正确标记 `is_system=1`，但 `session detail` 和 `conversation history` 接口未进行过滤，导致内部调度 Prompt（如“请作为买家 Agent...”）泄露给外部用户。
   - **策略**: 修改 `A2ABus.get_conversation_history` 和 `app.get_agent_session`，默认过滤 `is_system=1` 的消息。对 `AgentEvent` 记录进行脱敏处理，移除包含 Prompt 的原始快照，仅保留业务安全字段。
   - **技术约束**: 坚持 SQLite-first 单实例部署，不引入外部数据库。

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

1. **观察真实 Agent 接入**: 继续使用 `MVP_AGENT_TEST_PROMPTS.md` 引导其他 Agent (如 Qclaw) 接入并记录 events。
2. **复盘数据导出**: 增强 `/api/v1/admin/growth/reviews` 的导出功能，方便离线分析 Agent 博弈质量。
3. **冷启动优化**: 考虑增加预热请求或优化 `app.py` 启动耗时，减少 CloudRun 503 发生概率。
4. **性能监控**: 收集并展示 `/api/v1/agent/events` 中的时延数据。

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
