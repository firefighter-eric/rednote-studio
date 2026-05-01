# rednote_studio

`uv` 初始化的小红书视频项目。

当前项目先提供一个轻量骨架，方便你后续继续接入：

- 文案生成
- 分镜规划
- 图片素材整理
- 视频渲染与导出

## 快速开始

```bash
uv sync
uv run rednote_studio --help
```

## 项目结构

```text
.
├── data/                  # 现有素材和输出目录
├── rednote_studio/        # Python 包源码
├── pyproject.toml         # uv 项目配置
└── README.md
```

## 常用命令

```bash
uv run rednote_studio info
uv run rednote_studio init-workspace
```

## 后续方向

你后面可以继续往这个项目里加：

- `ffmpeg-python` 或直接调用 `ffmpeg`
- 文案/字幕生成模块
- 图片转视频、口播、字幕烧录流水线
- 多账号/多主题批量出片脚本
