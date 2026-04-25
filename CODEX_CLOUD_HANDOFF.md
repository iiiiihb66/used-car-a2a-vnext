# Codex Cloud Handoff

更新时间：2026-04-25

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
- 最新 Git 提交：`1fe2ce4 feat: add automated agent negotiation sessions`

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

## 下一步优先级

1. 把生产数据库从容器内 SQLite 换成 CloudBase SQL/MySQL，避免重新部署后测试数据丢失。
2. 给自动协商接口补 API 回归测试。
3. 给前端首页增加“自动协商 Demo”入口，让人类可以点按钮跑一轮。
4. 增强 Hermes-lite，对 Qclaw / WorkBuddy 测试过程做更清晰的复盘摘要。
5. 将长期核心算法未来迁到腾讯云私有服务，公开仓库只保留 Skill、OpenAPI、SDK 和外壳。

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

- 线上仍使用容器内 SQLite，重部署会重置测试数据。
- `evaluate_car` 工具仍是 mock 估价，需要后续接真实数据源或更稳健的规则。
- 自动协商目前是 MVP 调度器，不是最终交易系统；它只形成“见面/复核/沟通意向”，不能表达支付、托管、贷款或金融推荐。
- 公开仓库适合早期测试。商业化前必须拆分 public shell 和 private Tencent Cloud core。
