import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ibus_ai_pinyin.cache import CandidateCache
from ibus_ai_pinyin.keybindings import matches_keybinding
from ibus_ai_pinyin.local_candidates import get_local_candidates
from ibus_ai_pinyin.llm_client import LLMClient

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus


def test_parse_candidates():
    client = LLMClient({"api": {}, "prompt": {}})
    assert client.parse_candidates('候选：```json\n["你好", "你号", "你好", 1]\n```') == [
        "你好",
        "你号",
    ]
    assert client.parse_candidates('说明文字 ["中文候选"] 其他文字') == ["中文候选"]
    assert client.parse_candidates('["bào cuò", "报错", "bug"]') == [
        "报错",
        "bug",
    ]


def test_cache_promote():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CandidateCache(os.path.join(tmpdir, "cache.sqlite3"))
        cache.put_many("nihao", ["你好", "你号"])
        cache.promote("nihao", "你号")
        assert cache.get("nihao", limit=2) == ["你号", "你好"]


def test_local_candidates():
    assert get_local_candidates("ni hao", limit=1) == ["你好"]
    assert get_local_candidates("meiyou", limit=5) == ["没有"]
    assert get_local_candidates("haishi meiyou", limit=5) == ["还是没有"]
    assert get_local_candidates("baocuo", limit=5) == ["报错"]
    assert get_local_candidates("xiufu", limit=5) == ["修复"]
    assert get_local_candidates("unknown", limit=5) == []


def test_toggle_keybinding():
    binding = {"enabled": True, "key": "space", "modifiers": ["Control"]}
    assert matches_keybinding(IBus, IBus.KEY_space, IBus.ModifierType.CONTROL_MASK, binding)
    assert not matches_keybinding(IBus, IBus.KEY_space, 0, binding)
    assert not matches_keybinding(IBus, IBus.KEY_a, IBus.ModifierType.CONTROL_MASK, binding)


if __name__ == "__main__":
    test_parse_candidates()
    test_cache_promote()
    test_local_candidates()
    test_toggle_keybinding()
    print("ok")
