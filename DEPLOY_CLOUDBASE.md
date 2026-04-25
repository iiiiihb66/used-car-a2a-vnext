# CloudBase 部署说明

## 目标

将 `used-car-a2a-vnext` 作为 CloudBase 云托管服务部署，供微信小程序调用。

## 前置条件

1. 已开通 CloudBase 环境
2. 已安装 Node.js
3. 已安装 CLI

```bash
npm install -g @cloudbase/cli@latest
```

4. 已登录

```bash
tcb login
```

## 环境变量

- `DATABASE_URL`（可选，不填则默认 SQLite）
- `DB_DIR`（可选，指定 SQLite 数据目录）
- `SQLITE_FILENAME`（可选）
- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_MODEL`
- `ADMIN_TOKEN`
- `CORS_ORIGINS`

## 推荐的 CloudBase AI 配置

- `AI_BASE_URL`: `https://<ENV_ID>.api.tcloudbasegateway.com/v1/ai/hunyuan/v1`
- `AI_MODEL`: `hunyuan-turbos-latest`

## 本地验证

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

访问:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## 部署到云托管

在项目目录执行:

```bash
tcb cloudrun deploy -e <ENV_ID> -s <SERVICE_NAME> --source .
```

建议服务名:

- `used-car-a2a-vnext`

## 免费 / 个人版 MVP 推荐路径

如果目标是不升级套餐，建议这样配：

1. 不开 CloudBase SQL / MySQL。
2. 不配置 `DATABASE_URL`，让服务继续使用 SQLite。
3. 将实例数控制在 `1`，先按单实例 MVP 运行。
4. 用 `python scripts/backup_sqlite.py` 定期导出数据库快照。

这条路径的优点是改动最小、成本最低，适合先验证产品闭环。

## GitHub Actions 自动部署

仓库已提供手动触发的工作流:

- `.github/workflows/deploy-cloudbase.yml`

需要在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 添加:

- `TCB_SECRET_ID`
- `TCB_SECRET_KEY`
- `TCB_ENV_ID`
- `TCB_SERVICE_NAME`

配置完成后，在 GitHub `Actions -> Deploy CloudBase -> Run workflow` 手动部署。
详细步骤见 `GITHUB_ACTIONS.md`。

## 部署后检查

1. `/health` 返回 `healthy`
2. `/docs` 可以打开
3. 小程序能正常请求:
   - `/api/v1/cars`
   - `/api/v1/cars/{car_id}/verify`
   - `/api/v1/agent/inquiry`

## 注意

- 当前版本是工具型后端，不包含支付、托管、贷款与金融能力。
- 若未来启用 CloudBase SQL / MySQL，请先确认套餐、私有网络与实例成本。
- 不建议在多实例场景下继续依赖单个 SQLite 文件作为在线主库。
