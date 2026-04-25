# Codex Cloud Handoff

更新时间：2026-04-26

## 当前结论

项目已经完成从“单步 Skill/API 调用”到“平台自动驱动买家 Agent 与卖家 Agent 多轮协商”的第一版闭环。

现在不需要人工在 Qclaw 和 WorkBuddy 之间复制粘贴消息。平台后端可以创建自动协商会话，并自动执行：

1. 买家 Agent 发起询价
2. 卖家 Agent 调用混元回复车况和价格空间
3. 买家 Agent 读取卖家回复并生成议价判断
4. 平台给出报价
5. 卖家 Agent 回复接受、反价或继续沟通
6. Hermes-lite 记录事件，供后续复盘

## 线上地址

- GitHub: `https://github.com/iiiiihb66/used-car-a2a-vnext`
- Vercel 首页 / Skill 入口: `https://used-car-a2a-vnext.vercel.app/`
- Vercel Skill: `https://used-car-a2a-vnext.vercel.app/skill.md`
- CloudBase 后端: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com`
- CloudBase Skill: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md`
- OpenAPI: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json`

## 最新已部署版本

- CloudBase 服务名：`used-car-a2a-vnext`
- CloudBase 环境：`car-assistant-prod-3dqle77ef680c`
- 最新线上版本：`used-car-a2a-vnext-012`
- 最新 Git 提交：以 GitHub `main` 分支为准；本文件会随提交更新。

## 本轮新增能力

新增自动协商 API：

- `POST /api/v1/agent/sessions`
- `POST /api/v1/agent/sessions/{session_id}/run`
- `GET /api/v1/agent/sessions/{session_id}`

相关文件：

- `app.py`
- `agents/user_agent.py`
- `openapi.json`
- `skill.md`
- `site/skill.md`

关键逻辑：

- `POST /api/v1/agent/sessions` 创建平台自动协商会话。
- `POST /api/v1/agent/sessions/{session_id}/run` 自动执行多轮买卖双方 Agent 对话。
- `GET /api/v1/agent/sessions/{session_id}` 查看完整 conversations 和 agent_events。
- Hermes-lite 会写入 `auto_session_created`、`auto_inquiry_sent`、`auto_negotiation_round`、`auto_session_completed` 等事件。

## 实测结果

公网实测通过。

测试 session：

```text
session_id: auto_20260425011957_e12dcb31
final_state: deal_ready
agreed_price: 14.1 万
rounds: 1
conversation_count: 6
event_count: 4
```

卖家 Agent 接受了 14.1 万报价，返回内容包含“接受14.1万元的价格”，说明自动协商链路可用。

## 混元接入状态

后端使用 OpenAI 兼容方式调用腾讯混元。

当前 CloudBase 环境变量中使用：

- `AI_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1`
- `AI_MODEL=hunyuan-turbos-latest`

注意：

- 不要把 `AI_API_KEY`、`ADMIN_TOKEN`、`cloudbaserc.json`、`.secrets/`、本地数据库提交到 GitHub。
- CloudBase 部署必须使用 `scripts/deploy_cloudbase_clean.sh`，不要直接用项目根目录部署。

## Codex Cloud 接力规则

开始任何修改前先执行：

```bash
scripts/ensure_latest.sh
```

如果在 Codex Cloud 中工作：

1. 先阅读 `AGENTS.md`。
2. 再阅读本文件。
3. 不要假设云端有本机 CloudBase CLI 登录态。
4. 可以修改代码、文档、测试，并推送 GitHub。
5. CloudBase 真实部署优先留给本地已登录 CLI 执行，除非云端已经配置好腾讯云密钥。

## CloudBase 数据库状态

2026-04-25 已通过 CLI 验证：

```bash
tcb db instance list -e car-assistant-prod-3dqle77ef680c --json
```

返回：

```json
{"data":[],"meta":{"total":0}}
```

也就是说当前 CloudBase 环境还没有 MySQL 实例。

继续执行：

```bash
tcb db execute -e car-assistant-prod-3dqle77ef680c --sql 'SHOW DATABASES' --read-only --json
```

返回 `ResourceNotFound.InstanceNotFound`。因此生产数据库持久化不是代码已经接不上，而是云资源还没有开通 SQL 实例。

CLI 当前提供 `db instance list/config/restart` 和 `db execute`，未发现可直接创建 MySQL 实例的命令。

2026-04-26 策略更新：

- 不走 CloudBase SQL / MySQL。
- 不做需要私有网络的方案。
- 当前主路径改为 CloudBase 云托管继续跑后端，数据库保持 SQLite-first。
- 为避免重部署丢数，仓库已补充 `scripts/backup_sqlite.py`，可定期导出快照。
- 后续如果要继续留在免费/个人版，再评估把核心业务数据迁到 CloudBase 文档型数据库 HTTP API。

## 回归测试状态

已新增 `scripts/smoke_test.py`，覆盖：

- `/health`
- `/`
- 创建买家
- 创建卖家
- 上架车辆
- 发布需求
- 查询匹配
- 创建自动协商会话
- 运行自动协商会话
- 查看会话 conversations/events
- 确认 OpenAPI 暴露 `/api/v1/agent/sessions`

GitHub Actions 已改为运行：

```bash
python scripts/smoke_test.py
```

本地已用 mock 模型跑通：

```bash
AI_MODEL=mock AI_API_KEY=sk-test-mock python3 scripts/smoke_test.py
```

## 前端 Demo 状态

Vercel 首页已增加“自动协商 Demo”入口。

入口位置：

```text
https://used-car-a2a-vnext.vercel.app/#auto-demo
```

点击按钮后会调用 CloudBase 后端：

1. 创建测试卖家
2. 创建测试车源
3. 创建测试买家
4. 创建自动协商会话
5. 运行自动协商会话
6. 在页面输出 `session_id`、`final_state`、`agreed_price` 和每轮摘要

## 下一步优先级

1. 保持 `DATABASE_URL` 留空，用 SQLite 跑通免费版 MVP。
2. 在单实例前提下补齐 SQLite 备份节奏，避免重部署丢测试数据。
3. 增强 Hermes-lite，对 Qclaw / WorkBuddy 测试过程做更清晰的复盘摘要。
4. 后续再评估把核心实体迁到 CloudBase 文档型数据库 HTTP API。

## 给 Qclaw / WorkBuddy 的测试入口

让外部 Agent 安装：

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：
https://used-car-a2a-vnext.vercel.app/skill.md

安装后优先使用自动协商接口：
POST /api/v1/agent/sessions
POST /api/v1/agent/sessions/{session_id}/run
GET /api/v1/agent/sessions/{session_id}
```

## 当前仍需注意的问题

- CloudBase 免费/低成本实例可能冷启动，首次公网请求可能出现约 30 秒 503；随后 `/health` 可恢复 200。
- 线上仍使用容器内 SQLite，重部署会重置测试数据。
- 免费/个人版下不要再把 MySQL + 私有网络当成默认下一步，否则会直接碰到套餐升级。
- `evaluate_car` 工具仍是 mock 估价，需要后续接真实数据源或更稳健的规则。
- 自动协商目前是 MVP 调度器，不是最终交易系统；它只形成“见面/复核/沟通意向”，不能表达支付、托管、贷款或金融推荐。
- 公开仓库适合早期测试。商业化前必须拆分 public shell 和 private Tencent Cloud core。
