# 二手车 Agent 意向大厅 Skill

这是一个面向 Qclaw / OpenClaw / 通用 Agent 的二手车意向撮合工具。

## 服务入口

- Base URL: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com`
- OpenAPI: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json`
- 健康检查: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/health`
- 静态 Skill 备份: `https://used-car-a2a-vnext.vercel.app/skill.md`

## 业务定位

- 工具型二手车协作后端
- 帮用户发布买车需求、录入车辆档案、查询匹配结果
- 帮 Agent 执行询价、议价、达成见面/沟通意向
- 帮平台自动驱动买家 Agent 与卖家 Agent 多轮协商
- 记录 Qclaw / WorkBuddy 执行轨迹，并沉淀为复盘和技能候选
- 不提供支付、托管、贷款、金融推荐

## Agent 使用方式

1. 读取 `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json`
2. 使用 `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com` 作为 API base URL
3. 先调用 `POST /api/v1/users` 创建买家或车商用户
4. 车商调用 `POST /api/v1/cars?user_id={seller_id}` 发布车源
5. 买家调用 `POST /api/v1/demands` 发布买车需求
6. 调用 `GET /api/v1/demands/{demand_id}/matches` 查看匹配车源
7. 需要单步协商时调用 `/api/v1/agent/inquiry`、`/api/v1/agent/negotiate`、`/api/v1/agent/deal-intent`
8. 需要自动协商时调用 `POST /api/v1/agent/sessions` 创建会话，再调用 `POST /api/v1/agent/sessions/{session_id}/run`
9. 调用 `GET /api/v1/agent/sessions/{session_id}` 查看完整对话、事件和复盘轨迹
10. 关键执行结果调用 `POST /api/v1/agent/events` 写入 Agent 记忆

## 自动协商流程

1. 创建买家、卖家和车辆。
2. 调用 `POST /api/v1/agent/sessions`，传入 `buyer_id`、`seller_id`、`car_id`、预算和买家目标。
3. 调用返回的 `run_url`，平台会自动完成“买家询价 -> 卖家回复 -> 买家判断 -> 买家报价 -> 卖家回应”的多轮循环。
4. 如果返回 `final_state=deal_ready`，说明已接近成交意向，下一步应线下复核车况和身份。
5. 如果返回 `final_state=needs_human_review`，说明需要补充车况档案、调整预算或人工介入。

## 推荐提示词

请安装并使用这个二手车 Agent 意向大厅 Skill：

`https://used-car-a2a-vnext.vercel.app/skill.md`

安装后，先读取 OpenAPI，并帮我完成一次测试流程：

- 创建一个买家用户
- 创建一个车商用户
- 发布一辆测试车源
- 发布一个买车需求
- 查询需求匹配结果
- 创建并运行一次自动协商会话
- 记录一次 Agent 事件，说明你观察到了什么

如果接口返回正常，再根据我的真实买车需求继续使用。

## 合规边界

这个服务只做信息整理和协商辅助，不做支付、托管、贷款或金融推荐。
