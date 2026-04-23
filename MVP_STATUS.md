# MVP 状态与上线检查

## 当前结论

`used-car-a2a-vnext` 已经具备当前阶段适合上线验证的 MVP 主链路：

1. 用户创建
2. 车商发布车源
3. 用户发布购车需求
4. 平台返回可匹配车源
5. Agent 发起询价 / 议价 / 达成成交意向
6. 车辆档案写入生命周期记录并进行链式校验
7. 举报卖家并由管理员审核

当前版本定位：

- 工具型二手车 Agent 后端
- 信息整理、透明档案、协商辅助、信誉治理
- 不提供支付、托管、贷款或金融能力

## 已实现能力

### 用户与信誉

- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `GET /api/v1/users/{user_id}/reputation`
- `GET /api/v1/reputation/leaderboard`

### 车源与车档

- `POST /api/v1/cars`
- `GET /api/v1/cars`
- `GET /api/v1/cars/{car_id}`
- `GET /api/v1/users/{user_id}/cars`
- `POST /api/v1/cars/{car_id}/records`
- `GET /api/v1/cars/{car_id}/records`
- `GET /api/v1/cars/{car_id}/verify`

### 需求大厅与撮合

- `POST /api/v1/demands`
- `GET /api/v1/users/{user_id}/demands`
- `GET /api/v1/demands/{demand_id}`
- `GET /api/v1/demands/{demand_id}/matches`

### Agent 协商

- `POST /api/v1/agent/inquiry`
- `POST /api/v1/agent/negotiate`
- `POST /api/v1/agent/deal-intent`
- `GET /api/v1/conversations/{user_id}`

### 举报与治理

- `POST /api/v1/reports/seller`
- `GET /api/v1/admin/reports`
- `POST /api/v1/admin/reports/review`

## 已验证的主链路

本地已通过实际调用验证以下顺序：

1. 创建买家
2. 创建卖家
3. 卖家发布车辆
4. 买家发布需求
5. 平台返回匹配结果

验证结果：

- 买家创建 `200`
- 卖家创建 `200`
- 车辆创建 `200`
- 需求创建 `200`
- 匹配查询 `200`

## 仍未完成或仍为占位的能力

这些不影响当前 MVP，但还不算完整生产能力：

- `submit_demand` MCP 工具仍是 mock，HTTP API 已补齐
- `verify_identity` 仍是 mock
- `schedule_inspection` 仍是 mock
- AI 大模型能力依赖 CloudBase AI 配置完成后才是正式可用
- 生产数据库尚未切到 CloudBase SQL / MySQL

## 上线前必须补齐的配置

### 必填环境变量

- `DATABASE_URL`
- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_MODEL`
- `ADMIN_TOKEN`
- `CORS_ORIGINS`

### 推荐值

- `AI_BASE_URL`
  `https://car-assistant-prod-3dqle77ef680c.api.tcloudbasegateway.com/v1/ai/hunyuan/v1`
- `AI_MODEL`
  `hunyuan-turbos-latest`
- `CORS_ORIGINS`
  前端域名，开发阶段可先填 `*`

## 还缺的生产收尾

1. 在 CloudBase 服务里写入环境变量
2. 将数据库从默认本地模式切到 CloudBase SQL / MySQL
3. 为前端配置新的 API Base URL
4. 用真实 CloudBase AI Key 跑通一次询价与议价
5. 校验管理员接口的 `X-Admin-Token`

## 适合当前阶段的判断

结论不是“所有设想都实现了”，而是：

**当前这版已经实现了适合个人主体工具型产品的 MVP 核心能力。**

已经适合现在做的：

- 需求挂号
- 车源上架
- 平台匹配
- Agent 协商
- 透明车档
- 信誉与举报

暂不适合现在做的：

- 支付
- 托管
- 贷款
- 电子合同闭环
- 外部实名与验车系统深度接入
