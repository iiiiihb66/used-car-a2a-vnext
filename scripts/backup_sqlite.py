#!/usr/bin/env python3
"""
创建 SQLite 一致性备份。

用途：
1. CloudBase 免费/个人版继续使用本地 SQLite 时，手动导出快照。
2. 将备份文件同步到挂载存储或本地归档目录，降低重部署丢数风险。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def resolve_sqlite_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("当前 DATABASE_URL 不是 SQLite，跳过备份。")
    return Path(database_url[len(prefix):]).expanduser().resolve()


def backup_sqlite_file(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"{source.stem}_{timestamp}.db"
    temp_target = target.with_suffix(".tmp")

    with sqlite3.connect(source) as src_conn, sqlite3.connect(temp_target) as dst_conn:
        src_conn.backup(dst_conn)

    temp_target.replace(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="备份当前 SQLite 数据库文件")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("SQLITE_BACKUP_DIR", "./backups"),
        help="备份输出目录，默认读取 SQLITE_BACKUP_DIR 或 ./backups",
    )
    args = parser.parse_args()

    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parent.parent / 'data' / 'c2c_platform.db'}",
    )

    try:
        source = resolve_sqlite_path(database_url)
    except ValueError as exc:
        print(f"[skip] {exc}")
        return 0

    if not source.exists():
        print(f"[error] SQLite 文件不存在: {source}")
        return 1

    target = backup_sqlite_file(source, Path(args.output_dir).expanduser().resolve())
    print(f"[ok] 已创建备份: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
