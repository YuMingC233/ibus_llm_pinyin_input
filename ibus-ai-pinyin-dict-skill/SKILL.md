---
name: ibus-ai-pinyin-domain-dictionary
description: Generate and validate .dict.json domain dictionary files for ibus_llm_pinyin_input. Use this skill when the user wants to extract project-specific terms, proper nouns, product names, system names, module names, technical abbreviations, or business vocabulary from documents and convert them into an importable input-method dictionary.
---

# ibus-ai-pinyin Domain Dictionary Skill

## Purpose

This skill helps generate `.dict.json` domain dictionary files for `ibus_llm_pinyin_input`.

Use it when the user wants to:

- Convert project documents into an input-method dictionary.
- Extract proper nouns, system names, product names, project names, module names, organization names, technical terms, abbreviations, or mixed Chinese-English terms.
- Generate a dictionary that can be imported into the input method.
- Validate, clean, merge, or refine an existing `.dict.json` file.
- Convert a manually prepared term list into the standard dictionary format.

The output should follow the format in `resources/dictionary-format-v1.md`.

## Core Output Requirement

When generating a dictionary, output valid JSON only unless the user explicitly asks for explanation.

The default output shape is:

```json
{
  "version": "1.0",
  "name": "词库名称",
  "description": "词库说明",
  "source": "llm_extract",
  "locale": "zh-CN",
  "entries": []
}
```

Each entry should follow this shape:

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

Only `term` is strictly required in each entry, but when possible, generate all recommended fields.

## Extraction Rules

Extract terms that are useful for a Chinese input method.

Prefer extracting:

- Project names, such as `大渡口路灯项目`.
- Product names, such as `鸿灵`.
- System names, such as `鸿燕系统`.
- Module names, such as `智能生成大屏`.
- Tool names, such as `鸿灵MCP工具`.
- Organization or company names.
- Internal business concepts.
- Technical terms, such as `向量召回`, `RAG`, `OpenAI-compatible`.
- English or mixed Chinese-English names, such as `Dify Workflow`, `BrowserOS`, `Claude Code`.
- Stable abbreviations, such as `MCP`, `API`, `LLM`.

Avoid extracting:

- Ordinary Chinese words.
- Full sentences.
- Verbs or adjectives that are not domain terms.
- Generic concepts and common nouns that are not project-specific, such as `功能`, `系统`, `用户`, `数据`, `排序`, `搜索`, unless the source clearly uses them as domain vocabulary or the user explicitly asks to include them.
- Temporary wording that looks like a one-off phrase.
- Sensitive personal data unless the user explicitly asks to include it.

When the target input method will be used for long pinyin phrases, include short but important domain nouns that help disambiguate the phrase. For example, if the source uses `鸿灵知识库搜索功能`, include `鸿灵`, `知识库`, and `搜索` so the input method can pass these terms as LLM context.

## Pinyin Rules

Use lowercase pinyin with spaces between Chinese syllables.

Examples:

- `鸿灵` → `hong ling`
- `智能生成大屏` → `zhi neng sheng cheng da ping`
- `大渡口路灯项目` → `da du kou lu deng xiang mu`
- `鸿灵MCP工具` → `hong ling mcp gong ju`

For English or mixed terms:

- Preserve English terms in lowercase.
- Keep stable abbreviations as lowercase tokens in pinyin.
- `Dify Workflow` → `dify workflow`
- `OpenAI-compatible` → `openai compatible`
- `鸿灵MCP工具` → `hong ling mcp gong ju`

If unsure about a rare character or proper pronunciation, either omit `pinyin` or add the most likely pinyin and mention uncertainty outside JSON only if explanation is allowed.

Add practical alternate pinyin forms when users are likely to type a synonym, old name, or business wording but the expected candidate should use the canonical term.

Examples:

- `搜索` may use `["sou suo", "jian suo"]` when users type `jiansuo` but the product wording should be `搜索`.
- `鸿灵` should include `hong ling`; do not rely only on the short code `hl`, because long pinyin context matching uses full pinyin forms.
- For a canonical term with common pronunciation ambiguity, add the common input forms only if they are actually useful in this domain.

Do not put short-code forms such as `hl` or `ss` in `pinyin`; put them in `short`.

## Short Code Rules

Generate `short` from pinyin initials.

Examples:

- `hong ling` → `hl`
- `hong ling mcp gong ju` → `hlmcpgj`
- `zhi neng sheng cheng da ping` → `znscdp`

For mixed terms, add practical aliases:

- `鸿灵MCP工具` may have `["hlmcp", "hlmcpgj"]`.
- `Dify Workflow` may have `["dfwf"]`.
- `OpenAI-compatible` may have `["oai"]` only if the document or user indicates that abbreviation is meaningful.

## Type Values

Use one of these recommended values:

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

If uncertain, use `other`.

Important: do not output unsupported values such as `concept`, `tool`, `algorithm`, `framework`, `database`, or `protocol`. Map them to the supported set:

- tool/framework/database/protocol/model/library/language -> `tech`
- algorithm/concept/method/process -> `tech` if technical and domain-useful, otherwise `other`
- product/platform/application -> `product`
- capability/user-facing behavior -> `feature`
- business phrase or internal vocabulary -> `business`

## Weight Rules

Use a value from 0 to 100.

Suggested defaults:

- 95-100: core product, project, or frequently used internal term.
- 85-94: important module, system, or feature.
- 70-84: technical term, common abbreviation, or repeated business term.
- 50-69: potentially useful but less central term.
- Below 50: avoid unless the user explicitly wants broad coverage.

Do not overfill the dictionary. It is better to output 30 precise entries than 300 noisy entries.

## Alias Rules

Use `aliases` for:

- Variants with spaces, such as `鸿灵 MCP`.
- Common written variants, such as `鸿灵MCP`.
- English aliases, if explicitly present in the source.
- Official abbreviations.

Do not invent brand-new aliases unless they are obvious and useful for input.

## Tags and Comments

Use tags for project, product, or domain grouping.

Examples:

```json
"tags": ["鸿灵", "Dify", "知识库"]
```

Use `comment` to explain why the term is included or where it appears.

Keep comments short.

## Quality Checklist

Before finalizing:

1. JSON must be valid.
2. `version` must be `"1.0"`.
3. `entries` must be an array.
4. Every entry must have non-empty `term`.
5. Avoid duplicate `term`.
6. `weight` must be an integer between 0 and 100.
7. `enabled` should be boolean.
8. Pinyin should be lowercase and space-separated.
9. Do not include Markdown code fences when the user asks for a direct dictionary file.
10. Prefer precision over recall.
11. Run or mentally apply `scripts/validate_dict.py`; the generated file must pass validation.
12. For long phrase disambiguation, ensure key canonical terms have full pinyin forms, not only `short`.
13. If a term should be selected when the user types a synonym, add that synonym's pinyin to `pinyin`.

## Common User Requests

### Generate a dictionary from documents

Read the supplied content, extract useful domain terms, and output a complete `.dict.json`.

### Clean an existing dictionary

Validate structure, remove duplicates, normalize pinyin and short codes, and keep the strongest entry when duplicates exist.

### Convert a term list

If the user provides plain terms, convert them into dictionary entries. Generate pinyin and short codes when possible.

### Merge dictionaries

Merge entries by `term`. Keep the higher `weight`, merge `aliases`, merge `tags`, and preserve useful comments.

## Suggested Response Style

If the user asks for a file, create or output the `.dict.json` content directly.

If the user asks for a review, summarize:

- Number of entries.
- Suspected noisy terms.
- Missing pinyin.
- Duplicate or conflicting terms.
- Suggested improvements.
