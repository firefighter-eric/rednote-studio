#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
INVALID_NAME_CHARS = re.compile(r'[/:*?"<>|]')


def collect_images(raw_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in raw_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def safe_dir_name(name: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("_", name).strip()
    if not cleaned:
        raise ValueError("Food directory name cannot be empty.")
    return cleaned


def open_rgb(path: Path) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path))
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, "white")
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    return image.convert("RGB")


def generate_sheets(args: argparse.Namespace) -> int:
    raw_dir = args.raw_dir.expanduser().resolve()
    files = collect_images(raw_dir)
    if not files:
        raise SystemExit(f"No supported images found in {raw_dir}")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        font = None

    per_sheet = args.columns * args.rows
    for sheet_index in range(math.ceil(len(files) / per_sheet)):
        chunk = files[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        sheet = Image.new(
            "RGB",
            (args.columns * args.thumb_size, args.rows * (args.thumb_size + 34)),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for item_index, path in enumerate(chunk):
            row, col = divmod(item_index, args.columns)
            with open_rgb(path) as image:
                image.thumbnail((args.thumb_size, args.thumb_size), Image.Resampling.LANCZOS)
                x = col * args.thumb_size + (args.thumb_size - image.width) // 2
                y = row * (args.thumb_size + 34) + (args.thumb_size - image.height) // 2
                sheet.paste(image, (x, y))
            absolute_index = sheet_index * per_sheet + item_index + 1
            label = f"{absolute_index:02d} {path.name[:8]}"
            draw.text(
                (col * args.thumb_size + 6, row * (args.thumb_size + 34) + args.thumb_size + 6),
                label,
                fill="black",
                font=font,
            )
        output_path = output_dir / f"sheet_{sheet_index + 1}.jpg"
        sheet.save(output_path, quality=92)
        print(output_path)

    print("Index:")
    for index, path in enumerate(files, 1):
        print(f"{index:02d} {path.name}")
    return 0


def resolve_mapping_item(item: int | str, by_index: dict[int, Path], by_name: dict[str, Path]) -> Path:
    if isinstance(item, int):
        if item not in by_index:
            raise SystemExit(f"Image index not found: {item}")
        return by_index[item]
    if item.isdigit():
        index = int(item)
        if index in by_index:
            return by_index[index]
    if item not in by_name:
        raise SystemExit(f"Image filename not found: {item}")
    return by_name[item]


def organize(args: argparse.Namespace) -> int:
    raw_dir = args.raw_dir.expanduser().resolve()
    base_dir = args.base_dir.expanduser().resolve()
    files = collect_images(raw_dir)
    if not files:
        raise SystemExit(f"No supported images found in {raw_dir}")

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    by_index = {index: path for index, path in enumerate(files, 1)}
    by_name = {path.name: path for path in files}

    used_indexes: list[int] = []
    for food_name, items in mapping.items():
        output_dir = base_dir / safe_dir_name(food_name)
        output_dir.mkdir(parents=True, exist_ok=True)
        for number, item in enumerate(items, 1):
            source = resolve_mapping_item(item, by_index, by_name)
            used_indexes.append(files.index(source) + 1)
            target = output_dir / f"{number}.jpg"
            if target.exists() and not args.overwrite:
                raise SystemExit(f"Target exists; use --overwrite to replace: {target}")
            with open_rgb(source) as image:
                image.save(target, format="JPEG", quality=args.quality, optimize=True)

    missing = sorted(set(by_index) - set(used_indexes))
    duplicates = sorted(index for index in set(used_indexes) if used_indexes.count(index) > 1)
    print(f"organized_groups: {len(mapping)}")
    print(f"organized_files: {len(used_indexes)}")
    print(f"missing_indexes: {missing}")
    print(f"duplicate_indexes: {duplicates}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Organize food-note photos into per-food JPG folders.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sheets = subparsers.add_parser("sheets", help="Create contact sheets for visual grouping.")
    sheets.add_argument("raw_dir", type=Path)
    sheets.add_argument("--output-dir", type=Path, default=Path("/tmp/food_notes_sheets"))
    sheets.add_argument("--columns", type=int, default=4)
    sheets.add_argument("--rows", type=int, default=4)
    sheets.add_argument("--thumb-size", type=int, default=220)
    sheets.set_defaults(func=generate_sheets)

    organize_parser = subparsers.add_parser("organize", help="Copy/convert mapped images to numbered JPGs.")
    organize_parser.add_argument("raw_dir", type=Path)
    organize_parser.add_argument("--base-dir", type=Path, required=True)
    organize_parser.add_argument("--mapping", type=Path, required=True)
    organize_parser.add_argument("--quality", type=int, default=95)
    organize_parser.add_argument("--overwrite", action="store_true")
    organize_parser.set_defaults(func=organize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
