import re


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value).strip())


def normalize_pinyin(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def compact_pinyin(value):
    return "".join(ch for ch in normalize_pinyin(value) if ch.isalnum())


def normalize_short(value):
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def as_string_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []

    result = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = normalize_text(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
