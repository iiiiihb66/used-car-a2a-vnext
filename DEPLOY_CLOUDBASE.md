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

## 必填环境变量

- `DATABASE_URL`
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

## 部署后检查

1. `/health` 返回 `healthy`
2. `/docs` 可以打开
3. 小程序能正常请求:
   - `/api/v1/cars`
   - `/api/v1/cars/{car_id}/verify`
   - `/api/v1/agent/inquiry`

## 注意

- 当前版本是工具型后端，不包含支付、托管、贷款与金融能力。
- 若使用 CloudBase SQL，请确保数据库白名单允许云托管访问。
