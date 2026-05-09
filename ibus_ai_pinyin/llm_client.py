import json
import logging
import os
import re
import time

import requests


class LLMClient:
    def __init__(self, config):
        api = config.get("api", {})
        self.base_url = api.get("base_url", "http://127.0.0.1:8080/v1").rstrip("/")
        self.endpoint = api.get("endpoint", "/chat/completions")
        self.model = api.get("model", "qwen3-0.6b")
        self.timeout = api.get("timeout_ms", 800) / 1000
        self.temperature = api.get("temperature", 0.1)
        self.top_p = api.get("top_p", 0.8)
        self.max_tokens = api.get("max_tokens", 64)
        self.stream = api.get("stream", False)
        self.proxy_enabled = api.get("proxy_enabled", False)
        self.thinking = api.get("thinking", {})
        self.extra_body = api.get("extra_body", {})

        api_key = api.get("api_key", "")
        api_key_env = api.get("api_key_env", "OPENAI_API_KEY")
        self.api_key = api_key or os.environ.get(api_key_env, "sk-local")

        prompt = config.get("prompt", {})
        self.system_prompt = prompt.get(
            "system",
            "你是一个中文拼音输入法转换器。只输出 JSON 字符串数组。",
        )
        self.user_template = prompt.get(
            "user_template",
            "拼音：{pinyin}\n请输出中文候选 JSON 数组。",
        )

    def get_candidates(self, pinyin, max_candidates=5):
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_template.format(pinyin=pinyin)},
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": self.stream,
        }
        if isinstance(self.extra_body, dict):
            body.update(self.extra_body)
        if isinstance(self.thinking, dict) and self.thinking.get("enabled") is False:
            body["thinking"] = {"type": self.thinking.get("type", "disabled")}
        elif isinstance(self.thinking, dict) and self.thinking.get("enabled") is True:
            body["thinking"] = {"type": self.thinking.get("type", "enabled")}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        session = requests.Session()
        session.trust_env = bool(self.proxy_enabled)
        url = self.base_url + self.endpoint
        start = time.monotonic()
        try:
            resp = session.post(
                url,
                headers=headers,
                json=body,
                timeout=self.timeout,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logging.info(
                "LLM response received model=%s status=%s elapsed_ms=%s",
                self.model,
                resp.status_code,
                elapsed_ms,
            )
            resp.raise_for_status()
        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logging.exception(
                "LLM request failed model=%s elapsed_ms=%s url=%s",
                self.model,
                elapsed_ms,
                url,
            )
            raise
        data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        if not content:
            content = message.get("reasoning_content") or ""
            logging.info("LLM content empty, using reasoning_content fallback")
        logging.info("LLM raw output elapsed_ms=%s content=%r", elapsed_ms, content)
        candidates = self.parse_candidates(content, max_candidates=max_candidates)
        logging.info("LLM parsed candidates elapsed_ms=%s candidates=%r", elapsed_ms, candidates)
        return candidates

    def parse_candidates(self, content, max_candidates=5):
        text = content.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]

        arr = json.loads(text)
        if not isinstance(arr, list):
            return []

        result = []
        seen = set()
        for item in arr:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item or item in seen or not self.is_valid_candidate(item):
                continue
            seen.add(item)
            result.append(item)
            if len(result) >= max_candidates:
                break
        return result

    def is_valid_candidate(self, candidate):
        if re.search(r"[\u3400-\u9fff]", candidate):
            return True
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+#._-]{0,31}", candidate):
            return True
        return False
