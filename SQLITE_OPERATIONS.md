# SQLite Operations

更新时间：2026-04-26

## 目的

当前免费版 MVP 不使用 CloudBase SQL / MySQL，线上默认继续使用 SQLite。

这份手册解决两个问题：

1. 部署前把 CloudBase 容器里的 SQLite 下载到本地。
2. 部署后必要时把本地备份恢复回线上。

## 前提

CloudBase 服务必须配置：

```text
ADMIN_TOKEN=<强随机管理员令牌>
```

本地执行脚本前也要提供同一个令牌：

```bash
export ADMIN_TOKEN='<CloudBase 服务里的 ADMIN_TOKEN>'
```

## 部署前备份线上数据库

```bash
python scripts/cloud_sqlite_backup.py download --output-dir ./backups
```

默认请求：

```text
GET /api/v1/admin/database/backup
```

接口使用 `X-Admin-Token` 鉴权，只支持当前 SQLite-first 模式。

## 部署

仍然使用干净部署脚本：

```bash
scripts/deploy_cloudbase_clean.sh
```

注意：

1. 部署包会排除 `.env`、`.secrets`、`cloudbaserc.json` 和 `data/*.db`。
2. 不要把 SQLite 数据库文件提交到 GitHub。
3. 不要配置 `DATABASE_URL` 指向 CloudBase SQL / MySQL，除非已经接受付费和私有网络成本。

## 部署后验证

```bash
python scripts/smoke_test.py
```

如果要测线上接口，把脚本里的本地 `TestClient` 改成 HTTP 测试之前，先不要删除本地 smoke test；本地测试仍用于快速发现代码回归。

## 必要时恢复线上数据库

只有在部署后确认数据丢失，才执行恢复：

```bash
python scripts/cloud_sqlite_backup.py restore ./backups/cloud_sqlite_YYYYMMDD_HHMMSS.db
```

默认请求：

```text
POST /api/v1/admin/database/restore
```

恢复接口会：

1. 校验上传文件是有效 SQLite。
2. 先为线上当前数据库创建一份 `pre_restore` 备份。
3. 替换当前 SQLite 文件。
4. 重新初始化表结构，补齐缺失表。

## 限制

1. 这是免费版 MVP 的过渡方案，不是正式生产数据库方案。
2. 恢复操作会替换线上 SQLite，执行前必须确认备份文件正确。
3. 多实例运行时不要使用这个方案；CloudBase 云托管实例数应保持为 1。
4. 如果未来要长期保存线上业务数据，应迁移到外部数据库或 CloudBase 文档型数据库 HTTP API。
