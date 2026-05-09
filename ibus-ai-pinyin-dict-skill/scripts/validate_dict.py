#!/usr/bin/env python3
"""
Validate ibus-ai-pinyin .dict.json files.

Usage:
  python3 scripts/validate_dict.py examples/hongling.dict.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_TYPES = {
    "product",
    "project",
    "system",
    "module",
    "feature",
    "organization",
    "person",
    "tech",
    "abbreviation",
    "business",
    "mixed",
    "other",
}

PINYIN_RE = re.compile(r"^[a-z0-9 ._+\-/]+$")


def as_list(value: Any, field: str, index: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return value
    raise ValueError(f"entries[{index}].{field} must be a string or a list of strings")


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["Top-level value must be an object"]

    if data.get("version") != "1.0":
        errors.append('Top-level "version" must be "1.0"')

    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        errors.append('Top-level "name" is required and must be a non-empty string')

    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append('Top-level "entries" is required and must be a list')
        return errors

    seen_terms: set[str] = set()

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entries[{i}] must be an object")
            continue

        term = entry.get("term")
        if not isinstance(term, str) or not term.strip():
            errors.append(f"entries[{i}].term is required and must be a non-empty string")
            continue

        if len(term) > 64:
            errors.append(f"entries[{i}].term is too long: {term!r}")

        if term in seen_terms:
            errors.append(f"Duplicate term: {term!r}")
        seen_terms.add(term)

        if "weight" in entry:
            weight = entry["weight"]
            if not isinstance(weight, int) or not (0 <= weight <= 100):
                errors.append(f"entries[{i}].weight must be an integer between 0 and 100")

        if "enabled" in entry and not isinstance(entry["enabled"], bool):
            errors.append(f"entries[{i}].enabled must be true or false")

        if "type" in entry and entry["type"] not in ALLOWED_TYPES:
            errors.append(
                f"entries[{i}].type must be one of {sorted(ALLOWED_TYPES)}, got {entry['type']!r}"
            )

        try:
            pinyins = as_list(entry.get("pinyin"), "pinyin", i)
            shorts = as_list(entry.get("short"), "short", i)
        except ValueError as exc:
            errors.append(str(exc))
            pinyins = []
            shorts = []

        for p in pinyins:
            if p != p.lower():
                errors.append(f"entries[{i}].pinyin should be lowercase: {p!r}")
            if not PINYIN_RE.match(p):
                errors.append(f"entries[{i}].pinyin contains unusual characters: {p!r}")

        for s in shorts:
            if s != s.lower():
                errors.append(f"entries[{i}].short should be lowercase: {s!r}")
            if not re.match(r"^[a-z0-9]+$", s):
                errors.append(f"entries[{i}].short should contain only lowercase letters/numbers: {s!r}")

        aliases = entry.get("aliases", [])
        if aliases is not None:
            if not isinstance(aliases, list) or not all(isinstance(x, str) for x in aliases):
                errors.append(f"entries[{i}].aliases must be a list of strings")
            elif any(not x.strip() for x in aliases):
                errors.append(f"entries[{i}].aliases contains empty string")

        tags = entry.get("tags", [])
        if tags is not None:
            if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
                errors.append(f"entries[{i}].tags must be a list of strings")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_dict.py <file.dict.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    errors = validate(path)

    if errors:
        print(f"Validation failed: {path}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
