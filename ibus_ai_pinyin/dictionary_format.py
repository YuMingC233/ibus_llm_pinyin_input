from ibus_ai_pinyin.pinyin_utils import (
    as_string_list,
    compact_pinyin,
    normalize_pinyin,
    normalize_short,
    normalize_text,
)


SUPPORTED_VERSION = "1.0"
VALID_TYPES = {
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


def normalize_weight(value, warnings, index):
    try:
        weight = int(value)
    except (TypeError, ValueError):
        warnings.append(f"第 {index} 条 weight 无效，已修正为 50")
        return 50
    if weight < 0:
        warnings.append(f"第 {index} 条 weight 小于 0，已修正为 0")
        return 0
    if weight > 100:
        warnings.append(f"第 {index} 条 weight 大于 100，已修正为 100")
        return 100
    return weight


def normalize_dictionary(data):
    warnings = []
    errors = []

    if not isinstance(data, dict):
        return None, ["词库文件必须是 JSON object"], []

    version = str(data.get("version", "")).strip()
    if version != SUPPORTED_VERSION:
        errors.append(f"version 必须为 {SUPPORTED_VERSION}")

    name = normalize_text(data.get("name", ""))
    if not name:
        errors.append("name 不能为空")

    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("entries 必须是数组")

    if errors:
        return None, errors, warnings

    normalized = {
        "version": version,
        "name": name,
        "description": normalize_text(data.get("description", "")),
        "source": normalize_text(data.get("source", "")),
        "locale": normalize_text(data.get("locale", "zh-CN")) or "zh-CN",
        "entries": [],
    }

    merged = {}
    skipped = 0
    for offset, raw_entry in enumerate(entries, start=1):
        if not isinstance(raw_entry, dict):
            skipped += 1
            warnings.append(f"第 {offset} 条不是 object，已跳过")
            continue

        term = normalize_text(raw_entry.get("term", ""))
        if not term:
            skipped += 1
            warnings.append(f"第 {offset} 条缺少 term，已跳过")
            continue

        entry_type = normalize_text(raw_entry.get("type", "other")) or "other"
        if entry_type not in VALID_TYPES:
            warnings.append(f"第 {offset} 条 type 无效，已修正为 other")
            entry_type = "other"

        enabled = raw_entry.get("enabled", True)
        if not isinstance(enabled, bool):
            warnings.append(f"第 {offset} 条 enabled 无效，已修正为 true")
            enabled = True

        pinyin_values = [normalize_pinyin(item) for item in as_string_list(raw_entry.get("pinyin"))]
        short_values = [normalize_short(item) for item in as_string_list(raw_entry.get("short"))]
        aliases = as_string_list(raw_entry.get("aliases"))
        tags = as_string_list(raw_entry.get("tags"))
        weight = normalize_weight(raw_entry.get("weight", 50), warnings, offset)
        comment = normalize_text(raw_entry.get("comment", ""))

        if term in merged:
            existing = merged[term]
            existing["weight"] = max(existing["weight"], weight)
            existing["enabled"] = existing["enabled"] or enabled
            existing["pinyin"] = _merge_lists(existing["pinyin"], pinyin_values)
            existing["short"] = _merge_lists(existing["short"], short_values)
            existing["aliases"] = _merge_lists(existing["aliases"], aliases)
            existing["tags"] = _merge_lists(existing["tags"], tags)
            if len(comment) > len(existing["comment"]):
                existing["comment"] = comment
            warnings.append(f"第 {offset} 条 term 重复，已合并")
            continue

        merged[term] = {
            "term": term,
            "normalized_term": normalize_text(term).lower(),
            "type": entry_type,
            "weight": weight,
            "enabled": enabled,
            "pinyin": pinyin_values,
            "compact_pinyin": [compact_pinyin(item) for item in pinyin_values],
            "short": short_values,
            "aliases": aliases,
            "tags": tags,
            "comment": comment,
        }

    normalized["entries"] = list(merged.values())
    normalized["total_entries"] = len(entries)
    normalized["skipped_entries"] = skipped
    return normalized, [], warnings


def _merge_lists(left, right):
    result = list(left)
    seen = set(result)
    for item in right:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
