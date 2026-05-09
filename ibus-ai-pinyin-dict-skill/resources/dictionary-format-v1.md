# ibus-ai-pinyin Dictionary Format v1

## File extension

Recommended extension:

```text
.dict.json
```

Examples:

```text
hongling.dict.json
company_terms.dict.json
project_terms.dict.json
```

## Encoding

Use UTF-8.

## Top-level structure

```json
{
  "version": "1.0",
  "name": "我的词库",
  "description": "项目专有名词",
  "source": "manual",
  "locale": "zh-CN",
  "entries": []
}
```

## Top-level fields

| Field | Required | Description |
|---|---:|---|
| `version` | yes | Format version. Current version is `"1.0"`. |
| `name` | yes | Dictionary name. |
| `description` | no | Dictionary description. |
| `source` | no | Source, such as `manual`, `llm_extract`, `wiki`, `company_export`. |
| `locale` | no | Default: `zh-CN`. |
| `entries` | yes | Dictionary entries. |

## Entry structure

```json
{
  "term": "鸿灵MCP工具",
  "pinyin": ["hong ling mcp gong ju"],
  "short": ["hlmcp", "hlmcpgj"],
  "aliases": ["鸿灵 MCP", "鸿灵MCP"],
  "type": "module",
  "weight": 95,
  "tags": ["鸿灵", "Dify", "MCP"],
  "comment": "Dify 中使用的鸿灵 MCP 工具",
  "enabled": true
}
```

## Entry fields

| Field | Required | Description |
|---|---:|---|
| `term` | yes | Candidate text shown by the input method. |
| `pinyin` | no | Full pinyin forms. Use lowercase and spaces between syllables. |
| `short` | no | Short codes or initial codes. |
| `aliases` | no | Alias terms that may also be shown as candidates. |
| `type` | no | Term type. |
| `weight` | no | Priority from 0 to 100. Default can be 50. |
| `tags` | no | Tags for grouping. |
| `comment` | no | Short explanation. |
| `enabled` | no | Whether the term is active. Default can be true. |

## Recommended type values

- `product`
- `project`
- `system`
- `module`
- `feature`
- `organization`
- `person`
- `tech`
- `abbreviation`
- `business`
- `mixed`
- `other`

Unsupported values such as `concept`, `tool`, `algorithm`, `framework`, `database`, and `protocol` should not be emitted. Use `tech`, `feature`, `business`, `product`, or `other` instead.

## Pinyin rules

Use lowercase pinyin with spaces:

```text
鸿灵 -> hong ling
智能生成大屏 -> zhi neng sheng cheng da ping
大渡口路灯项目 -> da du kou lu deng xiang mu
```

Mixed Chinese-English terms:

```text
鸿灵MCP工具 -> hong ling mcp gong ju
Dify Workflow -> dify workflow
OpenAI-compatible -> openai compatible
```

Add alternate full-pinyin forms when a user is likely to type a synonym but the candidate should use the canonical term:

```json
{
  "term": "搜索",
  "pinyin": ["sou suo", "jian suo"],
  "short": ["ss"],
  "type": "tech"
}
```

Long pinyin context matching uses full `pinyin` forms, not `short`, so important domain words should have complete pinyin entries.

## Short code rules

Use pinyin initials:

```text
hong ling -> hl
hong ling mcp gong ju -> hlmcpgj
zhi neng sheng cheng da ping -> znscdp
```

You may add common practical abbreviations:

```json
"short": ["hlmcp", "hlmcpgj"]
```

## Minimal valid file

```json
{
  "version": "1.0",
  "name": "我的词库",
  "entries": [
    {
      "term": "鸿灵"
    },
    {
      "term": "智能生成大屏"
    }
  ]
}
```

## Standard file

```json
{
  "version": "1.0",
  "name": "鸿灵项目词库",
  "description": "鸿灵平台、Dify、AI 问数、知识库相关专有名词",
  "source": "manual",
  "locale": "zh-CN",
  "entries": [
    {
      "term": "鸿灵MCP工具",
      "pinyin": ["hong ling mcp gong ju"],
      "short": ["hlmcp", "hlmcpgj"],
      "aliases": ["鸿灵 MCP", "鸿灵MCP"],
      "type": "module",
      "weight": 95,
      "tags": ["Dify", "MCP"],
      "comment": "鸿灵平台中的 Dify 工具",
      "enabled": true
    }
  ]
}
```
