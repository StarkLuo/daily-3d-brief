---
name: daily-3d-brief
description: 检索事件相机、前馈式 3D/4D 重建、Gaussian Splatting 及其与世界模型和具身智能交叉方向的最新学术与产业动态，完成跨日去重、来源核验、原图选取，并生成固定版式的中文 HTML 日报。适用于每日或定期研究情报简报；不用于一般论文综述或单篇论文解读。
---

# 每日 3D/4D 研究简报

在当前项目目录中生成可直接浏览、可打印的中文 HTML 简报，并维护跨日去重状态。

## 每次运行必须读取

- 读取 [内容与检索规则](references/content-rules.md)，据此检索、筛选和核验。
- 读取 [状态格式](references/state-schema.md)，据此初始化、读取和更新 `data/seen-items.json`。
- 将 [HTML 模板](assets/brief-template.html) 作为版式基准。若项目内已有用户确认过的更新版 HTML，则优先沿用其视觉样式，但仍须满足本 Skill 的结构与校验要求。

## 工作流

1. 确认当前日期、时区、项目目录和上一期成功简报。读取 `data/seen-items.json`；若不存在，运行 `scripts/state.py init` 创建。
2. 先检索过去 24 小时。只有在没有合格新增且状态记录表明相应更早窗口尚未覆盖时，才依次扩展至 48 小时、72 小时，最多一周。不得因扩窗重复报道已收录条目。
3. 为候选项确定稳定键，并在写作前与状态文件比对。学术项优先使用 `arxiv:<id>` 或 `doi:<doi>`；产业项使用规范化官方 URL。标题相似但稳定键不同的条目需要人工判断是否为同一事项。
4. 逐项核验标题、公开日期、会议/期刊状态、方法信息和结果。会议接收状态优先使用会议或期刊官方来源；只有 arXiv comments 时明确标注核验层级。
5. 选取 2–4 张真正提高理解效率的图片。论文优先使用论文 PDF 或项目页中的框架图、关键效果图；产业项使用官方产品或新闻图片。获得可用于当前输出的素材后，保存到 `assets/YYYY-MM-DD/`，优先转为 WebP。不得用 AI 生成图替代论文架构，不得使用来源不明的聚合站缩略图。公开分发前另须确认再分发许可；无法确认时使用带官方来源链接的占位图，不提交第三方原图。
6. 完成扩窗和去重后，先判断是否存在至少一项合格新增。若学术与产业两侧均为零新增，则停止生成：不创建 `YYYY-MM-DD.html`，不创建当日资源目录，也不写入一次“成功简报”状态；仅在任务运行结果中报告“无新增”和实际覆盖窗口。若至少有一项合格新增，再生成 `YYYY-MM-DD.html`：内容较少时使用 2 页，信息丰富时使用 3 页。第一页为结论、方向统计和 1–2 篇必读；第二页为研究地图或其余核心条目；第三页仅在需要时用于产业信号、事件相机状态、阅读顺序和研究空白。
7. 每个被报道的学术或产业事项都必须在最外层元素写入唯一的 `data-item-key` 和 `data-item-title`。图片必须是相对路径，并在页面中标明来源。链接直接指向论文、项目、会议或公司的第一方页面。
8. 使用 `scripts/validate_brief.py` 检查 HTML。修复全部错误后，再运行 `scripts/state.py sync-report` 更新去重状态。状态更新失败时必须报错，不得假装完成。
9. 最终只报告新增数量、输出路径、扩窗范围和验证结果；不在聊天中重复整篇简报。

## 命令

以下路径均相对于本 Skill 目录；执行时解析为绝对路径：

```bash
python3 scripts/state.py init <project>/data/seen-items.json
python3 scripts/state.py import-history <project>/data/seen-items.json <project>
python3 scripts/state.py has <project>/data/seen-items.json arxiv:2609.21498
python3 scripts/validate_brief.py <project>/YYYY-MM-DD.html --state <project>/data/seen-items.json
python3 scripts/state.py sync-report <project>/data/seen-items.json <project>/YYYY-MM-DD.html --date YYYY-MM-DD
```

先校验、后同步。不要交换最后两步。

## 迁移到其他研究领域

复制本 Skill 后，至少修改 frontmatter 的 `name`、`description`，以及 `references/content-rules.md` 中的研究范围和筛选边界；再修改 `agents/openai.yaml` 的展示名称与默认提示词、`assets/brief-template.html` 的栏目名称。新领域使用独立项目目录和新的空白去重状态，不沿用示例论文的 `data/seen-items.json`。仓库根目录的 `README.md` 给出 macOS、Windows 的安装与启动步骤。
