# Ubuntu 下基于 IBus 的大模型拼音输入法开发文档

## 1. 项目目标

本项目目标是在 Ubuntu 桌面环境下开发一个基于 IBus 框架的输入法引擎。用户直接输入拼音，输入法在用户按下触发键后调用大模型，将拼音转换为中文候选项，并允许用户选择候选后提交到当前输入框。

本方案不依赖传统拼音词库，不使用 Rime / Fcitx / libpinyin 作为主转换引擎，而是直接使用大模型完成“拼音到中文”的转换。为了便于模型切换，请求接口采用 OpenAI API 的 Chat Completions 兼容格式，支持配置不同厂商、不同本地模型服务或远程模型服务。

示例交互：

```text
用户输入：nihao
按下空格
候选：1. 你好  2. 你号  3. 倪浩
按下 1 或空格
提交：你好
```

长句示例：

```text
用户输入：wo yao xie yi pian guan yu ai shuru fa de wen zhang
按下空格
候选：
1. 我要写一篇关于 AI 输入法的文章
2. 我要写一篇关于爱输入法的文章
3. 我要写一篇关于 AI 输入法的文档
```

## 2. 设计原则

这个输入法不是传统拼音输入法的复刻，而是一个“大模型驱动的拼音转中文输入法”。因此设计重点与传统输入法不同。

第一，输入法逻辑尽量简单。IBus 负责捕获按键、显示预编辑文本、显示候选项、提交文本；大模型负责根据拼音生成中文候选。

第二，请求接口必须可配置。不同用户可能使用 OpenAI、通义千问兼容接口、智谱兼容接口、本地 llama.cpp server、本地 Ollama OpenAI 兼容接口等，因此不能把模型服务写死。

第三，模型调用必须低延迟。输入法是高频交互工具，不能每输入一个字母就请求大模型。MVP 版本只在用户按下空格、回车或指定触发键时调用模型。

第四，必须有缓存。相同拼音的结果应该优先走本地缓存，不应该反复请求模型。用户选择过的候选也应该提升权重。

第五，错误时不能阻塞输入。模型服务不可用、超时、返回格式错误时，输入法应该允许用户提交原始拼音，避免用户无法继续打字。

## 3. 技术选型

### 3.1 输入法框架

使用 IBus。

原因：

```text
Ubuntu / GNOME 默认集成较好
Python 原型开发速度快
支持 preedit、lookup table、candidate、commit text 等输入法核心能力
适合快速验证大模型输入法逻辑
```

### 3.2 开发语言

使用 Python 3。

原因：

```text
IBus Python GI 绑定可用
调用 HTTP API 简单
方便读取 JSON 配置
方便接 SQLite 缓存
原型迭代成本低
```

### 3.3 大模型接口

使用 OpenAI-compatible Chat Completions 接口。

默认请求形式：

```http
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json
```

请求体：

```json
{
  "model": "qwen3-0.6b",
  "messages": [
    {
      "role": "system",
      "content": "你是一个拼音输入法转换器，只输出 JSON 数组。"
    },
    {
      "role": "user",
      "content": "把下面的拼音转换成中文候选：nihao"
    }
  ],
  "temperature": 0.1,
  "max_tokens": 64,
  "stream": false
}
```

响应解析路径：

```text
choices[0].message.content
```

模型应返回：

```json
["你好", "你号", "倪浩"]
```

## 4. 总体架构

```text
┌──────────────────────────┐
│ 当前应用输入框             │
│ GTK / Qt / Chrome / VSCode │
└─────────────▲────────────┘
              │ commit_text
┌─────────────┴────────────┐
│ IBus AI Pinyin Engine     │
│                            │
│ - 捕获键盘事件              │
│ - 维护拼音 buffer           │
│ - 更新 preedit              │
│ - 展示候选词 lookup table    │
│ - 提交候选                  │
└─────────────▲────────────┘
              │ candidates
┌─────────────┴────────────┐
│ Candidate Manager          │
│                            │
│ - 查缓存                    │
│ - 调用 LLM Client           │
│ - 解析 JSON                 │
│ - 排序和去重                │
└─────────────▲────────────┘
              │ HTTP
┌─────────────┴────────────┐
│ OpenAI-compatible API      │
│                            │
│ - OpenAI                   │
│ - llama.cpp server          │
│ - Ollama compatible API     │
│ - vLLM                      │
│ - 自定义模型服务             │
└──────────────────────────┘
```

## 5. 功能范围

### 5.1 MVP 功能

MVP 版本需要实现以下功能：

```text
输入英文字母，进入拼音 buffer
实时显示 preedit 拼音
按空格触发大模型转换
显示候选词列表
按数字键 1-9 选择候选
按空格提交第一个候选
按回车提交第一个候选或原始拼音
按 Esc 清空 buffer
按 Backspace 删除 buffer 最后一个字符
模型失败时提交原始拼音
支持配置 base_url、api_key、model
支持 SQLite 缓存
```

### 5.2 非 MVP 功能

以下能力不建议第一版实现：

```text
实时逐字请求模型
复杂分词
云端用户词库同步
拼音纠错
模糊音
双拼
上下文跨应用记忆
复杂配置 GUI
```

这些功能可以在 MVP 稳定后逐步增加。

## 6. 系统依赖

### 6.1 Ubuntu 依赖

```bash
sudo apt update
sudo apt install -y \
  ibus \
  python3 \
  python3-gi \
  gir1.2-ibus-1.0 \
  python3-requests \
  sqlite3
```

如果系统没有启用 IBus，可执行：

```bash
im-config -n ibus
```

然后注销重新登录。

### 6.2 Python 依赖

为了降低安装复杂度，MVP 可以只使用系统包：

```text
python3-gi
requests
sqlite3 标准库
json 标准库
threading 标准库
queue 标准库
```

如果后续需要更复杂配置，可以加入：

```bash
pip install pydantic pyyaml
```

但第一版不建议引入太多依赖。

## 7. 项目目录结构

建议使用用户级安装，不污染系统目录。

```text
~/.local/share/ibus-ai-pinyin/
├── engine.py                 # IBus 输入法主程序
├── llm_client.py             # OpenAI-compatible API 请求封装
├── config.py                 # 配置读取
├── cache.py                  # SQLite 缓存
├── prompts.py                # Prompt 模板
├── utils.py                  # 工具函数
└── README.md

~/.local/share/ibus/component/
└── ai-pinyin.xml             # IBus component 注册文件

~/.config/ibus-ai-pinyin/
├── config.json               # 用户配置
└── cache.sqlite3             # 候选缓存
```

## 8. 配置文件设计

配置文件路径：

```text
~/.config/ibus-ai-pinyin/config.json
```

示例配置：

```json
{
  "api": {
    "base_url": "http://127.0.0.1:8080/v1",
    "api_key": "",
    "api_key_env": "OPENAI_API_KEY",
    "model": "qwen3-0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 800,
    "temperature": 0.1,
    "top_p": 0.8,
    "max_tokens": 64,
    "stream": false
  },
  "input": {
    "max_buffer_length": 120,
    "trigger_keys": ["space"],
    "commit_first_candidate_with_space": true,
    "enter_commit_raw_when_no_candidate": true,
    "candidate_page_size": 5
  },
  "candidate": {
    "max_candidates": 5,
    "deduplicate": true,
    "allow_ascii": false,
    "fallback_to_raw_pinyin": true
  },
  "cache": {
    "enabled": true,
    "path": "~/.config/ibus-ai-pinyin/cache.sqlite3",
    "ttl_days": 30,
    "promote_user_selection": true
  },
  "prompt": {
    "system": "你是一个中文拼音输入法转换器。你的任务是把用户输入的拼音转换成最可能的中文候选。只输出 JSON 字符串数组，不要解释，不要 Markdown，不要代码块。最多输出 5 个候选。",
    "user_template": "拼音：{pinyin}\n请输出中文候选 JSON 数组。"
  }
}
```

### 8.1 本地 llama.cpp server 配置示例

```json
{
  "api": {
    "base_url": "http://127.0.0.1:8080/v1",
    "api_key": "sk-local",
    "model": "qwen3-0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 800,
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }
}
```

### 8.2 Ollama OpenAI 兼容接口配置示例

```json
{
  "api": {
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "ollama",
    "model": "qwen3:0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 1200,
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }
}
```

### 8.3 远程 OpenAI-compatible 服务配置示例

```json
{
  "api": {
    "base_url": "https://api.example.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model": "your-fast-model",
    "endpoint": "/chat/completions",
    "timeout_ms": 1000,
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }
}
```

## 9. Prompt 设计

输入法场景的 Prompt 必须短、硬、稳定，不要让模型自由发挥。

推荐 system prompt：

```text
你是一个中文拼音输入法转换器。
你的任务是把用户输入的拼音转换成最可能的中文候选。
只输出 JSON 字符串数组，不要解释，不要 Markdown，不要代码块。
最多输出 5 个候选。
候选必须是中文短语或中文句子。
不要输出拼音本身。
不要输出英文，除非拼音明显表示 AI、API、CPU、GPU、IBus、Linux 等技术词。
```

推荐 user prompt：

```text
拼音：{pinyin}
请输出中文候选 JSON 数组。
```

示例：

```text
拼音：wo yao xie yi pian guan yu ai shuru fa de wenzhang
请输出中文候选 JSON 数组。
```

模型输出：

```json
["我要写一篇关于 AI 输入法的文章", "我要写一篇关于爱输入法的文章"]
```

## 10. HTTP 请求封装设计

### 10.1 请求地址拼接

配置项：

```json
{
  "base_url": "http://127.0.0.1:8080/v1",
  "endpoint": "/chat/completions"
}
```

最终 URL：

```text
http://127.0.0.1:8080/v1/chat/completions
```

### 10.2 请求头

```http
Authorization: Bearer {api_key}
Content-Type: application/json
```

如果 api_key 为空，可以仍然传一个本地占位值，例如：

```text
sk-local
```

部分本地 OpenAI-compatible 服务不校验 key，但仍要求 Authorization header 存在。

### 10.3 请求体

```json
{
  "model": "qwen3-0.6b",
  "messages": [
    {
      "role": "system",
      "content": "你是一个中文拼音输入法转换器。只输出 JSON 字符串数组。"
    },
    {
      "role": "user",
      "content": "拼音：nihao\n请输出中文候选 JSON 数组。"
    }
  ],
  "temperature": 0.1,
  "top_p": 0.8,
  "max_tokens": 64,
  "stream": false
}
```

### 10.4 响应格式

OpenAI-compatible Chat Completions 常见响应：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "qwen3-0.6b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "[\"你好\", \"你号\", \"倪浩\"]"
      },
      "finish_reason": "stop"
    }
  ]
}
```

解析路径：

```python
content = data["choices"][0]["message"]["content"]
```

然后对 content 做 JSON 解析。

### 10.5 返回容错

模型有时可能返回：

````text
```json
["你好", "你号"]
````

````

或者：

```text
候选：["你好", "你号"]
````

因此解析器需要做容错：

```text
去除 Markdown 代码块
提取第一个 [ 到最后一个 ] 之间的内容
尝试 json.loads
过滤非字符串元素
去重
限制候选数量
```

## 11. 缓存设计

### 11.1 为什么必须有缓存

输入法是高频操作。如果每次输入同一个拼音都请求模型，体验会很差，也会增加成本。

缓存解决三个问题：

```text
提升速度
降低模型调用成本
让用户选择过的候选越来越靠前
```

### 11.2 SQLite 表结构

```sql
CREATE TABLE IF NOT EXISTS candidates (
  pinyin TEXT NOT NULL,
  candidate TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'llm',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (pinyin, candidate)
);

CREATE INDEX IF NOT EXISTS idx_candidates_pinyin_score
ON candidates (pinyin, score DESC, updated_at DESC);
```

### 11.3 查询逻辑

```sql
SELECT candidate
FROM candidates
WHERE pinyin = ?
ORDER BY score DESC, updated_at DESC
LIMIT ?;
```

### 11.4 写入逻辑

模型返回候选后写入缓存：

```sql
INSERT INTO candidates (pinyin, candidate, score, source, created_at, updated_at)
VALUES (?, ?, 0, 'llm', ?, ?)
ON CONFLICT(pinyin, candidate)
DO UPDATE SET updated_at = excluded.updated_at;
```

用户选择候选后提升分数：

```sql
UPDATE candidates
SET score = score + 10,
    updated_at = ?
WHERE pinyin = ? AND candidate = ?;
```

## 12. IBus 引擎状态机

输入法内部维护以下状态：

```python
buffer: str                 # 当前拼音输入
candidates: list[str]       # 当前候选
candidate_visible: bool     # 候选窗口是否显示
selected_index: int         # 当前选中候选
is_requesting: bool         # 是否正在请求模型
```

状态流转：

```text
空闲状态
  ↓ 输入字母
拼音编辑状态
  ↓ 空格
请求候选状态
  ↓ 模型返回
候选选择状态
  ↓ 数字键 / 空格 / 回车
提交文本并回到空闲状态
```

异常流转：

```text
请求候选状态
  ↓ 超时 / 异常 / 空结果
候选失败状态
  ↓ 回车
提交原始拼音
```

## 13. 按键设计

| 按键              | 行为                              |
| --------------- | ------------------------------- |
| a-z             | 加入拼音 buffer                     |
| '               | 作为拼音分隔符加入 buffer，可选             |
| 空格              | 有候选时提交当前候选；无候选时触发模型转换           |
| 回车              | 有候选时提交当前候选；无候选时提交原始拼音           |
| 数字 1-9          | 选择对应候选并提交                       |
| Backspace       | 删除 buffer 最后一个字符；如果候选显示则先返回编辑状态 |
| Esc             | 清空 buffer 和候选                   |
| PageUp/PageDown | 候选翻页，后续版本实现                     |
| 左右方向键           | 候选选择，后续版本实现                     |

MVP 可以先不实现复杂翻页，只显示最多 5 个候选。

## 14. 候选展示设计

IBus 中使用 `IBus.LookupTable` 展示候选。

候选格式：

```text
1. 你好
2. 你号
3. 倪浩
```

在 IBus LookupTable 里，候选文本只放中文，不需要手动拼数字序号。IBus UI 会根据当前环境显示候选列表。

候选生成后执行：

```python
self.update_lookup_table(table, True)
```

清空候选时执行：

```python
self.hide_lookup_table()
```

## 15. 异步请求设计

不能在 `do_process_key_event` 中同步请求模型，否则 UI 会卡住。

错误示例：

```python
def do_process_key_event(...):
    candidates = call_llm(self.buffer)  # 阻塞 UI，不推荐
```

正确做法：

```text
按空格
  ↓
启动后台线程请求模型
  ↓
立即返回 True
  ↓
preedit 显示“nihao ...”或“正在转换”
  ↓
后台线程拿到结果
  ↓
通过 GLib.idle_add 回到主线程更新候选
```

示例：

```python
threading.Thread(
    target=self.fetch_candidates_worker,
    args=(self.buffer,),
    daemon=True
).start()
```

回到 IBus 主线程：

```python
GLib.idle_add(self.on_candidates_ready, pinyin, candidates)
```

## 16. 核心代码骨架

### 16.1 llm_client.py

````python
import json
import os
import re
import requests


class LLMClient:
    def __init__(self, config):
        self.config = config
        api = config.get("api", {})
        self.base_url = api.get("base_url", "http://127.0.0.1:8080/v1").rstrip("/")
        self.endpoint = api.get("endpoint", "/chat/completions")
        self.model = api.get("model", "qwen3-0.6b")
        self.timeout = api.get("timeout_ms", 800) / 1000
        self.temperature = api.get("temperature", 0.1)
        self.top_p = api.get("top_p", 0.8)
        self.max_tokens = api.get("max_tokens", 64)
        self.stream = api.get("stream", False)

        api_key = api.get("api_key", "")
        api_key_env = api.get("api_key_env", "OPENAI_API_KEY")
        self.api_key = api_key or os.environ.get(api_key_env, "sk-local")

        prompt = config.get("prompt", {})
        self.system_prompt = prompt.get(
            "system",
            "你是一个中文拼音输入法转换器。只输出 JSON 字符串数组。"
        )
        self.user_template = prompt.get(
            "user_template",
            "拼音：{pinyin}\n请输出中文候选 JSON 数组。"
        )

    def get_candidates(self, pinyin: str, max_candidates: int = 5):
        url = self.base_url + self.endpoint
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_template.format(pinyin=pinyin)}
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": self.stream
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        resp = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return self.parse_candidates(content, max_candidates=max_candidates)

    def parse_candidates(self, content: str, max_candidates: int = 5):
        text = content.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start:end + 1]

        arr = json.loads(text)
        if not isinstance(arr, list):
            return []

        result = []
        seen = set()
        for item in arr:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item:
                continue
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
            if len(result) >= max_candidates:
                break
        return result
````

### 16.2 cache.py

```python
import os
import sqlite3
import time


class CandidateCache:
    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.init_db()

    def init_db(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
          pinyin TEXT NOT NULL,
          candidate TEXT NOT NULL,
          score INTEGER NOT NULL DEFAULT 0,
          source TEXT NOT NULL DEFAULT 'llm',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (pinyin, candidate)
        )
        """)
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_candidates_pinyin_score
        ON candidates (pinyin, score DESC, updated_at DESC)
        """)
        self.conn.commit()

    def get(self, pinyin: str, limit: int = 5):
        cur = self.conn.execute(
            """
            SELECT candidate
            FROM candidates
            WHERE pinyin = ?
            ORDER BY score DESC, updated_at DESC
            LIMIT ?
            """,
            (pinyin, limit)
        )
        return [row[0] for row in cur.fetchall()]

    def put_many(self, pinyin: str, candidates: list[str], source: str = "llm"):
        now = int(time.time())
        for candidate in candidates:
            self.conn.execute(
                """
                INSERT INTO candidates (pinyin, candidate, score, source, created_at, updated_at)
                VALUES (?, ?, 0, ?, ?, ?)
                ON CONFLICT(pinyin, candidate)
                DO UPDATE SET updated_at = excluded.updated_at
                """,
                (pinyin, candidate, source, now, now)
            )
        self.conn.commit()

    def promote(self, pinyin: str, candidate: str):
        now = int(time.time())
        self.conn.execute(
            """
            UPDATE candidates
            SET score = score + 10,
                updated_at = ?
            WHERE pinyin = ? AND candidate = ?
            """,
            (now, pinyin, candidate)
        )
        self.conn.commit()
```

### 16.3 config.py

```python
import json
import os


DEFAULT_CONFIG = {
    "api": {
        "base_url": "http://127.0.0.1:8080/v1",
        "api_key": "",
        "api_key_env": "OPENAI_API_KEY",
        "model": "qwen3-0.6b",
        "endpoint": "/chat/completions",
        "timeout_ms": 800,
        "temperature": 0.1,
        "top_p": 0.8,
        "max_tokens": 64,
        "stream": False
    },
    "input": {
        "max_buffer_length": 120,
        "candidate_page_size": 5
    },
    "candidate": {
        "max_candidates": 5,
        "fallback_to_raw_pinyin": True
    },
    "cache": {
        "enabled": True,
        "path": "~/.config/ibus-ai-pinyin/cache.sqlite3"
    },
    "prompt": {
        "system": "你是一个中文拼音输入法转换器。你的任务是把用户输入的拼音转换成最可能的中文候选。只输出 JSON 字符串数组，不要解释，不要 Markdown，不要代码块。最多输出 5 个候选。",
        "user_template": "拼音：{pinyin}\n请输出中文候选 JSON 数组。"
    }
}


def deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config():
    path = os.path.expanduser("~/.config/ibus-ai-pinyin/config.json")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG

    with open(path, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    return deep_merge(DEFAULT_CONFIG, user_config)
```

### 16.4 engine.py 核心骨架

```python
#!/usr/bin/env python3
import threading

import gi
gi.require_version("IBus", "1.0")
from gi.repository import IBus, GLib

from config import load_config
from llm_client import LLMClient
from cache import CandidateCache


class AIPinyinEngine(IBus.Engine):
    def __init__(self, bus, object_path):
        super().__init__(connection=bus.get_connection(), object_path=object_path)
        self.config = load_config()
        self.llm = LLMClient(self.config)

        cache_cfg = self.config.get("cache", {})
        self.cache_enabled = cache_cfg.get("enabled", True)
        self.cache = CandidateCache(cache_cfg.get("path", "~/.config/ibus-ai-pinyin/cache.sqlite3"))

        self.buffer = ""
        self.candidates = []
        self.selected_index = 0
        self.is_requesting = False

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False

        # 数字键选候选
        if self.candidates and IBus.KEY_1 <= keyval <= IBus.KEY_9:
            index = keyval - IBus.KEY_1
            if index < len(self.candidates):
                self.commit_candidate(index)
                return True

        if keyval == IBus.KEY_space:
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
            self.clear_all()
            return True

        if keyval == IBus.KEY_BackSpace:
            if self.candidates:
                self.candidates = []
                self.hide_lookup_table()
                self.update_preedit()
                return True
            if self.buffer:
                self.buffer = self.buffer[:-1]
                self.update_preedit()
                return True
            return False

        code = IBus.keyval_to_unicode(keyval)
        if code == 0:
            return False

        ch = chr(code)
        if self.accept_char(ch):
            max_len = self.config.get("input", {}).get("max_buffer_length", 120)
            if len(self.buffer) < max_len:
                self.buffer += ch.lower()
                self.candidates = []
                self.hide_lookup_table()
                self.update_preedit()
                return True

        return False

    def accept_char(self, ch: str):
        return ch.isascii() and (ch.isalpha() or ch in ["'", " "])

    def update_preedit(self, suffix: str = ""):
        text = self.buffer + suffix
        ibus_text = IBus.Text.new_from_string(text)
        self.update_preedit_text(ibus_text, len(text), bool(text))

    def request_candidates(self):
        if self.is_requesting:
            return

        pinyin = " ".join(self.buffer.split())
        max_candidates = self.config.get("candidate", {}).get("max_candidates", 5)

        if self.cache_enabled:
            cached = self.cache.get(pinyin, limit=max_candidates)
            if cached:
                self.show_candidates(pinyin, cached)
                return

        self.is_requesting = True
        self.update_preedit(" …")

        threading.Thread(
            target=self.fetch_candidates_worker,
            args=(pinyin, max_candidates),
            daemon=True
        ).start()

    def fetch_candidates_worker(self, pinyin: str, max_candidates: int):
        try:
            candidates = self.llm.get_candidates(pinyin, max_candidates=max_candidates)
        except Exception:
            candidates = []
        GLib.idle_add(self.on_candidates_ready, pinyin, candidates)

    def on_candidates_ready(self, pinyin: str, candidates: list[str]):
        self.is_requesting = False

        # 如果用户已经修改了 buffer，丢弃旧请求结果
        current = " ".join(self.buffer.split())
        if current != pinyin:
            return False

        if candidates:
            if self.cache_enabled:
                self.cache.put_many(pinyin, candidates)
            self.show_candidates(pinyin, candidates)
        else:
            self.update_preedit()
        return False

    def show_candidates(self, pinyin: str, candidates: list[str]):
        self.candidates = candidates
        self.selected_index = 0

        table = IBus.LookupTable.new(
            page_size=self.config.get("input", {}).get("candidate_page_size", 5),
            cursor_pos=0,
            cursor_visible=True,
            round=True
        )

        for cand in candidates:
            table.append_candidate(IBus.Text.new_from_string(cand))

        self.update_lookup_table(table, True)
        self.update_preedit()

    def commit_candidate(self, index: int):
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
        self.update_preedit()
        self.hide_lookup_table()

    def do_focus_out(self):
        self.clear_all()


class EngineFactory(IBus.Factory):
    def __init__(self, bus):
        super().__init__(connection=bus.get_connection())
        self.bus = bus
        self.engine_id = 0

    def do_create_engine(self, engine_name):
        self.engine_id += 1
        object_path = f"/org/freedesktop/IBus/Engine/AIPinyin/{self.engine_id}"
        return AIPinyinEngine(self.bus, object_path)


def main():
    IBus.init()
    bus = IBus.Bus()
    factory = EngineFactory(bus)
    bus.request_name("org.freedesktop.IBus.AIPinyin", 0)
    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    main()
```

## 17. IBus Component 注册文件

路径：

```text
~/.local/share/ibus/component/ai-pinyin.xml
```

内容示例：

```xml
<?xml version="1.0" encoding="utf-8"?>
<component>
  <name>org.freedesktop.IBus.AIPinyin</name>
  <description>AI Pinyin Input Method</description>
  <exec>/home/YOUR_USERNAME/.local/share/ibus-ai-pinyin/engine.py</exec>
  <version>0.1.0</version>
  <author>Volsifly</author>
  <license>MIT</license>
  <homepage>https://example.com</homepage>
  <textdomain>ibus-ai-pinyin</textdomain>

  <engines>
    <engine>
      <name>ai-pinyin</name>
      <language>zh_CN</language>
      <license>MIT</license>
      <author>Volsifly</author>
      <icon>ibus-keyboard</icon>
      <layout>us</layout>
      <longname>AI 拼音输入法</longname>
      <description>使用大模型将拼音转换为中文的 IBus 输入法</description>
      <rank>80</rank>
    </engine>
  </engines>
</component>
```

注意替换：

```text
/home/YOUR_USERNAME
```

可以通过命令查看用户名：

```bash
whoami
```

## 18. 安装流程

### 18.1 创建目录

```bash
mkdir -p ~/.local/share/ibus-ai-pinyin
mkdir -p ~/.local/share/ibus/component
mkdir -p ~/.config/ibus-ai-pinyin
```

### 18.2 放置代码

将以下文件放入：

```text
~/.local/share/ibus-ai-pinyin/engine.py
~/.local/share/ibus-ai-pinyin/llm_client.py
~/.local/share/ibus-ai-pinyin/cache.py
~/.local/share/ibus-ai-pinyin/config.py
```

增加执行权限：

```bash
chmod +x ~/.local/share/ibus-ai-pinyin/engine.py
```

### 18.3 注册 IBus Component

将 `ai-pinyin.xml` 放入：

```text
~/.local/share/ibus/component/ai-pinyin.xml
```

### 18.4 重启 IBus

```bash
ibus restart
```

如果没有出现输入法，注销重新登录。

### 18.5 添加输入法

执行：

```bash
ibus-setup
```

然后添加：

```text
Chinese -> AI 拼音输入法
```

也可以在 GNOME 设置中进入：

```text
Settings -> Keyboard -> Input Sources
```

添加对应输入源。

## 19. 本地模型服务启动示例

### 19.1 llama.cpp server 示例

假设使用本地 GGUF 模型：

```bash
llama-server \
  -m ./models/qwen3-0.6b-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 512 \
  -n 64
```

输入法配置：

```json
{
  "api": {
    "base_url": "http://127.0.0.1:8080/v1",
    "api_key": "sk-local",
    "model": "qwen3-0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 800,
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }
}
```

### 19.2 Ollama 示例

启动模型：

```bash
ollama run qwen3:0.6b
```

输入法配置：

```json
{
  "api": {
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "ollama",
    "model": "qwen3:0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 1200,
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }
}
```

## 20. 测试命令

在接入 IBus 前，先测试模型接口。

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "qwen3-0.6b",
    "messages": [
      {"role": "system", "content": "你是一个中文拼音输入法转换器。只输出 JSON 字符串数组。"},
      {"role": "user", "content": "拼音：nihao\n请输出中文候选 JSON 数组。"}
    ],
    "temperature": 0.1,
    "max_tokens": 64,
    "stream": false
  }'
```

预期返回 content 中包含：

```json
["你好", "你号", "倪浩"]
```

## 21. 日志设计

MVP 阶段建议写入用户目录：

```text
~/.cache/ibus-ai-pinyin/engine.log
```

日志内容包括：

```text
启动时间
配置加载结果，不记录 api_key
模型请求耗时
模型返回候选数量
解析失败原因
HTTP 错误码
IBus 异常
```

注意不要记录完整用户输入内容，至少默认不要记录。输入法输入内容可能包含隐私信息。

## 22. 隐私与安全

这个项目涉及输入法，隐私风险非常高。必须明确设计边界。

### 22.1 默认推荐本地模型

如果使用远程 API，用户输入的拼音内容会被发送到远程服务。虽然只是拼音，但仍可能还原出敏感文本。

因此默认推荐：

```text
本地 llama.cpp server
本地 Ollama
本地 vLLM
局域网私有模型服务
```

### 22.2 不记录敏感内容

日志中不要默认记录用户输入的拼音和模型返回结果。

可以配置：

```json
{
  "debug": {
    "log_user_input": false,
    "log_model_output": false
  }
}
```

### 22.3 API Key 处理

不要把 API Key 写入日志。

推荐优先使用环境变量：

```bash
export OPENAI_API_KEY="sk-xxx"
```

配置中只写：

```json
{
  "api": {
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

## 23. 性能优化建议

### 23.1 只在触发时请求模型

不要逐字符请求。

```text
错误：n、ni、nih、niha、nihao 每次都请求
正确：用户输入完整拼音，按空格后请求
```

### 23.2 控制 max_tokens

输入法候选通常很短，建议：

```text
短词：32
长句：64
最多不要超过 128
```

### 23.3 控制 timeout

本地模型：

```text
500ms - 1200ms
```

远程模型：

```text
1000ms - 2000ms
```

超过超时就回退，不要卡住输入法。

### 23.4 使用缓存

缓存命中时应该在几十毫秒内返回。

### 23.5 模型常驻内存

不要每次请求时启动模型。模型服务必须常驻。

## 24. 错误处理

| 场景              | 处理方式                   |
| --------------- | ---------------------- |
| 模型服务未启动         | 不显示候选，允许回车提交原始拼音       |
| HTTP 超时         | 清除请求状态，恢复 preedit      |
| JSON 解析失败       | 尝试提取数组；失败则回退           |
| 候选为空            | 回退原始拼音                 |
| 用户请求中途修改 buffer | 丢弃旧请求结果                |
| API Key 错误      | 日志记录 HTTP 状态码，不在 UI 阻塞 |
| IBus focus out  | 清空 buffer 和候选          |

## 25. 开发里程碑

### 25.1 第一阶段：最小可运行版本

目标：能输入拼音，按空格调用模型，提交第一个候选。

任务：

```text
完成 IBus 注册
完成 buffer 和 preedit
完成 OpenAI-compatible 请求
完成候选解析
完成空格提交
```

### 25.2 第二阶段：候选选择

目标：能显示多个候选，并用数字键选择。

任务：

```text
实现 IBus LookupTable
实现数字键 1-9 选择
实现候选去重
实现候选失败回退
```

### 25.3 第三阶段：缓存和学习

目标：常用输入越来越快。

任务：

```text
接入 SQLite
缓存模型候选
用户选择后提升 score
缓存优先返回
```

### 25.4 第四阶段：体验优化

目标：更像真实输入法。

任务：

```text
候选翻页
方向键选择
标点处理
中英文切换
状态栏提示
配置热重载
```

### 25.5 第五阶段：模型增强

目标：提升转换准确率。

任务：

```text
加入上下文短记忆
区分短词和长句 prompt
加入技术词白名单
支持企业词汇提示
支持用户自定义固定短语
```

## 26. 推荐默认模型策略

虽然本开发文档允许自定义模型，但默认推荐选择 CPU 可运行的小模型。

推荐优先级：

```text
1. Qwen3-0.6B Q4 / Q5：速度优先，适合 MVP
2. Qwen3-1.7B Q4：质量更好，但 CPU 延迟更高
3. 其他中文小模型：需要测试 JSON 稳定性和拼音转换能力
```

输入法场景不建议使用太大的模型，因为输入延迟比单次生成质量更重要。

## 27. 验收标准

MVP 版本验收：

```text
Ubuntu 下能在 IBus 输入源中看到“AI 拼音输入法”
可以切换到该输入法
输入 nihao 按空格，能出现“你好”等候选
按数字键 1 可以提交第一个候选
输入长拼音句子，能返回中文句子候选
模型服务关闭时，输入法不会卡死
相同拼音第二次输入能命中缓存
日志不泄露 API Key
```

## 28. 已知限制

这个方案直接使用大模型实现拼音转中文，因此有以下限制：

```text
首次输入延迟高于传统输入法
小模型可能输出不稳定 JSON
小模型可能产生错误候选
没有传统词库时，短词准确率不一定高
远程 API 存在隐私和网络延迟问题
CPU 运行模型时性能取决于机器配置
```

因此，长期产品化建议采用混合架构：

```text
短词和高频词：本地词库
长句和补全：大模型
候选排序：用户缓存 + 模型重排
```

但本项目 MVP 按照要求，先实现“直接使用大模型”的版本。

## 29. 后续可扩展方向

### 29.1 加入本地词库兜底

即使主转换逻辑由大模型完成，也可以加入极小词库处理高频短词，提升速度。

### 29.2 加入企业词汇提示

在 prompt 中加入用户自定义词：

```text
常用词：鸿灵、知识库、语义层、向量召回、工作流、智能体
```

这样模型对专业词会更稳定。

### 29.3 加入上下文

输入法可以记录最近一次提交的短上下文，但要注意隐私。

示例：

```text
上文：今天我们讨论了输入法
拼音：zhe ge fang an keyi xian zuo mvp
候选：这个方案可以先做 MVP
```

### 29.4 加入 AI 指令模式

例如：

```text
/zb
```

触发：

```text
生成周报模板
```

或者：

```text
/rw xiufu ibus houxuan chuang wenti
```

输出：

```text
任务：修复 IBus 候选窗口问题
```

这会让输入法从“拼音输入法”变成“AI 办公输入入口”。

## 30. 总结

本开发方案的核心是：

```text
Ubuntu + IBus + Python Engine + OpenAI-compatible API + 可配置模型 + SQLite 缓存
```

第一版不要追求传统输入法的完整能力，而是先验证一个关键问题：

```text
用户输入拼音后，大模型能否在可接受延迟内返回可用中文候选。
```

只要这个链路跑通，后续就可以继续叠加词库、缓存、用户学习、企业术语、AI 指令模式和上下文补全，逐步把它演化成真正可用的 AI 输入法。
