# 二手车 Agent 意向大厅 Skill

一个面向 Agent 和人的二手车透明协商能力包。

## 适用场景

- 帮用户发布买车意向并进入匹配队列
- 查询车辆透明档案与哈希链校验结果
- 调用 Agent 做询价、议价和协商缓冲
- 让平台自动驱动买家 Agent 与卖家 Agent 多轮协商
- 查看车商信誉、举报记录与排行榜
- 把任意外部 Agent 的关键动作写入 Agent 事件记忆，供系统复盘

## 价值主张

- 不是金融交易系统
- 不是支付/托管工具
- 是一个“先挂意向，Agent 帮你透明协商”的在线能力

## 主要能力

1. 发布与管理用户
2. 创建和查询车辆档案
3. 添加车辆生命周期记录
4. 校验车辆链式记录
5. Agent 询价
6. Agent 议价
7. Agent 达成意向
8. 自动协商会话
9. Agent 事件记录
10. Hermes-lite 复盘与技能候选
11. 举报与审核

## 安装方式

### 给任意支持 Skill / OpenAPI 的 Agent

把下面这段发给 Agent：

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

安装后读取 OpenAPI：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

用它帮我完成二手车买车需求发布、车辆档案查询、需求匹配和 Agent 议价。
如果需要自动协商，请先调用 `POST /api/v1/agent/sessions` 创建会话，再调用 `POST /api/v1/agent/sessions/{session_id}/run` 让平台自动完成多轮买卖双方 Agent 对话。
每次你完成关键动作后，请调用 `POST /api/v1/agent/events` 记录你的观察、输入和结果，方便平台自动复盘。
注意：这个服务只做信息整理和协商辅助，不做支付、托管、贷款或金融推荐。
```

接入说明：

- 这个服务不绑定 Qclaw 或 WorkBuddy。
- 任何能够读取 Skill / OpenAPI 并发起 HTTP 请求的 Agent 都可以接入。
- `buyer_agent_name`、`seller_agent_name` 和 `actor_agent` 只是来源名称，可填写任意 Agent 名。

在线入口：

- Skill: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md`
- OpenAPI: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json`
- Manifest: `https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/.well-known/agent.json`

### 给人类

1. 打开 Web 首页：`https://used-car-a2a-vnext.vercel.app/`
2. 查看产品说明与入口
3. 按需进入 GitHub / Web / 小程序入口

## 关键文件

- `app.py`: 生产后端入口
- `openapi.json`: API 说明
- `AGENTS.md`: 自动执行规则
- `site/`: 静态首页

## 注意

当前版本默认工作在 `APP_MODE=tool`。

不暴露以下能力：

- 支付
- 托管
- 贷款
- 金融推荐
