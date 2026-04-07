"""
用途：
将单张图片或整个目录中的图片批量转换为 JPG 格式，适合在小红书视频素材预处理中统一图片格式。

支持格式：
PNG、WEBP、JPEG、JPG、BMP、TIF、TIFF

功能说明：
1. 支持传入单个文件或目录。
2. 支持递归扫描子目录。
3. 支持指定输出目录。
4. 支持设置 JPEG 质量。
5. 支持覆盖已存在的 JPG 文件。

用法示例：
uv run image2jpg data/20260406/image/1.0.jpeg
uv run image2jpg data/20260406/image -r
uv run image2jpg data/20260406/image -r -o data/20260406/jpg
uv run image2jpg data/20260406/image -r -o data/20260406/jpg --overwrite
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SUPPORTED_SUFFIXES = {".png", ".webp", ".jpeg", ".jpg", ".bmp", ".tif", ".tiff"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert images to JPG format.",
    )
    parser.add_argument("input", type=Path, help="Input image file or directory.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory. Defaults to the input file's parent or the input directory itself.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan directories for images.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality from 1 to 100. Default is 95.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JPG files.",
    )
    return parser


def collect_images(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in input_path.glob(pattern)
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def convert_image(source: Path, target: Path, quality: int, overwrite: bool) -> bool:
    if target.exists() and not overwrite:
        print(f"skip exists: {target}")
        return False

    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        rgba_image = image.convert("RGBA")
        # JPEG does not support alpha; flatten onto white for predictable output.
        converted = Image.new("RGB", rgba_image.size, "white")
        converted.paste(rgba_image, mask=rgba_image.getchannel("A"))
        converted.save(target, format="JPEG", quality=quality, optimize=True)

    print(f"converted: {source} -> {target}")
    return True


def resolve_target(source: Path, input_root: Path, output_dir: Path | None) -> Path:
    target_name = f"{source.stem}.jpg"
    if output_dir is None:
        return source.with_suffix(".jpg")

    if input_root.is_file():
        return output_dir / target_name

    relative_parent = source.relative_to(input_root).parent
    return output_dir / relative_parent / target_name


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.expanduser().resolve()

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    if not 1 <= args.quality <= 100:
        raise SystemExit("Quality must be between 1 and 100.")

    images = collect_images(input_path, recursive=args.recursive)
    if not images:
        raise SystemExit("No supported images found.")

    converted_count = 0
    for source in images:
        target = resolve_target(source, input_path, args.output_dir)
        if source.resolve() == target.resolve():
            print(f"skip same path: {source}")
            continue
        if convert_image(source, target, args.quality, args.overwrite):
            converted_count += 1

    print(f"done: {converted_count}/{len(images)} converted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
