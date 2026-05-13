#!/usr/bin/env python3
"""
JSON 格式校验脚本 — 检查知识库文章是否符合标准格式。

用法：
    python .codex/hooks/validate_json.py knowledge/articles/github-20260317-001.json
    python .codex/hooks/validate_json.py knowledge/articles/*.json

Codex hook:
    在 requirements.toml 中显式传入 knowledge/articles 目录。

退出码：
    0 — 全部通过
    1 — 存在校验失败
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from MyGK_DB.knowledge_contract import (  # noqa: E402
    validate_article_contract,
    validate_index_contract,
)


def expand_json_files(args: list[str]) -> list[str]:
    files: list[str] = []
    for arg in args:
        path = Path(arg)
        if path.is_dir():
            files.extend(str(f) for f in sorted(path.glob("*.json")))
        else:
            files.append(arg)
    return files


# ── 校验函数 ─────────────────────────────────────────────────────────────

def validate_article(data: dict) -> list[str]:
    """
    校验单篇文章，返回错误列表。

    Args:
        data: 文章 JSON 数据

    Returns:
        错误消息列表，空列表表示校验通过
    """
    return validate_article_contract(data)


# ── CLI 入口 ─────────────────────────────────────────────────────────────

def main() -> int:
    files = expand_json_files(sys.argv[1:])
    if not files:
        print("[SKIP] 未发现需要校验的 knowledge/articles/*.json 文件")
        return 0

    total_files = 0
    failed_files = 0
    all_errors: dict[str, list[str]] = {}

    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            print(f"[SKIP] 文件不存在: {filepath}")
            continue
        if not path.suffix == ".json":
            print(f"[SKIP] 非 JSON 文件: {filepath}")
            continue

        total_files += 1

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            all_errors[filepath] = [f"JSON 解析失败: {e}"]
            failed_files += 1
            continue

        if path.name == "index.json":
            errors = validate_index_contract(data, path.parent)
        else:
            errors = validate_article(data)
        if errors:
            all_errors[filepath] = errors
            failed_files += 1

    # 输出结果
    print(f"\n{'='*50}")
    print(f"JSON 格式校验结果")
    print(f"{'='*50}")

    if all_errors:
        for filepath, errors in all_errors.items():
            print(f"\n[FAIL] {filepath}")
            for err in errors:
                print(f"  - {err}")
    else:
        print("\n[PASS] 所有文件校验通过")

    print(f"\n总计: {total_files} 文件, {total_files - failed_files} 通过, {failed_files} 失败")

    return 1 if failed_files > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
