# 每日 3D/4D 学术简报

一个可改成其他研究领域的本地简报工作流：Codex Skill 负责检索、核验、跨日去重和生成 HTML；零第三方依赖的 Python 阅读器自动扫描目录中的日期简报，支持搜索、按月／按周浏览和图片放大。仓库只附带 [一份完成的简报](2026-09-22.html)作为示例，不包含私人历史库存或自动化任务配置。

## 仓库内容

| 路径 | 用途 |
| --- | --- |
| `brief_reader.py` | 本地阅读器，监听 `127.0.0.1` 并扫描当前目录的 `YYYY-MM-DD.html` |
| `start_reader.command` / `start_reader.cmd` | macOS / Windows 启动入口 |
| `assets/brief.css` | 新简报可复用的版式样式 |
| `skill/daily-3d-brief/` | 检索与生成规则、HTML 骨架、去重和校验脚本 |
| `2026-09-22.html` | 唯一的完成版示例；第三方图片已替换为来源占位图 |

需要 Python 3.10 或更新版本；阅读器和校验脚本只使用 Python 标准库。阅读器不需要联网，点击简报中的论文或产品链接才会访问外部网站。

## 打开示例

macOS：在仓库目录运行 `./start_reader.command`，也可在 Finder 中打开该文件。若没有执行权限，先运行 `chmod +x start_reader.command`。

Windows：双击 `start_reader.cmd`，或在命令提示符中运行它。脚本优先使用 Python Launcher 的 `py -3`，没有 Launcher 时尝试 `python`。

也可以在任一系统直接运行 `python brief_reader.py --open`（Windows 常用 `py -3 brief_reader.py --open`）。服务启动后会使用系统默认浏览器，已有服务会被复用。关闭服务进程后，网页将停止提供内容。

## 安装 Skill 与生成自己的日报

将 `skill/daily-3d-brief` 文件夹复制到 Codex 技能目录：

| 系统 | 目标位置 |
| --- | --- |
| macOS | `~/.codex/skills/daily-3d-brief/` |
| Windows | `%USERPROFILE%\.codex\skills\daily-3d-brief\` |

若目标目录已有同名 Skill，请先比较，不要直接覆盖。首次在新项目中运行时，用下列命令创建空白去重状态；不要从别人的历史数据开始：

```bash
python skill/daily-3d-brief/scripts/state.py init data/seen-items.json
```

Windows 可将命令开头的 `python` 换为 `py -3`，路径分隔符换为反斜杠。生成后先校验再同步状态：

```bash
python skill/daily-3d-brief/scripts/validate_brief.py YYYY-MM-DD.html --state data/seen-items.json
python skill/daily-3d-brief/scripts/state.py sync-report data/seen-items.json YYYY-MM-DD.html --date YYYY-MM-DD
```

Skill 会在无合格新增时不生成空白 HTML；阅读器无需登记或重建索引，刷新后就能看到新增文件。若要创建定时任务，可让任务在工作日指定时间调用安装后的 Skill，并明确项目目录、时区与研究范围；仓库不包含原作者的本机计划或账户设置。

### 换成自己的研究领域

1. 修改 `skill/daily-3d-brief/SKILL.md` 的名称、描述和研究主线；修改 `references/content-rules.md` 的纳入／排除标准、来源与检索窗口。
2. 修改 `agents/openai.yaml` 的显示名称和默认提示词；将 `assets/brief-template.html` 中的标题与栏目换成自己的领域。
3. 在自己的项目目录初始化新的 `data/seen-items.json`。稳定键、校验和阅读器可以继续使用，不需要改成某个固定领域的数据结构。
4. 用一份真实日报走完“检索 → 第一方核验 → 写 HTML → 校验 → 同步状态”，再设置重复执行。检查 Windows 与 macOS 的路径、时区和可用字体。

`assets/brief.css` 是版式参考；示例日报还包含少量自身的内联样式。更换领域时可以从 HTML 骨架生成新报告，不必复制示例中的具体论文判断。

## 公开与版权边界

代码、脚本、样式和本项目原创的占位图按 [MIT License](LICENSE) 授权；原创简报文字按 [CC BY 4.0](CONTENT_LICENSE.md) 授权。论文和产品图片没有随仓库上传，示例中的占位图可点击前往官方来源。引用或标注图源不自动赋予再分发权；若你公开自己生成的简报，请先逐张核实素材许可。仓库默认忽略新生成的日期简报、图片目录和去重状态，避免误将私人工作目录整体推送。

示例由 AI 辅助检索和归纳。研究结论、发表状态和日期口径应以各条目链接的第一方来源复核。
