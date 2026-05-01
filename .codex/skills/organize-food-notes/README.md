# 整理食物小志图片

把 `data/food_notes/raw` 里的食物小志原图整理成仓库当前使用的目录形态：

```text
data/food_notes/<菜名>/1.jpg
data/food_notes/<菜名>/2.jpg
data/food_notes/<菜名>/3.jpg
```

## 1. 生成缩略图预览

从仓库根目录执行，Python 一律走 uv 环境：

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py preview \
  data/food_notes/raw \
  --output-dir data/food_notes/_preview
```

如果提示缺少依赖，先安装进 uv 项目环境：

```bash
uv add pillow
```

输出：

- `preview.html`
- `sheet_01.jpg`、`sheet_02.jpg` ...
- `index.md`
- `index.json`
- `mapping.json`

## 2. 编辑分组

打开 `data/food_notes/_preview/mapping.json`，按缩略图编号填写：

```json
{
  "groups": {
    "番茄牛腩面": [2, 8, 19],
    "沙威玛": [3, 52, 44]
  },
  "exclude": []
}
```

`groups` 的顺序就是最终 `1.jpg`、`2.jpg`、`3.jpg` 的顺序。确实不要整理的 raw 图放进 `exclude`。

## 3. 确认分组

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py check \
  data/food_notes/raw \
  --base-dir data/food_notes \
  --mapping data/food_notes/_preview/mapping.json
```

确认 `missing_indexes` 和 `duplicate_indexes` 符合预期。

## 4. 写入结果

```bash
uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py apply \
  data/food_notes/raw \
  --base-dir data/food_notes \
  --mapping data/food_notes/_preview/mapping.json \
  --yes
```

常用选项：

- `--overwrite`：覆盖已有的 `1.jpg`、`2.jpg`、`3.jpg`。
- `--allow-missing`：允许只整理一部分 raw 图片。
- `--quality 95`：设置输出 JPEG 质量。

不加 `--yes` 时，`apply` 只做 dry run，不会写文件。
