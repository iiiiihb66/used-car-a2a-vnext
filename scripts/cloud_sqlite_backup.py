#!/usr/bin/env python3
"""
下载或恢复 CloudBase 云托管中的 SQLite 数据库快照。

需要后端配置 ADMIN_TOKEN，并通过 X-Admin-Token 调用管理接口。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com"


def api_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def require_admin_token(args: argparse.Namespace) -> str:
    token = args.admin_token or os.getenv("ADMIN_TOKEN")
    if not token:
        raise SystemExit("[error] 请通过 --admin-token 或 ADMIN_TOKEN 提供管理员令牌")
    return token


def request_bytes(url: str, token: str, *, method: str = "GET", data: bytes | None = None) -> bytes:
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Admin-Token": token,
            "Content-Type": "application/octet-stream",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"[error] HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"[error] 请求失败: {exc}") from exc


def download_backup(args: argparse.Namespace) -> int:
    token = require_admin_token(args)
    url = api_url(args.api_base, "/api/v1/admin/database/backup")
    data = request_bytes(url, token)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"cloud_sqlite_{timestamp}.db"
    output_path.write_bytes(data)

    print(f"[ok] 已下载线上 SQLite 备份: {output_path}")
    return 0


def restore_backup(args: argparse.Namespace) -> int:
    token = require_admin_token(args)
    backup_path = Path(args.backup_file).expanduser().resolve()
    if not backup_path.exists():
        raise SystemExit(f"[error] 备份文件不存在: {backup_path}")

    url = api_url(args.api_base, "/api/v1/admin/database/restore")
    response = request_bytes(url, token, method="POST", data=backup_path.read_bytes())
    try:
        payload = json.loads(response.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {"raw": response.decode("utf-8", errors="replace")}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CloudBase SQLite 备份/恢复工具")
    parser.add_argument(
        "--api-base",
        default=os.getenv("PUBLIC_BASE_URL", DEFAULT_API_BASE),
        help="后端 API Base URL，默认读取 PUBLIC_BASE_URL 或线上 CloudBase 地址",
    )
    parser.add_argument(
        "--admin-token",
        default=None,
        help="管理员令牌；也可使用 ADMIN_TOKEN 环境变量",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="下载线上 SQLite 备份")
    download.add_argument(
        "--output-dir",
        default=os.getenv("SQLITE_BACKUP_DIR", "./backups"),
        help="备份输出目录，默认读取 SQLITE_BACKUP_DIR 或 ./backups",
    )
    download.set_defaults(func=download_backup)

    restore = subparsers.add_parser("restore", help="把本地 SQLite 备份恢复到线上")
    restore.add_argument("backup_file", help="本地 .db 备份文件路径")
    restore.set_defaults(func=restore_backup)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
