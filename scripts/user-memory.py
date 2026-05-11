#!/usr/bin/env python3
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ibus_ai_pinyin.config import load_config
from ibus_ai_pinyin.user_memory import UserMemoryStore


def build_store(path=None):
    config = load_config()
    cache_path = config.get("cache", {}).get("path", "~/.config/ibus-ai-pinyin/cache.sqlite3")
    memory_cfg = config.get("memory_dictionary", {})
    return UserMemoryStore(path or memory_cfg.get("path", cache_path))


def print_terms(terms):
    for item in terms:
        enabled = "on" if item["enabled"] else "off"
        short = item["short"] or "-"
        print(
            f"{item['term']}\t{item['pinyin']}\t{short}\t"
            f"weight={item['weight']}\tcount={item['confirm_count']}\t{enabled}"
        )


def main():
    parser = argparse.ArgumentParser(description="Manage ibus-ai-pinyin user memory dictionary")
    parser.add_argument("--db", help="SQLite database path, defaults to config memory_dictionary.path")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List learned terms")
    list_parser.add_argument("--all", action="store_true", help="Include disabled terms")
    list_parser.add_argument("--limit", type=int, default=100)

    search_parser = sub.add_parser("search", help="Search learned terms")
    search_parser.add_argument("query")
    search_parser.add_argument("--all", action="store_true", help="Include disabled terms")
    search_parser.add_argument("--limit", type=int, default=100)

    disable_parser = sub.add_parser("disable", help="Disable a term")
    disable_parser.add_argument("term")

    enable_parser = sub.add_parser("enable", help="Enable a term")
    enable_parser.add_argument("term")

    delete_parser = sub.add_parser("delete", help="Delete a term")
    delete_parser.add_argument("term")

    sub.add_parser("clear", help="Delete all learned terms")

    export_parser = sub.add_parser("export", help="Export as .dict.json")
    export_parser.add_argument("--all", action="store_true", help="Include disabled terms")

    args = parser.parse_args()
    store = build_store(args.db)

    if args.command == "list":
        print_terms(store.list_terms(include_disabled=args.all, limit=args.limit))
    elif args.command == "search":
        print_terms(store.list_terms(query=args.query, include_disabled=args.all, limit=args.limit))
    elif args.command == "disable":
        print(store.set_enabled(args.term, False))
    elif args.command == "enable":
        print(store.set_enabled(args.term, True))
    elif args.command == "delete":
        print(store.delete_term(args.term))
    elif args.command == "clear":
        print(store.clear_terms())
    elif args.command == "export":
        print(store.export_dictionary_json(include_disabled=args.all))


if __name__ == "__main__":
    main()
