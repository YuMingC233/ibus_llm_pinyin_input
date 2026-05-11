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
from ibus_ai_pinyin.user_memory import UserMemoryStore


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


def merge_context_items(*groups):
    result = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = item.get("text") if isinstance(item, dict) else None
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(item)
    return result


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

        memory_cfg = self.config.get("memory_dictionary", {})
        self.memory_cfg = memory_cfg
        self.memory_enabled = memory_cfg.get("enabled", True)
        self.user_memory = UserMemoryStore(
            memory_cfg.get("path", cache_cfg.get("path", "~/.config/ibus-ai-pinyin/cache.sqlite3"))
        )

        self.buffer = ""
        self.candidates = []
        self.selected_index = 0
        self.is_requesting = False
        self.request_id = 0
        self.input_cfg = self.config.get("input", {})
        self.zh_mode = self.input_cfg.get("default_mode", "zh") != "en"
        self.toggle_key = self.input_cfg.get("toggle_key", {})
        self.edit_mode = False
        self.edit_text = ""
        self.edit_cursor = 0
        self.edit_original_pinyin = ""
        self.edit_original_candidate = ""
        self.edit_candidates_snapshot = []
        self.edit_replacement_buffer = ""
        self.edit_replacement_candidates = []

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        logging.debug(
            "key event keyval=%s keycode=%s state=%s caps=%s",
            keyval,
            keycode,
            int(state),
            self.is_caps_lock_active(state),
        )

        if matches_keybinding(IBus, keyval, state, self.toggle_key):
            self.toggle_input_mode()
            return True

        if not self.zh_mode:
            return False

        if self.edit_mode:
            return self.process_edit_key_event(keyval, state)

        ctrl_digit_index = self.ctrl_digit_index(keyval, keycode, state)
        if self.candidates and ctrl_digit_index is not None:
            index = ctrl_digit_index
            if index < len(self.candidates):
                self.start_candidate_edit(index)
                return True

        if self.is_caps_lock_active(state):
            if self.buffer or self.candidates:
                logging.info(
                    "caps lock active clearing buffer_len=%s candidates=%s",
                    len(self.buffer),
                    len(self.candidates),
                )
                self.clear_all()
            return False

        if state & PASSTHROUGH_MODIFIERS:
            if self.buffer or self.candidates:
                logging.info(
                    "passthrough shortcut clearing keyval=%s keycode=%s state=%s buffer_len=%s candidates=%s",
                    keyval,
                    keycode,
                    int(state),
                    len(self.buffer),
                    len(self.candidates),
                )
                self.clear_all()
            return False

        if self.candidates and keyval in (IBus.KEY_Up, IBus.KEY_Down):
            direction = -1 if keyval == IBus.KEY_Up else 1
            self.move_selection(direction)
            return True

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
            logging.debug("space pressed buffer_len=%s candidates=%s", len(self.buffer), len(self.candidates))
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

        if self.is_caps_lock_char(ch):
            if self.buffer or self.candidates:
                logging.info(
                    "caps lock char clearing char=%s buffer_len=%s candidates=%s",
                    ch,
                    len(self.buffer),
                    len(self.candidates),
                )
                self.clear_all()
            return False

        if not self.buffer and not self.candidates and self.should_passthrough_initial_char(ch):
            logging.debug("initial char passthrough char=%s", ch)
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
                logging.debug("buffer appended buffer_len=%s", len(self.buffer))
                return True

        if self.buffer and self.accept_inline_symbol(ch):
            max_len = self.config.get("input", {}).get("max_buffer_length", 120)
            if len(self.buffer) < max_len:
                self.buffer += ch
                self.candidates = []
                self.hide_lookup_table()
                self.update_composition_ui()
                logging.debug("buffer symbol appended buffer_len=%s", len(self.buffer))
                return True

        if self.candidates:
            self.commit_candidate(self.selected_index)
            return False
        if self.buffer and ch.isprintable() and not ch.isspace():
            self.commit_raw()
            return False

        return False

    def accept_char(self, ch):
        return ch.isascii() and (ch.isalnum() or ch in ["'", " "])

    def accept_inline_symbol(self, ch):
        return ch.isascii() and ch.isprintable() and not ch.isalnum() and not ch.isspace()

    def should_passthrough_initial_char(self, ch):
        return ch.isascii() and ch.isdigit()

    def should_passthrough_key(self, keyval):
        return keyval in PASSTHROUGH_KEYS or IBus.KEY_F1 <= keyval <= IBus.KEY_F35

    def ctrl_digit_index(self, keyval, keycode=None, state=0):
        if not state & IBus.ModifierType.CONTROL_MASK:
            return None
        if IBus.KEY_1 <= keyval <= IBus.KEY_9:
            return keyval - IBus.KEY_1
        if IBus.KEY_KP_1 <= keyval <= IBus.KEY_KP_9:
            return keyval - IBus.KEY_KP_1
        if keycode is not None:
            # X11/IBus commonly reports top-row 1..9 as hardware keycodes 10..18
            # even when Ctrl changes keyval into a non-printable control value.
            if 10 <= keycode <= 18:
                return keycode - 10
            # Some Wayland/evdev paths report top-row 1..9 as keycodes 2..10.
            if 2 <= keycode <= 10:
                return keycode - 2

        ch = IBus.keyval_to_unicode(keyval)
        if isinstance(ch, int):
            ch = chr(ch) if ch else ""
        if isinstance(ch, str) and len(ch) == 1 and "1" <= ch <= "9":
            return ord(ch) - ord("1")
        return None

    def is_caps_lock_active(self, state):
        return bool(state & IBus.ModifierType.LOCK_MASK)

    def is_caps_lock_char(self, ch):
        return ch.isascii() and ch.isalpha() and ch.isupper()

    def toggle_input_mode(self):
        self.zh_mode = not self.zh_mode
        self.clear_all()
        self.update_mode_property()
        logging.info("input mode toggled mode=%s", "zh" if self.zh_mode else "en")

    def register_mode_property(self):
        prop_list = IBus.PropList()
        prop_list.append(self.create_mode_property())
        self.register_properties(prop_list)
        logging.debug("mode property registered mode=%s", "zh" if self.zh_mode else "en")

    def update_mode_property(self):
        self.update_property(self.create_mode_property())
        logging.debug("mode property updated mode=%s", "zh" if self.zh_mode else "en")

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

    def update_edit_ui(self):
        if self.edit_replacement_buffer:
            text = f"{self.edit_text}\n{self.edit_replacement_buffer}"
        else:
            text = self.edit_text
        cursor = min(self.edit_cursor, len(self.edit_text))
        self.update_preedit_text(IBus.Text.new_from_string(text), cursor, True)
        self.update_auxiliary_text(IBus.Text.new_from_string("候选修改"), True)

    def start_candidate_edit(self, index):
        pinyin = " ".join(self.buffer.split())
        self.edit_mode = True
        self.edit_text = self.candidates[index]
        self.edit_cursor = len(self.edit_text)
        self.edit_original_pinyin = pinyin
        self.edit_original_candidate = self.candidates[index]
        self.edit_candidates_snapshot = list(self.candidates)
        self.edit_replacement_buffer = ""
        self.edit_replacement_candidates = []
        self.candidates = []
        self.hide_lookup_table()
        self.update_edit_ui()
        logging.info("candidate edit started candidate_len=%s", len(self.edit_text))

    def process_edit_key_event(self, keyval, state):
        if state & PASSTHROUGH_MODIFIERS and not (
            keyval == IBus.KEY_Return and state & IBus.ModifierType.CONTROL_MASK
        ):
            return False

        if self.edit_replacement_candidates and IBus.KEY_1 <= keyval <= IBus.KEY_9:
            index = keyval - IBus.KEY_1
            if index < len(self.edit_replacement_candidates):
                self.apply_edit_replacement(self.edit_replacement_candidates[index])
                return True

        if keyval == IBus.KEY_Left:
            self.edit_cursor = max(0, self.edit_cursor - 1)
            self.update_edit_ui()
            return True
        if keyval == IBus.KEY_Right:
            self.edit_cursor = min(len(self.edit_text), self.edit_cursor + 1)
            self.update_edit_ui()
            return True
        if keyval == IBus.KEY_Home:
            self.edit_cursor = 0
            self.update_edit_ui()
            return True
        if keyval == IBus.KEY_End:
            self.edit_cursor = len(self.edit_text)
            self.update_edit_ui()
            return True

        if keyval == IBus.KEY_BackSpace:
            if self.edit_replacement_buffer:
                self.edit_replacement_buffer = self.edit_replacement_buffer[:-1]
                self.edit_replacement_candidates = []
                self.hide_lookup_table()
            elif self.edit_cursor > 0:
                self.edit_text = self.edit_text[: self.edit_cursor - 1] + self.edit_text[self.edit_cursor :]
                self.edit_cursor -= 1
            self.update_edit_ui()
            return True
        if keyval == IBus.KEY_Delete:
            if self.edit_cursor < len(self.edit_text):
                self.edit_text = self.edit_text[: self.edit_cursor] + self.edit_text[self.edit_cursor + 1 :]
                self.update_edit_ui()
                return True
            return False

        if keyval == IBus.KEY_space:
            if self.edit_replacement_buffer:
                self.request_edit_replacement_candidates()
                return True
            self.insert_edit_text(" ")
            return True

        if keyval == IBus.KEY_Return:
            save_memory = not bool(state & IBus.ModifierType.CONTROL_MASK)
            self.commit_edited_candidate(save_memory=save_memory)
            return True

        if keyval == IBus.KEY_Escape:
            self.exit_candidate_edit(restore_candidates=True)
            return True

        ch = IBus.keyval_to_unicode(keyval)
        if isinstance(ch, int):
            if ch == 0:
                return False
            ch = chr(ch)
        if not ch:
            return False
        if self.accept_char(ch):
            self.edit_replacement_buffer += ch.lower()
            self.edit_replacement_candidates = []
            self.hide_lookup_table()
            self.update_edit_ui()
            return True
        if ch.isprintable() and not ch.isspace():
            self.insert_edit_text(ch)
            return True
        return False

    def insert_edit_text(self, text):
        self.edit_text = self.edit_text[: self.edit_cursor] + text + self.edit_text[self.edit_cursor :]
        self.edit_cursor += len(text)
        self.update_edit_ui()

    def request_edit_replacement_candidates(self):
        pinyin = " ".join(self.edit_replacement_buffer.split())
        max_candidates = self.config.get("candidate", {}).get("max_candidates", 5)
        candidates = get_local_candidates(pinyin, limit=max_candidates)
        if len(candidates) < max_candidates:
            try:
                candidates = merge_candidates(
                    candidates,
                    self.llm.get_candidates(pinyin, max_candidates=max_candidates),
                    limit=max_candidates,
                )
            except Exception as exc:
                logging.warning("edit replacement candidate request failed: %s", exc)
        self.edit_replacement_candidates = candidates
        if candidates:
            self.show_edit_replacement_candidates(candidates)
        else:
            self.insert_edit_text(self.edit_replacement_buffer)
            self.edit_replacement_buffer = ""
            self.update_edit_ui()

    def show_edit_replacement_candidates(self, candidates):
        table = IBus.LookupTable.new(
            page_size=self.config.get("input", {}).get("candidate_page_size", 5),
            cursor_pos=0,
            cursor_visible=True,
            round=True,
        )
        for candidate in candidates:
            table.append_candidate(IBus.Text.new_from_string(candidate))
        self.update_lookup_table(table, True)
        self.update_edit_ui()

    def apply_edit_replacement(self, text):
        self.insert_edit_text(text)
        self.edit_replacement_buffer = ""
        self.edit_replacement_candidates = []
        self.hide_lookup_table()
        self.update_edit_ui()

    def commit_edited_candidate(self, save_memory=True):
        text = self.edit_text
        pinyin = self.edit_original_pinyin
        original = self.edit_original_candidate
        self.commit_text(IBus.Text.new_from_string(text))
        if save_memory and self.memory_enabled:
            self.save_candidate_correction(pinyin, original, text)
        self.clear_all()

    def save_candidate_correction(self, pinyin, original, corrected):
        if self.memory_cfg.get("record_corrections", True):
            self.user_memory.record_correction(pinyin, original, corrected)
        if not self.memory_cfg.get("auto_learn", True):
            return
        if not self.user_memory.should_auto_learn(
            corrected,
            min_han=self.memory_cfg.get("auto_learn_min_han", 2),
            max_han=self.memory_cfg.get("auto_learn_max_han", 12),
        ):
            logging.info("candidate correction recorded without term learning corrected_len=%s", len(corrected))
            return
        learned = self.user_memory.learn_term(
            corrected,
            pinyin,
            weight=self.memory_cfg.get("default_weight", 80),
            max_weight=self.memory_cfg.get("max_weight", 120),
        )
        if learned and self.cache_enabled:
            self.cache.put_many(pinyin, [corrected], source="user_memory")
            self.cache.promote(pinyin, corrected)
        logging.info("candidate correction learned=%s corrected_len=%s", learned, len(corrected))

    def exit_candidate_edit(self, restore_candidates=False):
        candidates_snapshot = list(self.edit_candidates_snapshot)
        self.edit_mode = False
        self.edit_text = ""
        self.edit_cursor = 0
        self.edit_original_pinyin = ""
        self.edit_original_candidate = ""
        self.edit_candidates_snapshot = []
        self.edit_replacement_buffer = ""
        self.edit_replacement_candidates = []
        self.hide_lookup_table()
        if restore_candidates:
            self.candidates = candidates_snapshot
            if self.candidates:
                self.show_candidates(self.candidates)
                return
            self.update_composition_ui()
        else:
            self.update_preedit_text(IBus.Text.new_from_string(""), 0, False)

    def request_candidates(self):
        if self.is_requesting:
            return

        pinyin = " ".join(self.buffer.split())
        max_candidates = self.config.get("candidate", {}).get("max_candidates", 5)
        logging.info("candidate request started chars=%s", len(pinyin))

        dictionary_context = []
        user_context = []
        user_exact_candidates = []
        if self.memory_enabled:
            if self.memory_cfg.get("exact_match_candidate", True):
                user_exact_candidates = self.user_memory.get_exact_candidates(
                    pinyin,
                    limit=max_candidates,
                )
                if user_exact_candidates:
                    logging.info("user memory exact candidate count=%s", len(user_exact_candidates))
            if self.memory_cfg.get("send_to_llm", True):
                user_context = self.user_memory.get_context_items(
                    pinyin,
                    limit=self.memory_cfg.get("max_context_terms", 8),
                )
                if user_context:
                    logging.info("user memory context count=%s", len(user_context))

        if self.dictionary_enabled:
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
            user_exact_candidates,
            cached,
            local_candidates,
            limit=max_candidates,
        )
        llm_context = merge_context_items(user_context, dictionary_context)
        if not llm_context and len(merged) >= max_candidates:
            self.show_candidates(merged)
            return

        if merged:
            self.show_candidates(merged)

        self.is_requesting = True
        self.request_id += 1
        request_id = self.request_id
        self.update_composition_ui(" ...")

        threading.Thread(
            target=self.fetch_candidates_worker,
            args=(
                request_id,
                pinyin,
                max_candidates,
                cached,
                local_candidates,
                llm_context,
                user_exact_candidates,
            ),
            daemon=True,
        ).start()

    def fetch_candidates_worker(
        self,
        request_id,
        pinyin,
        max_candidates,
        cached=None,
        local_candidates=None,
        dictionary_context=None,
        user_exact_candidates=None,
    ):
        candidates = []
        try:
            for candidate in self.llm.stream_candidates(
                pinyin,
                max_candidates=max_candidates,
                dictionary_context=dictionary_context or [],
            ):
                if candidate not in candidates:
                    candidates.append(candidate)
                    logging.info("LLM stream candidate ready count=%s", len(candidates))
                    GLib.idle_add(
                        self.on_candidates_delta,
                        request_id,
                        pinyin,
                        list(candidates),
                        cached or [],
                        local_candidates or [],
                        dictionary_context or [],
                        max_candidates,
                    )
            logging.info("LLM candidates ready count=%s", len(candidates))
            if not candidates:
                logging.info("LLM stream returned empty, falling back to non-stream")
                candidates = self.llm.get_candidates(
                    pinyin,
                    max_candidates=max_candidates,
                    dictionary_context=dictionary_context or [],
                )
                logging.info("LLM fallback candidates ready count=%s", len(candidates))
        except Exception as exc:
            logging.warning("LLM stream request failed, falling back to non-stream: %s", exc)
            try:
                candidates = self.llm.get_candidates(
                    pinyin,
                    max_candidates=max_candidates,
                    dictionary_context=dictionary_context or [],
                )
                logging.info("LLM fallback candidates ready count=%s", len(candidates))
            except Exception as fallback_exc:
                logging.warning("LLM fallback request failed: %s", fallback_exc)
                candidates = []
        if not candidates:
            candidates = get_local_candidates(pinyin, limit=max_candidates)
            if candidates:
                logging.info("local candidates ready count=%s", len(candidates))
        if dictionary_context:
            merged = merge_candidates(
                user_exact_candidates or [],
                candidates,
                cached or [],
                local_candidates or [],
                limit=max_candidates,
            )
        else:
            merged = merge_candidates(
                user_exact_candidates or [],
                cached or [],
                local_candidates or [],
                candidates,
                limit=max_candidates,
            )
        GLib.idle_add(self.on_candidates_ready, request_id, pinyin, merged)

    def on_candidates_delta(
        self,
        request_id,
        pinyin,
        candidates,
        cached,
        local_candidates,
        dictionary_context,
        max_candidates,
    ):
        current = " ".join(self.buffer.split())
        if request_id != self.request_id or current != pinyin:
            return False

        if dictionary_context:
            merged = merge_candidates(
                candidates,
                cached,
                local_candidates,
                limit=max_candidates,
            )
        else:
            merged = merge_candidates(
                cached,
                local_candidates,
                candidates,
                limit=max_candidates,
            )
        if merged:
            self.show_candidates(merged)
        return False

    def on_candidates_ready(self, request_id, pinyin, candidates):
        self.is_requesting = False

        current = " ".join(self.buffer.split())
        if request_id != self.request_id or current != pinyin:
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
        if self.selected_index >= len(candidates):
            self.selected_index = len(candidates) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        table = IBus.LookupTable.new(
            page_size=self.config.get("input", {}).get("candidate_page_size", 5),
            cursor_pos=self.selected_index,
            cursor_visible=True,
            round=True,
        )
        for candidate in candidates:
            table.append_candidate(IBus.Text.new_from_string(candidate))

        self.update_lookup_table(table, True)
        self.update_composition_ui()
        logging.info("lookup table shown count=%s", len(candidates))

    def move_selection(self, direction):
        if not self.candidates:
            return
        self.selected_index = (self.selected_index + direction) % len(self.candidates)
        self.show_candidates(self.candidates)
        logging.info("candidate selection moved index=%s", self.selected_index)

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
        self.request_id += 1
        self.edit_mode = False
        self.edit_text = ""
        self.edit_cursor = 0
        self.edit_original_pinyin = ""
        self.edit_original_candidate = ""
        self.edit_candidates_snapshot = []
        self.edit_replacement_buffer = ""
        self.edit_replacement_candidates = []
        self.buffer = ""
        self.candidates = []
        self.selected_index = 0
        self.is_requesting = False
        self.update_composition_ui()
        self.hide_lookup_table()

    def do_focus_in(self):
        logging.debug("focus in mode=%s", "zh" if self.zh_mode else "en")
        self.register_mode_property()
        self.update_mode_property()

    def do_focus_out(self):
        logging.debug("focus out buffer_len=%s candidates=%s", len(self.buffer), len(self.candidates))
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
