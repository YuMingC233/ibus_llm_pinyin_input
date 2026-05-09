#!/usr/bin/env python3
import logging
import os
import threading

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus

from ibus_ai_pinyin.cache import CandidateCache
from ibus_ai_pinyin.candidate_ranker import merge_candidates
from ibus_ai_pinyin.config import load_config
from ibus_ai_pinyin.dictionary_store import DomainDictionaryStore
from ibus_ai_pinyin.keybindings import matches_keybinding
from ibus_ai_pinyin.local_candidates import get_local_candidates
from ibus_ai_pinyin.llm_client import LLMClient


LOG_PATH = os.path.expanduser("~/.cache/ibus-ai-pinyin/engine.log")
INPUT_MODE_PROP_KEY = "InputMode"
PASSTHROUGH_MODIFIERS = (
    IBus.ModifierType.CONTROL_MASK
    | IBus.ModifierType.MOD1_MASK
    | IBus.ModifierType.SUPER_MASK
    | IBus.ModifierType.HYPER_MASK
    | IBus.ModifierType.META_MASK
)
PASSTHROUGH_KEYS = {
    IBus.KEY_Tab,
    IBus.KEY_ISO_Left_Tab,
    IBus.KEY_Left,
    IBus.KEY_Right,
    IBus.KEY_Up,
    IBus.KEY_Down,
    IBus.KEY_Home,
    IBus.KEY_End,
    IBus.KEY_Page_Up,
    IBus.KEY_Page_Down,
    IBus.KEY_Insert,
    IBus.KEY_Delete,
}


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


class AIPinyinEngine(IBus.Engine):
    def __init__(self, bus, object_path):
        super().__init__(connection=bus.get_connection(), object_path=object_path)
        self.config = load_config()
        self.llm = LLMClient(self.config)

        cache_cfg = self.config.get("cache", {})
        self.cache_enabled = cache_cfg.get("enabled", True)
        self.cache = CandidateCache(
            cache_cfg.get("path", "~/.config/ibus-ai-pinyin/cache.sqlite3")
        )

        dict_cfg = self.config.get("dictionary", {})
        self.dictionary_enabled = dict_cfg.get("enabled", True)
        self.dictionary_max_candidates = dict_cfg.get("max_candidates", 5)
        self.dictionary = DomainDictionaryStore(
            dict_cfg.get("path", cache_cfg.get("path", "~/.config/ibus-ai-pinyin/cache.sqlite3"))
        )

        self.buffer = ""
        self.candidates = []
        self.selected_index = 0
        self.is_requesting = False
        self.input_cfg = self.config.get("input", {})
        self.zh_mode = self.input_cfg.get("default_mode", "zh") != "en"
        self.toggle_key = self.input_cfg.get("toggle_key", {})

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        logging.info("key event keyval=%s keycode=%s state=%s", keyval, keycode, int(state))

        if matches_keybinding(IBus, keyval, state, self.toggle_key):
            self.toggle_input_mode()
            return True

        if not self.zh_mode:
            return False

        if state & PASSTHROUGH_MODIFIERS:
            if self.buffer or self.candidates:
                logging.info(
                    "passthrough shortcut clearing buffer_len=%s candidates=%s",
                    len(self.buffer),
                    len(self.candidates),
                )
                self.clear_all()
            return False

        if self.should_passthrough_key(keyval):
            if self.buffer or self.candidates:
                logging.info(
                    "passthrough key clearing keyval=%s buffer_len=%s candidates=%s",
                    keyval,
                    len(self.buffer),
                    len(self.candidates),
                )
                self.clear_all()
            return False

        if self.candidates and IBus.KEY_1 <= keyval <= IBus.KEY_9:
            index = keyval - IBus.KEY_1
            if index < len(self.candidates):
                self.commit_candidate(index)
                return True

        if keyval == IBus.KEY_space:
            logging.info("space pressed buffer_len=%s candidates=%s", len(self.buffer), len(self.candidates))
            if self.candidates:
                self.commit_candidate(self.selected_index)
                return True
            if self.buffer:
                self.request_candidates()
                return True
            return False

        if keyval == IBus.KEY_Return:
            if self.candidates:
                self.commit_candidate(self.selected_index)
                return True
            if self.buffer:
                self.commit_raw()
                return True
            return False

        if keyval == IBus.KEY_Escape:
            if self.buffer or self.candidates:
                self.clear_all()
                return True
            return False

        if keyval == IBus.KEY_BackSpace:
            if self.candidates:
                self.candidates = []
                self.hide_lookup_table()
                self.update_composition_ui()
                return True
            if self.buffer:
                self.buffer = self.buffer[:-1]
                self.update_composition_ui()
                return True
            return False

        ch = IBus.keyval_to_unicode(keyval)
        if isinstance(ch, int):
            if ch == 0:
                return False
            ch = chr(ch)
        if not ch:
            return False

        if self.accept_char(ch):
            if self.candidates:
                self.commit_candidate(self.selected_index)
            max_len = self.config.get("input", {}).get("max_buffer_length", 120)
            if len(self.buffer) < max_len:
                self.buffer += ch.lower()
                self.candidates = []
                self.hide_lookup_table()
                self.update_composition_ui()
                logging.info("buffer appended buffer_len=%s", len(self.buffer))
                return True

        if self.candidates:
            self.commit_candidate(self.selected_index)
            return False
        if self.buffer and ch.isprintable() and not ch.isspace():
            self.commit_raw()
            return False

        return False

    def accept_char(self, ch):
        return ch.isascii() and (ch.isalpha() or ch in ["'", " "])

    def should_passthrough_key(self, keyval):
        return keyval in PASSTHROUGH_KEYS or IBus.KEY_F1 <= keyval <= IBus.KEY_F35

    def toggle_input_mode(self):
        self.zh_mode = not self.zh_mode
        self.clear_all()
        self.update_mode_property()
        logging.info("input mode toggled mode=%s", "zh" if self.zh_mode else "en")

    def register_mode_property(self):
        prop_list = IBus.PropList()
        prop_list.append(self.create_mode_property())
        self.register_properties(prop_list)
        logging.info("mode property registered mode=%s", "zh" if self.zh_mode else "en")

    def update_mode_property(self):
        self.update_property(self.create_mode_property())
        logging.info("mode property updated mode=%s", "zh" if self.zh_mode else "en")

    def create_mode_property(self):
        label = "中" if self.zh_mode else "英"
        tooltip = "AI 拼音输入：中文模式" if self.zh_mode else "AI 拼音输入：英文模式"
        symbol = "中" if self.zh_mode else "英"
        prop = IBus.Property(
            key=INPUT_MODE_PROP_KEY,
            type=IBus.PropType.NORMAL,
            label=label,
            icon="",
            tooltip=tooltip,
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            symbol=symbol,
        )
        return prop

    def update_composition_ui(self, suffix=""):
        self.update_preedit_text(IBus.Text.new_from_string(""), 0, False)

        text = self.buffer + suffix
        if text:
            self.update_auxiliary_text(IBus.Text.new_from_string(text), True)
        else:
            self.update_auxiliary_text(IBus.Text.new_from_string(""), False)

    def request_candidates(self):
        if self.is_requesting:
            return

        pinyin = " ".join(self.buffer.split())
        max_candidates = self.config.get("candidate", {}).get("max_candidates", 5)
        logging.info("candidate request started chars=%s", len(pinyin))

        domain_candidates = []
        dictionary_context = []
        if self.dictionary_enabled:
            domain_candidates = self.dictionary.get_candidates(
                pinyin,
                limit=self.dictionary_max_candidates,
            )
            if domain_candidates:
                logging.info("domain dictionary candidates count=%s", len(domain_candidates))
            dictionary_context = self.dictionary.get_context_items(
                pinyin,
                limit=self.dictionary_max_candidates,
            )
            if dictionary_context:
                logging.info("domain dictionary context count=%s", len(dictionary_context))

        cached = []
        if self.cache_enabled:
            cached = self.cache.get(pinyin, limit=max_candidates)
            if cached:
                logging.info("candidate cache hit count=%s", len(cached))

        local_candidates = get_local_candidates(pinyin, limit=max_candidates)
        if local_candidates:
            logging.info("local candidates immediate count=%s", len(local_candidates))

        merged = merge_candidates(
            domain_candidates,
            cached,
            local_candidates,
            limit=max_candidates,
        )
        if len(merged) >= max_candidates:
            self.show_candidates(merged)
            return

        self.is_requesting = True
        self.update_composition_ui(" ...")

        threading.Thread(
            target=self.fetch_candidates_worker,
            args=(
                pinyin,
                max_candidates,
                domain_candidates,
                cached,
                local_candidates,
                dictionary_context,
            ),
            daemon=True,
        ).start()

    def fetch_candidates_worker(
        self,
        pinyin,
        max_candidates,
        domain_candidates=None,
        cached=None,
        local_candidates=None,
        dictionary_context=None,
    ):
        try:
            candidates = self.llm.get_candidates(
                pinyin,
                max_candidates=max_candidates,
                dictionary_context=dictionary_context or [],
            )
            logging.info("LLM candidates ready count=%s", len(candidates))
        except Exception as exc:
            logging.warning("LLM request failed: %s", exc)
            candidates = []
        if not candidates:
            candidates = get_local_candidates(pinyin, limit=max_candidates)
            if candidates:
                logging.info("local candidates ready count=%s", len(candidates))
        if dictionary_context:
            merged = merge_candidates(
                domain_candidates or [],
                candidates,
                cached or [],
                local_candidates or [],
                limit=max_candidates,
            )
        else:
            merged = merge_candidates(
                domain_candidates or [],
                cached or [],
                local_candidates or [],
                candidates,
                limit=max_candidates,
            )
        GLib.idle_add(self.on_candidates_ready, pinyin, merged)

    def on_candidates_ready(self, pinyin, candidates):
        self.is_requesting = False

        current = " ".join(self.buffer.split())
        if current != pinyin:
            return False

        if candidates:
            if self.cache_enabled:
                self.cache.put_many(pinyin, candidates)
            self.show_candidates(candidates)
        else:
            logging.info("candidate request returned empty")
            self.update_composition_ui()
        return False

    def show_candidates(self, candidates):
        self.candidates = candidates
        self.selected_index = 0

        table = IBus.LookupTable.new(
            page_size=self.config.get("input", {}).get("candidate_page_size", 5),
            cursor_pos=0,
            cursor_visible=True,
            round=True,
        )
        for candidate in candidates:
            table.append_candidate(IBus.Text.new_from_string(candidate))

        self.update_lookup_table(table, True)
        self.update_composition_ui()
        logging.info("lookup table shown count=%s", len(candidates))

    def commit_candidate(self, index):
        if not self.candidates or index >= len(self.candidates):
            return

        pinyin = " ".join(self.buffer.split())
        text = self.candidates[index]
        self.commit_text(IBus.Text.new_from_string(text))

        if self.cache_enabled:
            self.cache.promote(pinyin, text)

        self.clear_all()

    def commit_raw(self):
        self.commit_text(IBus.Text.new_from_string(self.buffer))
        self.clear_all()

    def clear_all(self):
        self.buffer = ""
        self.candidates = []
        self.selected_index = 0
        self.is_requesting = False
        self.update_composition_ui()
        self.hide_lookup_table()

    def do_focus_in(self):
        logging.info("focus in mode=%s", "zh" if self.zh_mode else "en")
        self.register_mode_property()
        self.update_mode_property()

    def do_focus_out(self):
        logging.info("focus out buffer_len=%s candidates=%s", len(self.buffer), len(self.candidates))
        self.clear_all()


class EngineFactory(IBus.Factory):
    def __init__(self, bus):
        super().__init__(
            connection=bus.get_connection(),
            object_path=IBus.PATH_FACTORY,
        )
        self.bus = bus
        self.engine_id = 0

    def do_create_engine(self, engine_name):
        self.engine_id += 1
        object_path = f"/org/freedesktop/IBus/Engine/AIPinyin/{self.engine_id}"
        return AIPinyinEngine(self.bus, object_path)


def main():
    setup_logging()
    logging.info("AI Pinyin engine starting")
    IBus.init()
    bus = IBus.Bus()
    EngineFactory(bus)
    bus.request_name("org.freedesktop.IBus.AIPinyin", 0)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
