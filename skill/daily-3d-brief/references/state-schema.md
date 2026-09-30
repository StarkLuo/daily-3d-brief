# 去重状态格式

项目状态文件固定为 `data/seen-items.json`，UTF-8 编码。状态只在当日 HTML 校验成功后更新。

首次接入已有简报目录时，可在初始化后运行一次 `state.py import-history`。它会从日期命名的 Markdown 中导入 arXiv 条目和产业章节的第一方链接，并从 HTML 的 `data-item-*` 属性导入结构化条目。

```json
{
  "version": 1,
  "updated_at": "2026-09-22T08:06:58+08:00",
  "items": {
    "arxiv:2609.21498": {
      "title": "VoxelTTO",
      "type": "academic",
      "first_seen": "2026-09-22",
      "last_seen": "2026-09-22",
      "url": "https://arxiv.org/abs/2609.21498"
    }
  },
  "runs": [
    {
      "date": "2026-09-22",
      "output": "2026-09-22.html",
      "item_keys": ["arxiv:2609.21498"]
    }
  ]
}
```

## 稳定键

- arXiv：`arxiv:<不含版本号的 ID>`。
- DOI：`doi:<小写 DOI>`。
- 官方论文但无 DOI/arXiv：`paper:<规范化官方 URL>`。
- 产业、产品、活动：`industry:<规范化官方 URL>`。
- 同一事项的 URL 发生跳转时保留原键，并更新 `url` 字段，不创建重复项。

HTML 中每个事项的最外层元素必须包含：

```html
<article
  data-item-key="arxiv:2609.21498"
  data-item-title="VoxelTTO"
  data-item-type="academic"
  data-item-url="https://arxiv.org/abs/2609.21498">
</article>
```

`data-item-type` 只能是 `academic`、`industry` 或 `event`。`state.py sync-report` 从这些属性更新状态；缺少稳定键或标题时直接失败。

## 一致性规则

- `version` 不支持时停止，不得静默覆盖。
- 同一个键对应不同标题时停止并人工判断。
- 同一报告中键必须唯一。
- `runs` 中同一日期只保留一次成功运行记录；重新生成当天报告时，以最新成功报告替换该运行记录，但不改变条目的 `first_seen`。
- 不因“候选项被检索到但未写入简报”而加入状态。
