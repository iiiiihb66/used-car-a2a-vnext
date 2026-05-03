# AGENTS.md (项目 Agent 规则手册)

## 产品目标

构建并维护一个 **工具型微信小程序后端**，用于二手车 A2A（Agent-to-Agent）协作。

本项目 **不是** 金融产品，且必须保持对 **个人主体小程序** 的安全性（合规性）。

核心用户价值：

- 车辆档案创建与浏览
- 不可篡改的生命周期记录（基于哈希链）
- A2A 询价与议价协商
- 信誉排行榜
- 卖家举报与人工审核

## 硬性约束 (禁止项)

严禁引入或暴露以下功能作为活跃的产品能力：

- 支付 (Payment)
- 担保交易 (Escrow)
- 贷款转让 (Loan transfer)
- 利率折扣 (Interest-rate discount)
- 金融推荐 (Financial recommendation)
- 投资/收益类语言 (Investment / yield language)
- 保证成交类措辞 (Guaranteed transaction wording)

如果代码中历史遗留了此类功能，请将其禁用或移出生产环境入口。

## 生产环境入口

- 生产应用入口：`app.py`
- 历史实验性入口不得用于部署。

## 部署目标

- 腾讯云 CloudBase / CloudRun (云托管)
- 微信小程序前端
- CloudBase AI / 混元大模型 (通过 OpenAI 兼容 API 接入)

## 工程偏好

- 默认保持产品处于 `APP_MODE=tool` 模式
- 倾向于使用小而集中的 API 接口，而非大型全功能接口
- 除非有特殊理由，否则保留中文用户界面文案
- 倾向于“乏味”的部署方案（简单稳定），而非复杂的架构
- 将 Agent 工作视为受监督的网络：买家 Agent、卖家 Agent 和平台调度 Agent 应通过后端交换状态，而非仅仅依赖聊天上下文
- 保持可解释性：匹配、协商和审核决策应为用户和管理员留下可核查的痕迹

## 同步规则

在进行任何分析、编辑、提交或部署工作之前：

1. 运行 `scripts/ensure_latest.sh`
2. 如果本地分支落后于 `origin/main`，先进行快进式合并 (fast-forward)
3. 如果工作区有未提交的本地更改，不要自动执行 pull
4. 如果分支发生偏离 (diverged)，停止操作并在继续前显式解决冲突

此规则适用于：

- 本地开发
- 云端 Agent 工作
- 部署准备
- 漏洞修复 / 评审 / 重构工作

## 交付规则 (Handoff Rule)

`PROJECT_HANDOFF.md` 是任何接管本项目的 AI Agent 的规范性延续文档。

在每次涉及代码、文档、部署配置、测试或项目方向变更的提交之前：

1. 更新 `PROJECT_HANDOFF.md`
2. 记录变更内容
3. 记录验证结果
4. 记录当前的本地 / GitHub / CloudBase 状态（如果相关）
5. 记录建议的下一个任务

不要在未保持 `PROJECT_HANDOFF.md` 为最新状态的情况下将工作推送到 GitHub。

## 发布前必做检查

1. `app.py` 导入成功
2. `/health` 接口返回 `healthy`
3. `/` 根路径返回 `mode=tool`
4. 管理员路由要求 `X-Admin-Token`
5. 生产环境路径未暴露支付 / 担保 / 贷款流程
6. 工作分支已与 `origin/main` 同步，或已显式处理偏离

## 近期优先级

1. 保持 SQLite-first 的 CloudBase MVP 稳定，不开启付费私有网络
2. 使用 `MVP_AGENT_TEST_PROMPTS.md` 运行 Qclaw / WorkBuddy / 通用 Agent 的 MVP 测试
3. 从外部 Agent 测试中收集 `/api/v1/agent/events`
4. 增加 `scripts/online_smoke_test.py` 用于可重复的部署后检查
5. 优化 Hermes-lite 总结，用于分析测试阻塞点和下一轮提示词建议
6. 仅在免费 MVP 使用显示 SQLite 备份/恢复流程不足时，才考虑使用 CloudBase 文档数据库 HTTP API

## 未来架构护栏

公共仓库可接受早期的 Agent 安装、演示和集成测试。在进行真正的商业使用前，需将系统拆分为：

- **公共外壳**：`skill.md`、`openapi.json`、README、SDK 示例、前端外壳以及非敏感的请求/响应协议。
- **私有腾讯云核心**：匹配/排序算法、卖家权重、信誉评分规则、协商策略、风险控制、反滥用逻辑、管理员工作流、数据库和日志。

公开代码应仅暴露协议和入口，而非核心的专有决策规则。

