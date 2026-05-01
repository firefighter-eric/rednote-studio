---
name: organize-food-notes
description: 整理“食物小志/食物笔记”类食谱图片：按每组第一张图上醒目的中文菜名建立目录，并输出 1.jpg、2.jpg、3.jpg 这类连续编号文件。适用于 Codex 需要清理 data/food_notes/raw、生成缩略图预览、确认分组映射、保留 raw 原图、把图片复制转换到 data/food_notes/items/<菜名>/，或在有小红书发帖时间时输出到 data/food_notes/items/<YYYY-MM-DD>_<菜名>/ 时。
---

# 整理食物小志图片

## 目标

把 `data/food_notes/raw` 里的 UUID/相机原始图，按当前仓库的 food notes 样式整理成：

```text
data/food_notes/items/<中文菜名>/1.jpg
data/food_notes/items/<中文菜名>/2.jpg
data/food_notes/items/<中文菜名>/3.jpg
data/food_notes/items/<中文菜名>/content.md
data/food_notes/items/<中文菜名>/meta.yaml
```

这个 skill 只负责图片整理；除非用户另说，不创建或改写 `content.md`，也不移动、删除 `raw/` 原图。

## 标准流程

1. 默认把 `data/food_notes/raw` 当作原图目录，把 `data/food_notes/items` 当作菜品输出根目录。
2. 所有 Python 命令都从项目根目录用 `uv run python ...` 执行，不使用系统 `python3`。如果缺少脚本依赖，先安装到 uv 项目环境，例如：

```bash
uv add pillow
```

3. 先运行 `preview`，生成缩略图联系表、索引和 `mapping.json`：

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py preview \
  data/food_notes/raw \
  --output-dir data/food_notes/_preview
```

4. 查看 `data/food_notes/_preview/preview.html` 或 `sheet_*.jpg`。每张图左下角有编号，编号对应 `index.md` / `index.json`。
5. 编辑 `data/food_notes/_preview/mapping.json`，把同一道菜的图片按输出顺序填到 `groups` 里：

```json
{
  "groups": {
    "番茄牛腩面": [2, 8, 19],
    "沙威玛": ["0A39FDA2-0624-441F-9F8C-D569CF6264D6.jpeg", 12, 31]
  },
  "exclude": []
}
```

6. 先确认分组计划，不落盘：

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py check \
  data/food_notes/raw \
  --base-dir data/food_notes/items \
  --mapping data/food_notes/_preview/mapping.json
```

7. `missing_indexes` 和 `duplicate_indexes` 都符合预期后，再写入编号 JPG：

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py apply \
  data/food_notes/raw \
  --base-dir data/food_notes/items \
  --mapping data/food_notes/_preview/mapping.json \
  --yes
```

## 命名和确认规则

- 目录名默认使用中文菜名；只有拿到小红书发帖时间时，才使用 `YYYY-MM-DD_中文菜名`。
- 不要用 raw EXIF 或本机文件系统时间给目录加日期；raw EXIF 只能写进 `capture_times`，文件系统时间只能写进 `file_times`，都要注明来源。
- 菜名使用第 1 页上最明显的中文菜名，只做必要的文件系统安全清理。
- 每组图片顺序就是最终 `1.jpg`、`2.jpg`、`3.jpg` 的顺序。
- 每张 raw 图片默认应该进入且只进入一个分组；确实不要整理的图片放进 `exclude`。
- 如果本轮只整理一部分 raw 图片，可以在 `check/apply` 加 `--allow-missing`，并在汇报里说明为什么有缺失编号。
- 目标文件已存在时默认停止；需要重跑覆盖时加 `--overwrite`。
- `apply` 不带 `--yes` 时只做 dry run，不写文件。

## 兼容旧用法

脚本保留了旧命令别名：

- `sheets` 等同于 `preview`
- `confirm` / `plan` 等同于 `check`
- `organize` 等同于 `apply`

旧版的顶层映射格式仍可用：

```json
{
  "沙威玛": [3, 52, 44],
  "番茄牛腩面": [2, 8, 19],
  "__exclude__": [7]
}
```

## 汇报要求

完成后向用户汇报：

- 生成的预览目录或写入目录。
- 整理出的分组数和图片数。
- `missing_indexes`、`duplicate_indexes` 是否为空；如果不为空，说明原因。
- 抽查最终目录是否是 `data/food_notes/items/<菜名>/1.jpg 2.jpg 3.jpg`，或在有可靠日期时为 `data/food_notes/items/<YYYY-MM-DD>_<菜名>/1.jpg 2.jpg 3.jpg`。
