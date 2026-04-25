# GitHub Actions 使用说明

## 目标

用 GitHub Actions 作为部署流水线：

1. Codex Cloud 或本地把代码推到 GitHub
2. GitHub Actions 安装 CloudBase CLI
3. GitHub Actions 使用腾讯云 API 密钥登录
4. GitHub Actions 部署 `used-car-a2a-vnext` 到 CloudBase 云托管

## 需要先配置的 GitHub Secrets

进入 GitHub 仓库：

`Settings -> Secrets and variables -> Actions -> New repository secret`

添加以下 4 个 secrets：

| Name | Value |
| --- | --- |
| `TCB_SECRET_ID` | 腾讯云访问管理里的 SecretId |
| `TCB_SECRET_KEY` | 腾讯云访问管理里的 SecretKey |
| `TCB_ENV_ID` | `car-assistant-prod-3dqle77ef680c` |
| `TCB_SERVICE_NAME` | `used-car-a2a-vnext` |

腾讯云 API 密钥可以在腾讯云控制台的访问管理/API 密钥管理里创建。

## 第一次使用

1. 打开 GitHub 仓库
2. 进入 `Actions`
3. 选择 `Deploy CloudBase`
4. 点击 `Run workflow`
5. 选择 `main`
6. 点击运行

运行成功后，GitHub Actions 会执行：

```bash
tcb login --apiKeyId "$TCB_SECRET_ID" --apiKey "$TCB_SECRET_KEY"
tcb cloudrun deploy -e "$TCB_ENV_ID" -s "$TCB_SERVICE_NAME" --source . --port 80 --force
```

## CloudBase 服务环境变量

生产环境变量先在 CloudBase 控制台里配置：

| Name | 说明 |
| --- | --- |
| `AI_API_KEY` | CloudBase AI / 混元 API Key |
| `AI_BASE_URL` | `https://car-assistant-prod-3dqle77ef680c.api.tcloudbasegateway.com/v1/ai/hunyuan/v1` |
| `AI_MODEL` | `hunyuan-turbos-latest` |
| `DATABASE_URL` | 可留空；留空时默认使用 SQLite |
| `DB_DIR` | 可选；指定 SQLite 落盘目录 |
| `ADMIN_TOKEN` | 管理员令牌 |
| `CORS_ORIGINS` | `https://used-car-a2a-vnext.vercel.app` |

这些值不写进 GitHub 仓库。

## 分工

- Codex Cloud：改代码、提交 GitHub
- GitHub Actions：测试和部署
- CloudBase：运行后端服务
- Vercel：运行静态首页

## 备注

当前工作流是手动触发，避免 secrets 尚未配置时每次 push 都失败。
等部署稳定后，可以再改成 `push main` 自动触发。
