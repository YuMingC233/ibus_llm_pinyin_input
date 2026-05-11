import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ibus_ai_pinyin.cache import CandidateCache
from ibus_ai_pinyin.candidate_ranker import merge_candidates
from ibus_ai_pinyin.dictionary_format import normalize_dictionary
from ibus_ai_pinyin.dictionary_store import DomainDictionaryStore
from ibus_ai_pinyin.keybindings import matches_keybinding
from ibus_ai_pinyin.local_candidates import get_local_candidates
from ibus_ai_pinyin.llm_client import LLMClient
from engine import AIPinyinEngine

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
    assert client.rank_candidates_by_context(
        ["鸿灵知识库检索功能", "鸿灵知识库搜索功能"],
        [{"text": "鸿灵", "weight": 85}, {"text": "知识库", "weight": 90}, {"text": "搜索", "weight": 85}],
    ) == ["鸿灵知识库搜索功能", "鸿灵知识库检索功能"]


def test_extract_complete_candidates_from_partial_json():
    client = LLMClient({"api": {}, "prompt": {}})
    assert client.extract_complete_candidates('["你好", "泥') == ["你好"]
    assert client.extract_complete_candidates('说明：["你好", "泥好", "你\\"号"') == [
        "你好",
        "泥好",
        '你"号',
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


def test_merge_candidates_keeps_source_order_and_dedupes():
    assert merge_candidates(["鸿灵MCP工具", "你好"], ["你好", "世界"], limit=3) == [
        "鸿灵MCP工具",
        "你好",
        "世界",
    ]
    assert merge_candidates(
        [],
        ["鸿灵知识库搜索功能"],
        ["红领巾知识库检索功能"],
        limit=5,
    ) == ["鸿灵知识库搜索功能", "红领巾知识库检索功能"]


def test_dictionary_normalize_merges_duplicate_terms():
    dictionary, errors, warnings = normalize_dictionary(
        {
            "version": "1.0",
            "name": "测试词库",
            "entries": [
                {
                    "term": " 鸿灵MCP工具 ",
                    "pinyin": "Hong Ling MCP Gong Ju",
                    "short": "HL-MCP",
                    "weight": 95,
                },
                {
                    "term": "鸿灵MCP工具",
                    "pinyin": ["hong ling mcp"],
                    "short": ["hlmcp"],
                    "weight": 120,
                },
            ],
        }
    )
    assert errors == []
    assert any("term 重复" in warning for warning in warnings)
    assert len(dictionary["entries"]) == 1
    entry = dictionary["entries"][0]
    assert entry["term"] == "鸿灵MCP工具"
    assert entry["weight"] == 100
    assert entry["pinyin"] == ["hong ling mcp gong ju", "hong ling mcp"]
    assert entry["short"] == ["hlmcp"]


def test_dictionary_store_import_and_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DomainDictionaryStore(os.path.join(tmpdir, "cache.sqlite3"))
        dictionary, errors, _warnings = normalize_dictionary(
            {
                "version": "1.0",
                "name": "测试词库",
                "entries": [
                    {
                        "term": "鸿灵MCP工具",
                        "pinyin": ["hong ling mcp gong ju"],
                        "short": ["hlmcp", "hlmcpgj"],
                        "type": "module",
                        "weight": 95,
                        "enabled": True,
                    },
                    {
                        "term": "禁用词",
                        "pinyin": ["jin yong ci"],
                        "weight": 99,
                        "enabled": False,
                    },
                ],
            }
        )
        assert errors == []
        report = store.import_dictionary(dictionary)
        assert report["inserted_terms"] == 2
        assert store.get_candidates("hong ling mcp gong ju", limit=5) == ["鸿灵MCP工具"]
        assert store.get_candidates("honglingmcpgongju", limit=5) == ["鸿灵MCP工具"]
        assert store.get_candidates("hlmcp", limit=5) == ["鸿灵MCP工具"]
        assert store.get_candidates("jin yong ci", limit=5) == []
        context = store.get_context_items("honglingmcpgongjuchajian", limit=5)
        assert [item["text"] for item in context] == ["鸿灵MCP工具"]


def test_toggle_keybinding():
    binding = {"enabled": True, "key": "space", "modifiers": ["Control"]}
    assert matches_keybinding(IBus, IBus.KEY_space, IBus.ModifierType.CONTROL_MASK, binding)
    assert not matches_keybinding(IBus, IBus.KEY_space, 0, binding)
    assert not matches_keybinding(IBus, IBus.KEY_a, IBus.ModifierType.CONTROL_MASK, binding)


def test_inline_symbol_detection():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    assert engine.accept_inline_symbol(",")
    assert engine.accept_inline_symbol("?")
    assert engine.accept_inline_symbol("-")
    assert not engine.accept_inline_symbol("a")
    assert not engine.accept_inline_symbol("1")
    assert not engine.accept_inline_symbol(" ")


def test_input_char_detection_accepts_digits():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    assert engine.accept_char("a")
    assert engine.accept_char("1")
    assert engine.accept_char("'")
    assert not engine.accept_char(",")


def test_initial_char_passthrough_detection():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    assert engine.should_passthrough_initial_char("1")
    assert not engine.should_passthrough_initial_char("a")
    assert not engine.should_passthrough_initial_char("'")


def test_caps_lock_state_detection():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    assert engine.is_caps_lock_active(IBus.ModifierType.LOCK_MASK)
    assert not engine.is_caps_lock_active(0)


def test_caps_lock_char_detection():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    assert engine.is_caps_lock_char("A")
    assert not engine.is_caps_lock_char("a")
    assert not engine.is_caps_lock_char("1")


def test_move_selection_wraps_candidates():
    engine = AIPinyinEngine.__new__(AIPinyinEngine)
    engine.candidates = ["你好", "你号", "拟好"]
    engine.selected_index = 0
    engine.show_candidates = lambda candidates: None
    engine.move_selection(1)
    assert engine.selected_index == 1
    engine.move_selection(-1)
    assert engine.selected_index == 0
    engine.move_selection(-1)
    assert engine.selected_index == 2


if __name__ == "__main__":
    test_parse_candidates()
    test_extract_complete_candidates_from_partial_json()
    test_cache_promote()
    test_local_candidates()
    test_merge_candidates_keeps_source_order_and_dedupes()
    test_dictionary_normalize_merges_duplicate_terms()
    test_dictionary_store_import_and_query()
    test_toggle_keybinding()
    test_inline_symbol_detection()
    test_input_char_detection_accepts_digits()
    test_initial_char_passthrough_detection()
    test_caps_lock_state_detection()
    test_caps_lock_char_detection()
    test_move_selection_wraps_candidates()
    print("ok")
