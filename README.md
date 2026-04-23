# 二手车 A2A 档案协商工具

这是一个面向微信小程序和 Agent 场景的工具型后端。

## 当前定位

- 车辆档案录入与展示
- 链式哈希验真
- Agent 询价/议价/达成意向
- 信誉榜与举报治理

## 不包含

- 支付
- 托管
- 贷款
- 金融推荐

## 本地启动

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

启动后访问:

- `http://127.0.0.1:8000/docs`

## 关键环境变量

复制 `.env.example` 为 `.env` 后填写:

- `DATABASE_URL`
- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_MODEL`
- `ADMIN_TOKEN`
- `CORS_ORIGINS`

## CloudBase 部署

见 [DEPLOY_CLOUDBASE.md](/Users/fuhongbo/Documents/Antigravity/项目对比/used-car-a2a-vnext/DEPLOY_CLOUDBASE.md)

## Vercel 首页部署

这个仓库已经包含静态首页源码和 `vercel.json`。

直接把 GitHub 仓库导入 Vercel 即可：

1. 选择仓库 `used-car-a2a-vnext`
2. 保持默认构建设置
3. 不需要额外的 build command
4. 首页根路径 `/` 会自动指向 `site/index.html`

静态首页源码位于：

- `site/index.html`
- `site/styles.css`

## 开发同步规则

开始任何本地或云端开发前先运行：

```bash
./scripts/ensure_latest.sh
```

详细说明见 [WORKFLOW.md](/Users/fuhongbo/Documents/Antigravity/项目对比/used-car-a2a-vnext/WORKFLOW.md)

## 上线入口

- 正式服务入口: `app.py`
- 历史实验入口: `main.py`

云托管请使用 `app.py`，不要使用旧的 `main.py`。
