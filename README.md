# IBus LLM Pinyin Input

一个基于 IBus 的大模型拼音输入法。用户输入拼音后按空格，输入法通过 OpenAI-compatible Chat Completions 接口请求中文候选，再由用户选择候选提交到当前输入框。

当前实现偏 MVP：IBus 负责按键捕获、候选窗、提交文本和缓存；大模型负责把拼音转换成中文候选。详细设计见 [design.md](design.md)。

## 特性

- 支持 OpenAI-compatible Chat Completions API。
- 支持本地 llama.cpp、Ollama、DeepSeek、OpenRouter 等兼容服务。
- 拼音输入期间不把原始拼音写入当前输入框，只在 IBus 弹出区域显示输入内容和候选。
- 用户选择候选后才提交中文到输入框。
- 焦点切换时自动清空原始拼音、候选和辅助文本。
- 支持快捷键切换中英文输入模式，默认 `Ctrl+Space`。
- IBus 状态栏/面板会显示当前输入模式：`中` 或 `英`。
- 支持 SQLite 候选缓存，常用候选会被提升排序。
- 支持导入 `.dict.json` 自定义领域词库，领域词会作为 LLM 上下文参与长拼音纠错。
- 拼音输入过程中输入 ASCII 标点或符号时，不会退出输入，会把符号连同拼音一起发送给 LLM。
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
  },
  "input": {
    "max_buffer_length": 120,
    "candidate_page_size": 5,
    "default_mode": "zh",
    "toggle_key": {
      "enabled": true,
      "key": "space",
      "modifiers": ["Control"]
    }
  },
  "dictionary": {
    "enabled": true,
    "path": "~/.config/ibus-ai-pinyin/cache.sqlite3",
    "max_candidates": 5
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

### 中英文切换快捷键

默认快捷键是 `Ctrl+Space`：

```json
{
  "input": {
    "default_mode": "zh",
    "toggle_key": {
      "enabled": true,
      "key": "space",
      "modifiers": ["Control"]
    }
  }
}
```

`default_mode` 可设置为：

```text
zh
en
```

英文模式下，输入法不会拦截普通按键，所有输入都会直接交给当前应用。再次按切换快捷键会回到中文模式。

IBus 状态栏/面板会显示当前模式：

```text
中
英
```

状态显示通过 IBus component 的 `icon_prop_key=InputMode` 和引擎内同名 property 实现。

例如改成 `Alt+Space`：

```json
{
  "input": {
    "toggle_key": {
      "enabled": true,
      "key": "space",
      "modifiers": ["Alt"]
    }
  }
}
```

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

如果已经开始输入拼音，继续输入 ASCII 标点或符号不会退出输入法缓冲区。例如输入 `nihao,` 后按空格，发送给 LLM 的内容就是 `nihao,`。如果当前没有拼音缓冲区，符号仍然直接交给当前应用。

## 自定义领域词库

输入法支持导入标准 `.dict.json` 词库。导入后，词库只作为 LLM 上下文使用，不会直接加入候选列表：

- 普通短输入不会被词库前缀候选污染，例如 `zhi` 不会因为词库里有 `知识库` 而直接展示 `知识库`。
- 长拼音短语输入时，命中的领域词会作为上下文传给 LLM，并对 LLM 候选重排。例如输入 `honglingzhishikujiansuogongneng` 时，词库可提供 `鸿灵`、`知识库`、`搜索`，帮助模型输出 `鸿灵知识库搜索功能`。

### 词库格式

最小示例：

```json
{
  "version": "1.0",
  "name": "我的项目词库",
  "entries": [
    {
      "term": "鸿灵",
      "pinyin": ["hong ling"],
      "short": ["hl"],
      "type": "product",
      "weight": 100,
      "enabled": true
    },
    {
      "term": "搜索",
      "pinyin": ["sou suo", "jian suo"],
      "short": ["ss"],
      "type": "tech",
      "weight": 85,
      "enabled": true
    }
  ]
}
```

`type` 只能使用以下值：

```text
product project system module feature organization person tech abbreviation business mixed other
```

不要使用 `concept`、`tool`、`algorithm`、`framework` 等非标准类型。完整格式见 [docs/dictionary-format-v1.md](docs/dictionary-format-v1.md)。

### 使用 skill 生成词库

项目内提供了 `ibus-ai-pinyin-dict-skill/`，可用于从项目文档、Wiki、术语表中生成 `.dict.json`。

典型提示：

```text
请使用 ibus-ai-pinyin-domain-dictionary skill，
从下面资料中提取适合输入法使用的专有名词，
生成 dev/mydict.json 词库文件。
```

生成词库时注意：

- 精准优先，不要把普通词大量加入词库。
- 核心领域词必须提供完整 `pinyin`，不能只给 `short`。
- 如果用户常输入同义词，但期望输出规范词，把同义输入的拼音也加到规范词的 `pinyin` 中。例如期望 `jiansuo` 输出 `搜索`，则写 `"pinyin": ["sou suo", "jian suo"]`。
- 生成后先校验，再导入。

### 校验和导入

校验 skill 生成的词库：

```bash
python3 ibus-ai-pinyin-dict-skill/scripts/validate_dict.py dev/mydict.json
```

只检查导入效果，不写数据库：

```bash
python3 scripts/import-dictionary.py dev/mydict.json --dry-run
```

导入到默认数据库：

```bash
python3 scripts/import-dictionary.py dev/mydict.json
```

默认数据库路径：

```text
~/.config/ibus-ai-pinyin/cache.sqlite3
```

导入后重启 IBus：

```bash
ibus restart
ibus engine ai-pinyin
```

### 缓存和 LLM 的关系

候选来源会融合：

```text
LLM 新结果
SQLite 历史缓存
本地兜底候选
```

词库本身不直接输出候选。当长输入命中领域词上下文时，缓存不会直接截断请求，输入法仍会调用 LLM 补充结果；缓存只作为后备候选参与融合，避免旧缓存污染覆盖新的词库纠错结果。

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
