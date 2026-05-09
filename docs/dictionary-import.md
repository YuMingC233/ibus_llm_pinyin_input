# 自定义领域词库导入

使用导入脚本把 `.dict.json` 写入输入法 SQLite 数据库：

```bash
python3 scripts/import-dictionary.py path/to/company.dict.json
```

默认数据库：

```text
~/.config/ibus-ai-pinyin/cache.sqlite3
```

指定数据库：

```bash
python3 scripts/import-dictionary.py path/to/company.dict.json --db /tmp/ibus-ai-pinyin.sqlite3
```

只校验不写入：

```bash
python3 scripts/import-dictionary.py path/to/company.dict.json --dry-run
```

覆盖已有词条的拼音、别名和标签映射：

```bash
python3 scripts/import-dictionary.py path/to/company.dict.json --replace
```

默认行为是 `--merge`：同名词条会合并映射，权重取较高值。

导入后，输入法会从领域词库、缓存、本地兜底和 LLM 候选中融合结果。领域词库候选排在最前，但不会阻断后续候选来源。
