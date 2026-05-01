# AGENTS.md

## 项目形态

`rednote_studio` 是一个用 `uv` 管理的 Python 项目，用于小红书/Rednote 内容生产工作流。当前仓库主要包含：

- `rednote_studio/`：Python 包源码和 CLI 入口。
- `data/`：本地素材、源文件和生成结果。
- `.codex/skills/`：仓库专用的 Codex skill，用于沉淀可重复执行的本地流程。

## 文档语言

- 仓库文档、skill 说明、面向人的 README/用法说明默认使用中文。
- 命令名、参数名、文件路径、代码标识符、第三方专有名词可以保留原文。
- 新增或改写文档时，优先使用简洁中文说明真实流程，不写泛泛的英文模板话。

## 命令约定

- 使用 `uv sync` 安装或同步依赖。
- Python 命令必须走 uv 环境，不使用系统 `python3`：

```bash
uv run python ...
```

- 如果缺少 Python 依赖，安装到 uv 项目环境：

```bash
uv add <package>
```

- 常用项目命令：

```bash
uv run rednote_studio --help
uv run rednote_studio info
uv run image2jpg --help
```

- Python 改动用以下命令检查：

```bash
uv run ruff check <path>
```

## 数据和媒体

- `data/` 是本地工作数据。除非用户明确要求，不删除、不覆盖、不移动源素材。
- 优先把结果复制或转换到稳定目标目录，不直接改动 raw 原图。
- `.DS_Store`、缓存文件、虚拟环境、临时预览和生成输出默认忽略；只有用户要求时才检查。

## Food Notes 流程

- 整理 `data/food_notes/raw` 时使用 `.codex/skills/organize-food-notes/`。
- 稳定输出形态是：

```text
data/food_notes/<菜名>/1.jpg
data/food_notes/<菜名>/2.jpg
data/food_notes/<菜名>/3.jpg
data/food_notes/<菜名>/content.md
```

- 图片整理流程应保留 `raw/` 原图，先生成预览，再确认映射，最后才写入连续编号 JPG。
- 抓取小红书帖子正文到现有 `data/food_notes/<菜名>/content.md` 时使用 `.codex/skills/fetch-xiaohongshu-posts/`。

## 编辑规则

- 改动范围保持贴近用户当前请求。
- 保留用户已有本地数据和无关工作区改动。
- 优先使用仓库已有脚本和 skill，不另起一套平行工具。
- 检查图片、PDF、视频等媒体时，优先做元数据检查，再进入更重的渲染或截图流程。
