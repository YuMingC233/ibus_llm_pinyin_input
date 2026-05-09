# ibus-ai-pinyin Domain Dictionary Skill

这个 Skill 用来把项目文档、术语表、Wiki 内容、需求文档等材料整理成 `ibus_llm_pinyin_input` 可导入的 `.dict.json` 领域词库。

## 文件内容

```text
SKILL.md
resources/dictionary-format-v1.md
resources/dictionary.schema.json
examples/hongling.dict.json
scripts/validate_dict.py
```

## 典型用途

把一段项目资料交给 ChatGPT，然后要求：

```text
请使用 ibus-ai-pinyin-domain-dictionary skill，
从下面资料中提取适合输入法使用的专有名词，
生成 .dict.json 词库文件。
```

## 校验示例

```bash
python3 scripts/validate_dict.py examples/hongling.dict.json
```

生成后建议先校验再导入：

```bash
python3 ibus-ai-pinyin-dict-skill/scripts/validate_dict.py dev/mydict.json
python3 scripts/import-dictionary.py dev/mydict.json --dry-run
python3 scripts/import-dictionary.py dev/mydict.json
```

## 设计原则

- 精准优先，不要污染输入法词库。
- 只提取专有名词、系统名、项目名、模块名、技术缩写等。
- 输出合法 JSON。
- 尽量提供 pinyin、short、type、weight、tags、comment。
- `type` 只能使用格式规范里的枚举值，不要生成 `concept`、`tool`、`algorithm` 等非标准类型。
- 对会影响长拼音短语纠错的核心词，必须提供完整 `pinyin`，不能只提供 `short`。
- 如果用户常用同义输入但期望规范候选，给规范词补充同义输入的拼音，例如 `搜索` 可写 `["sou suo", "jian suo"]`。
