# IBus LLM Pinyin Input

一个基于 IBus 的大模型拼音输入法。用户输入拼音后按空格，输入法通过 OpenAI-compatible Chat Completions 接口请求中文候选，再由用户选择候选提交到当前输入框。

当前实现偏 MVP：IBus 负责按键捕获、候选窗、提交文本和缓存；大模型负责把拼音转换成中文候选。详细设计见 [design.md](design.md)。

## 特性

- 支持 OpenAI-compatible Chat Completions API。
- 支持本地 llama.cpp、Ollama、DeepSeek、OpenRouter 等兼容服务。
- 拼音输入期间不把原始拼音写入当前输入框，只在 IBus 弹出区域显示输入内容和候选。
- 用户选择候选后才提交中文到输入框。
- 焦点切换时自动清空原始拼音、候选和辅助文本。
- 支持 SQLite 候选缓存，常用候选会被提升排序。
- 模型失败或超时时不会阻塞输入，可按回车提交原始拼音。
- 支持本地常用词兜底候选。
- Ctrl、Alt、Super、Meta 快捷键以及功能键、方向键等会直通应用，避免被输入法屏蔽。

## 依赖

```bash
sudo apt update
sudo apt install -y ibus python3 python3-gi gir1.2-ibus-1.0 python3-requests sqlite3
```

如果当前系统没有启用 IBus：

```bash
im-config -n ibus
```

然后注销并重新登录。

## 安装

```bash
chmod +x scripts/install-user.sh
./scripts/install-user.sh
ibus restart
```

之后打开 `ibus-setup`，添加：

```text
Chinese -> AI 拼音输入法
```

也可以在 GNOME 设置中通过 `Settings -> Keyboard -> Input Sources` 添加。

如果命令行切换可用，也可以执行：

```bash
ibus engine ai-pinyin
```

## 配置

首次启动会生成：

```text
~/.config/ibus-ai-pinyin/config.json
```

修改配置后需要重启 IBus 才会生效：

```bash
ibus restart
ibus engine ai-pinyin
```

默认配置使用本地 OpenAI-compatible 服务：

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
    "stream": false,
    "proxy_enabled": false,
    "thinking": {
      "enabled": false,
      "type": "disabled"
    },
    "extra_body": {}
  }
}
```

### DeepSeek 示例

```json
{
  "api": {
    "base_url": "https://api.deepseek.com",
    "api_key": "sk-...",
    "model": "deepseek-v4-flash",
    "endpoint": "/chat/completions",
    "timeout_ms": 15000,
    "max_tokens": 256,
    "stream": false,
    "proxy_enabled": false,
    "thinking": {
      "enabled": false,
      "type": "disabled"
    },
    "extra_body": {}
  }
}
```

`thinking.enabled=false` 会在请求体中加入：

```json
{
  "thinking": {
    "type": "disabled"
  }
}
```

这适用于支持关闭思考的 OpenAI-compatible 服务。其他厂商需要额外请求字段时，可以放到 `api.extra_body`。

### Ollama 示例

```json
{
  "api": {
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "ollama",
    "model": "qwen3:0.6b",
    "endpoint": "/chat/completions",
    "timeout_ms": 1200
  }
}
```

### llama.cpp server 示例

```bash
llama-server \
  -m ./models/qwen3-0.6b-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 512 \
  -n 64
```

## 使用

```text
输入 nihao
按空格请求候选
按 1-9 选择候选
按空格提交当前第一个候选
按回车提交当前候选或原始拼音
按 Esc 清空
按 Backspace 删除
```

拼音输入过程中，原始拼音不会写入当前输入框。IBus 候选弹窗会显示当前拼音和候选结果，只有选择候选或回车提交时才会写入输入框。

## 日志和缓存

日志：

```text
~/.cache/ibus-ai-pinyin/engine.log
```

缓存：

```text
~/.config/ibus-ai-pinyin/cache.sqlite3
```

日志会记录模型请求耗时、HTTP 状态、原始输出和解析后的候选，便于排查 API 配置问题。日志可能包含模型返回内容，调试完成后可以按需清理：

```bash
truncate -s 0 ~/.cache/ibus-ai-pinyin/engine.log
```

## 开发验证

```bash
python3 -m py_compile engine.py ibus_ai_pinyin/*.py tests/*.py
python3 tests/test_core.py
```

## License

MIT. See [LICENSE](LICENSE).
