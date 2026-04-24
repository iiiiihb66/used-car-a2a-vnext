# 二手车 Agent 意向大厅 Skill

一个面向 Agent 和人的二手车透明协商能力包。

## 适用场景

- 帮用户发布买车意向并进入匹配队列
- 查询车辆透明档案与哈希链校验结果
- 调用 Agent 做询价、议价和协商缓冲
- 查看车商信誉、举报记录与排行榜

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
8. 举报与审核

## 安装方式

### 给 Qclaw / OpenClaw

把下面这段发给 Agent：

```text
请安装并使用这个二手车 Agent 意向大厅 Skill：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/skill.md

安装后读取 OpenAPI：

https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com/openapi.json

用它帮我完成二手车买车需求发布、车辆档案查询、需求匹配和 Agent 议价。
注意：这个服务只做信息整理和协商辅助，不做支付、托管、贷款或金融推荐。
```

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
