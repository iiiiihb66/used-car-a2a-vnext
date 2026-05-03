# Project Handoff

更新时间：2026-05-03 16:45 Asia/Shanghai

## 用途

这份文件用于替代已经接近上下文上限、无法正常 compact 的旧 Codex 对话。

新对话接管项目时，优先读取：

1. `PROJECT_HANDOFF.md`
2. `AGENTS.md` (已中文化)
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

## Antigravity (Gemini 1.5 Pro) 接手后成果 (2026-05-03)

### Phase 2.1 (14:55 批次) — 匹配引擎 + 一键协商
1. **匹配引擎 (Match Engine)**: 成功部署 `match_pool` 逻辑，支持需求与车源的结构化匹配。
2. **一键协商**: 线上已支持从匹配记录直接开启 A2A 自动协商链路。
3. **线上验收**: 运行 `scripts/online_match_test.py` 验证通过，线上”需求 -> 匹配 -> 协商”闭环成功。
4. **AGENTS.md 中文化**: 将项目规则手册完整翻译为中文，明确了”非金融、工具型”的硬性约束。
5. **同步 GitHub**: 本地领先的 Phase 2.1 提交（至 `b9adcf3`）已全部推送到 GitHub 远程仓库。
6. **生产环境保障**: 预部署备份 + 健康度确认。

### Phase 2.2 (16:45 批次) — 业务闭环 + 生产硬化
1. **文件上传**: `POST /api/v1/upload` + `GET /uploads/{filename}`，支持图片和 PDF。
2. **Excel 批量导入车源**: `POST /api/v1/cars/batch-import`，使用 `utils/excel_parser.py` 解析，支持品牌/车型/年份/价格/里程等字段。
3. **需求大厅**: `GET /api/v1/demands` 公开浏览需求 + `POST /api/v1/demands/{id}/submit-car` 车商主动提交车源匹配（无需 admin token）。
4. **成交闭环 + 人类决策**: `models/deal.py`（Deal 模型）+ `POST /api/v1/deals` 创建成交 + `POST /api/v1/deals/{id}/action` 接受/拒绝/还价。
5. **修复 match→session 参数映射**: 传入 `buyer_budget_min`/`buyer_target_price`/`buyer_goal` 有上下文的参数，确保 submit-car → deal_ready 链路可用。
6. **分页**: `GET /api/v1/cars` 和 `GET /api/v1/users` 增加 `offset/limit` 分页；`GET /api/v1/cars` 新增 `mileage_max`/`year_min`/`year_max` 筛选。
7. **代码规范**: `models/database.py` 显式导入 `MatchPool` 和 `Deal`。
8. **验证**: 原始 `scripts/smoke_test.py` ✅ 通过；全链路（submit-car → session → deal_ready → deal → human accept）✅ 通过。

## 下一步优先级

1. **部署到 CloudBase**: 将 Phase 2.2 代码推送到线上环境，验证全链路（Excel导入、需求大厅、成交决策）在生产环境的表现。
2. **前端对接**: 微信小程序或 Web UI 对接新的 API。
3. **博弈质量观察**: 持续观察 Qclaw 与 WorkBuddy 的协商逻辑是否自然。
4. **503 冷启动优化**: 考虑轻量级预热方案。
5. **增加测试覆盖率**: 将 smoke_test.py 迁移到 pytest，添加 GitHub Actions CI 自动测试。|

---

## 历史关键转折

### 数据库路线 (2026-04-26)
- 放弃 CloudBase SQL / MySQL + 私有网络路线（月费约 179 元）。
- 确立 **SQLite-first** 方案，配合单实例云托管和手动备份脚本。

### Agent 优化 (2026-04-27)
- 引入 `PriceEvaluator` 和 `_calculate_offer_price` 逻辑，修复了离谱报价（如 13万的车报 2万）的 Bug。
- 实现了买家动态递增出价和卖家结构化车况模板。

## GitHub 与线上状态

GitHub 仓库：`https://github.com/iiiiihb66/used-car-a2a-vnext`
当前 `main` 分支状态：待提交 Phase 2.2 变更（上次已同步 Hash `b9adcf3`）。

线上服务：
- 环境 ID: `car-assistant-prod-3dqle77ef680c`
- 服务名: `used-car-a2a-vnext`
- 模式: `mode=tool` (单实例 SQLite)

---

## 给接管 AI 的指令

1. **先做同步**: 执行 `./scripts/ensure_latest.sh`。
2. **严守底线**: 不得引入支付、贷款等金融敏感功能（详见 `AGENTS.md`）。
3. **备份为先**: 任何涉及数据库结构或生产部署的操作，必须先运行 `scripts/cloud_sqlite_backup.py download`。
