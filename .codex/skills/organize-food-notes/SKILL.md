---
name: organize-food-notes
description: 整理“食物小志/食物笔记”类食谱图片：按每组第一张图上醒目的中文菜名建立目录，并输出 1.jpg、2.jpg、3.jpg 这类连续编号文件。适用于 Codex 需要清理 data/food_notes 或类似 raw 食物图片素材、保留 raw 原图、生成缩略图联系表辅助视觉分组，或把一批食谱长图整理成稳定的中文菜名目录时。
---

# 整理食物小志图片

## 目标

把原始食物笔记/食谱长图整理成易读的素材目录：

```text
data/food_notes/<中文菜名>/1.jpg
data/food_notes/<中文菜名>/2.jpg
data/food_notes/<中文菜名>/3.jpg
```

除非用户明确要求移动或删除原图，否则保留 `raw/` 里的 UUID/相机原始文件名。

## 工作流

1. 检查目标目录。优先把 `data/food_notes/raw` 当作原图来源；只有在存在多个可能的原图目录且无法判断时才询问用户。
2. 用 `scripts/organize_food_notes.py sheets ...` 生成缩略图联系表。
3. 根据视觉内容把图片按同一道菜/同一组食谱分组。目录名使用第 1 页上最明显的中文大标题。
4. 创建一个 JSON 映射表，把中文菜名映射到排序后的图片编号或文件名。
5. 用 `scripts/organize_food_notes.py organize ...` 复制并转换图片，输出为连续编号的 JPG。
6. 验证每张支持格式的原图都进入且只进入一个分组，除非用户明确要求排除某些图片。

## 命名规则

- 图片上有清晰中文标题时，使用中文目录名。
- 优先使用第一张图上的原始标题，只做必要的文件系统安全清理。
- 保留自然顺序：封面/介绍页在前，做法页在中间，营养/环境/收尾页在后。
- 遇到重复页时，只有明显不同或用户要求全部保留时才都放入整理目录。
- 每个菜名目录里使用 `1.jpg`、`2.jpg` 等文件名，不保留 UUID 文件名。
- 默认不改动 `raw/`。

## 脚本用法

生成视觉索引联系表：

```bash
python3 .codex/skills/organize-food-notes/scripts/organize_food_notes.py sheets \
  data/food_notes/raw \
  --output-dir /tmp/food_notes_sheets
```

创建映射 JSON：

```json
{
  "沙威玛": [3, 52, 44],
  "番茄牛腩面": [2, 8, 19]
}
```

编号来自脚本打印的原图排序列表，也会显示在联系表上。映射表里也可以直接使用文件名。

在保留原图的同时，整理输出为连续编号 JPG：

```bash
python3 .codex/skills/organize-food-notes/scripts/organize_food_notes.py organize \
  data/food_notes/raw \
  --base-dir data/food_notes \
  --mapping /tmp/food_notes_mapping.json
```

## 验证

- 汇报整理出的分组数和图片数。
- 确认 `missing_indexes` 为空，除非有刻意排除的图片。
- 抽查生成后的目录列表和每个目录里的编号文件。
