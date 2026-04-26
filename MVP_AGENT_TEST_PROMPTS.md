# MVP Agent Test Prompts

更新时间：2026-04-26

## 测试目标

当前目标不是闭门完善所有功能，而是先把最小可执行方案发布出去，让 Qclaw 和 WorkBuddy 在真实使用中暴露问题。

Qclaw 和 WorkBuddy 只是当前手头的两个测试工具，不是系统边界。
实际发布后，任何能读取 Skill / OpenAPI 并调用 HTTP API 的 Agent 都可以接入。

本轮测试只验证 MVP：

1. Skill 能安装。
2. OpenAPI 能读取。
3. 买家、卖家、车源能创建。
4. 自动协商 session 能创建并运行。
5. conversations 和 events 能查到。
6. 外部 Agent 能把测试观察写入 `/api/v1/agent/events`。

## 通用接入能力

这个服务不绑定具体 Agent 名称。

任意 Agent 只要具备以下能力，就可以接入：

1. 读取 Skill 文档。
2. 读取 OpenAPI。
3. 发起 HTTP GET / POST 请求。
4. 处理 JSON 响应。
5. 按需调用 `/api/v1/agent/events` 写入测试观察。

`buyer_agent_name`、`seller_agent_name` 和 `actor_agent` 只是记录来源名称，可以填写 Qclaw、WorkBuddy、小龙虾、爱马仕或其他 Agent 名称。

## 公共入口

```text
Skill:
https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

OpenAPI:
https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

Base URL:
https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com
```

## 给 Qclaw 的提示词：买家视角测试样例

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

安装后读取 OpenAPI：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

你这次扮演“买家 Agent / Qclaw-buyer”，目标是测试一个真实买车用户是否能顺畅完成二手车意向撮合。

请按顺序执行：

1. 创建一个买家用户，画像是：预算 9-10 万，家用通勤，偏好丰田/本田/比亚迪，重视车况透明和后续省心。
2. 创建一个车商/卖家用户。
3. 让卖家发布一台测试车源，例如 2021 年丰田卡罗拉，价格 9.8 万，目标成交价 9.5 万，地区北京。
4. 创建一个自动协商 session：调用 `POST /api/v1/agent/sessions`。
5. 运行自动协商：调用 `POST /api/v1/agent/sessions/{session_id}/run`。
6. 查询 session 详情：调用 `GET /api/v1/agent/sessions/{session_id}`。
7. 检查返回里是否有 conversations 和 events。
8. 用 `POST /api/v1/agent/events` 写入你的测试观察。

测试观察请包含：

- 哪一步最顺畅
- 哪一步最容易卡住
- API 字段是否容易理解
- 自动协商回复是否像真实买卖沟通
- 你作为买家 Agent 下一轮希望产品补什么功能

注意：

- 这个服务只做信息整理、车况档案和 Agent 协商辅助。
- 不测试支付、托管、贷款或金融推荐。
- 不要假设这已经是真实交易系统。
- 如果接口失败，请记录失败接口、请求摘要、响应状态和错误信息。
```

## 给 WorkBuddy 的提示词：车商 / 运营视角测试样例

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

安装后读取 OpenAPI：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

你这次扮演“车商 Agent / WorkBuddy-seller”和“平台运营观察员”，目标是测试车商是否能用这个 MVP 接住买家意向，并观察平台哪里需要优化。

请按顺序执行：

1. 创建一个车商/卖家用户，画像是：北京车商，重视透明档案，愿意合理议价。
2. 创建一个买家用户。
3. 发布一台测试车源，例如 2020 年本田雅阁，价格 13.8 万，目标成交价 13.3 万，地区北京。
4. 创建一个自动协商 session：调用 `POST /api/v1/agent/sessions`。
5. 设置 `seller_agent_name` 为 `WorkBuddy-seller`，`buyer_agent_name` 为 `Qclaw-buyer`。
6. 运行自动协商：调用 `POST /api/v1/agent/sessions/{session_id}/run`。
7. 查询 session 详情：调用 `GET /api/v1/agent/sessions/{session_id}`。
8. 检查 seller response 是否清楚说明车况、价格依据和可议价空间。
9. 用 `POST /api/v1/agent/events` 写入你的测试观察。

测试观察请包含：

- 车商发布车源流程是否自然
- 买家问题是否被卖家 Agent 正确理解
- 自动协商是否能保护车商底价
- conversations/events 是否足够让运营复盘
- 你作为车商 Agent 下一轮希望产品补什么功能

注意：

- 这个服务只形成沟通意向，不表达真实成交、支付、托管、贷款或金融推荐。
- 如果接口失败，请记录失败接口、请求摘要、响应状态和错误信息。
- 如果自动协商内容不自然，请保留原文片段并说明问题。
```

## 测试完成后的人工判断标准

可以发布 MVP，如果：

1. 两个 Agent 都能完成安装和 OpenAPI 读取。
2. 两个 Agent 都能成功跑完自动协商。
3. 每次测试都能留下 conversations 和 events。
4. 失败点可复现、可记录、不会阻断全部链路。

不要继续扩大功能范围，除非测试暴露的问题阻断 MVP 使用。

## 给其他 Agent 的通用提示词

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

安装后读取 OpenAPI：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

你这次作为外部测试 Agent 接入。你的 Agent 名称是：[填写你的名称]。

请完成一次 MVP 测试：

1. 创建买家用户。
2. 创建卖家用户。
3. 发布一台测试车源。
4. 创建自动协商 session，并把 `buyer_agent_name` 或 `seller_agent_name` 设置为你的 Agent 名称。
5. 运行自动协商。
6. 查询 session 详情。
7. 检查 conversations 和 events。
8. 调用 `POST /api/v1/agent/events` 写入你的测试观察，`actor_agent` 填你的 Agent 名称。

请明确记录：

- 你是哪一个 Agent
- 你扮演买家、卖家还是运营观察员
- 哪个接口最好用
- 哪个接口最容易出错
- 自动协商回复是否自然
- 下一轮最应该修什么

注意：
这个服务只做信息整理、车况档案和 Agent 协商辅助，不做支付、托管、贷款或金融推荐。
```
