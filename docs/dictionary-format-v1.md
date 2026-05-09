# 自定义领域词库格式 v1

词库文件使用 JSON，推荐文件名后缀为 `.dict.json`。第一版不自动生成拼音，词条需要显式提供 `pinyin` 或 `short`，否则只能被导入，不能通过拼音命中。

## 顶层结构

```json
{
  "version": "1.0",
  "name": "鸿灵项目词库",
  "description": "项目、系统、模块、技术词汇",
  "source": "manual",
  "locale": "zh-CN",
  "entries": []
}
```

必填字段：

- `version`：当前必须为 `1.0`
- `name`：词库名称
- `entries`：词条数组

## 词条结构

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

词条只有 `term` 必填。`weight` 范围是 `0-100`，越高越靠前。`enabled=false` 的词条会入库但不会作为候选返回。

支持的 `type`：

```text
product project system module feature organization person tech abbreviation business mixed other
```

## 匹配形式

导入时会为每个 `pinyin` 生成紧凑拼音：

```text
hong ling mcp gong ju -> honglingmcpgongju
```

`short` 会转为小写并只保留字母数字：

```text
HL-MCP -> hlmcp
```

候选查询顺序：

1. 完整拼音精确匹配
2. 紧凑拼音精确匹配
3. 短码精确匹配
4. 完整拼音前缀匹配
5. 紧凑拼音前缀匹配
6. 短码前缀匹配
