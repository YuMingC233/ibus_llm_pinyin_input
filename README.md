# Ubuntu AI Pinyin Input

这是一个基于 IBus 的大模型拼音输入法 MVP。用户输入拼音后按空格，输入法通过 OpenAI-compatible Chat Completions 接口请求中文候选，并用 IBus 候选窗提交文本。

详细设计见 [design.md](design.md)。

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

## 配置

首次启动会生成：

```text
~/.config/ibus-ai-pinyin/config.json
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
    "timeout_ms": 800
  }
}
```

本地 llama.cpp server 示例：

```bash
llama-server \
  -m ./models/qwen3-0.6b-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 512 \
  -n 64
```

Ollama OpenAI-compatible 示例：

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

模型失败或超时时，不会阻塞输入；可以按回车提交原始拼音。

## 日志和缓存

日志：

```text
~/.cache/ibus-ai-pinyin/engine.log
```

缓存：

```text
~/.config/ibus-ai-pinyin/cache.sqlite3
```

默认日志不会记录完整用户输入和模型输出。

## 开发验证

```bash
python3 -m py_compile engine.py ibus_ai_pinyin/*.py tests/*.py
python3 tests/test_core.py
```

## License

MIT
