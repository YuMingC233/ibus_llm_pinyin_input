#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ibus_ai_pinyin.dictionary_importer import DictionaryImporter
from ibus_ai_pinyin.dictionary_store import DomainDictionaryStore


def main():
    parser = argparse.ArgumentParser(description="Import ibus-ai-pinyin .dict.json files")
    parser.add_argument("path")
    parser.add_argument("--db", default="~/.config/ibus-ai-pinyin/cache.sqlite3")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", action="store_true", help="merge with existing terms (default)")
    parser.add_argument("--replace", action="store_true", help="replace mappings for existing terms")
    args = parser.parse_args()

    mode = "replace" if args.replace else "merge"
    store = DomainDictionaryStore(args.db)
    report = DictionaryImporter(store).import_file(args.path, mode=mode, dry_run=args.dry_run)

    print(f"正在导入词库：{report.get('dictionary_name', '')}")
    print(f"文件：{args.path}")
    print(f"读取词条：{report['total_entries']} 条")
    print(f"有效词条：{report['valid_entries']} 条")
    print(f"跳过词条：{report['skipped_entries']} 条")
    print(f"新增词条：{report['inserted_terms']} 条")
    print(f"更新词条：{report['updated_terms']} 条")
    print(f"新增拼音映射：{report['inserted_pinyin']} 条")
    print(f"新增别名：{report['inserted_aliases']} 条")
    print(f"新增标签：{report['inserted_tags']} 条")

    if report["warnings"]:
        print("\n警告：")
        for warning in report["warnings"]:
            print(f"- {warning}")
    if report["errors"]:
        print("\n错误：")
        for error in report["errors"]:
            print(f"- {error}")
        return 1
    if report["dry_run"]:
        print("\ndry-run 完成，未写入数据库。")
    else:
        print("\n导入完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
