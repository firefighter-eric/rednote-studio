#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
INVALID_NAME_CHARS = re.compile(r'[/:*?"<>|]')
LEGACY_EXCLUDE_KEYS = {"__exclude__", "__skip__"}
LEGACY_IGNORED_KEYS = {"__unassigned__", "unassigned"}


@dataclass(frozen=True)
class ImageEntry:
    index: int
    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class GroupPlan:
    name: str
    safe_name: str
    entries: tuple[ImageEntry, ...]
    output_dir: Path


@dataclass(frozen=True)
class OrganizePlan:
    raw_dir: Path
    base_dir: Path
    groups: tuple[GroupPlan, ...]
    excluded: tuple[ImageEntry, ...]
    missing_indexes: tuple[int, ...]
    duplicate_indexes: tuple[int, ...]
    errors: tuple[str, ...]


def collect_images(raw_dir: Path) -> list[Path]:
    if not raw_dir.exists():
        raise SystemExit(f"Raw directory not found: {raw_dir}")
    if not raw_dir.is_dir():
        raise SystemExit(f"Raw path is not a directory: {raw_dir}")
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


def read_entry(index: int, path: Path) -> ImageEntry:
    with Image.open(path) as image:
        width, height = ImageOps.exif_transpose(image).size
    return ImageEntry(index=index, path=path, width=width, height=height)


def collect_entries(raw_dir: Path) -> list[ImageEntry]:
    files = collect_images(raw_dir)
    if not files:
        raise SystemExit(f"No supported images found in {raw_dir}")
    return [read_entry(index, path) for index, path in enumerate(files, 1)]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont | None:
    for font_path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return None


def write_preview_files(entries: list[ImageEntry], raw_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    index_rows = [
        {
            "index": entry.index,
            "filename": entry.path.name,
            "path": str(entry.path),
            "width": entry.width,
            "height": entry.height,
        }
        for entry in entries
    ]
    (output_dir / "index.json").write_text(
        json.dumps(
            {"raw_dir": str(raw_dir), "count": len(entries), "images": index_rows},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    index_md = ["# Food Notes Raw Image Index", "", f"Raw dir: `{raw_dir}`", ""]
    index_md.append("| # | filename | size |")
    index_md.append("| ---: | --- | --- |")
    for entry in entries:
        index_md.append(f"| {entry.index:02d} | `{entry.path.name}` | {entry.width}x{entry.height} |")
    (output_dir / "index.md").write_text("\n".join(index_md) + "\n", encoding="utf-8")

    mapping_template = {
        "_comment": [
            "Fill groups with indexes from index.md or sheet_*.jpg.",
            "Each group is written as <food-name>/1.jpg, 2.jpg, 3.jpg in this order.",
            "Put intentionally ignored source indexes in exclude.",
            "Run check before apply.",
        ],
        "groups": {},
        "exclude": [],
        "unassigned": [entry.index for entry in entries],
    }
    template_path = output_dir / "mapping.template.json"
    template_path.write_text(
        json.dumps(mapping_template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    mapping_path = output_dir / "mapping.json"
    if not mapping_path.exists():
        mapping_path.write_text(
            json.dumps(mapping_template, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

def generate_sheets(args: argparse.Namespace) -> int:
    raw_dir = args.raw_dir.expanduser().resolve()
    entries = collect_entries(raw_dir)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for stale_sheet in output_dir.glob("sheet_*.jpg"):
        stale_sheet.unlink()

    font = load_font(16)
    per_sheet = args.columns * args.rows
    sheet_paths: list[Path] = []

    for sheet_index in range(math.ceil(len(entries) / per_sheet)):
        chunk = entries[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        sheet = Image.new(
            "RGB",
            (args.columns * args.thumb_size, args.rows * (args.thumb_size + 34)),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for item_index, entry in enumerate(chunk):
            row, col = divmod(item_index, args.columns)
            with open_rgb(entry.path) as image:
                image.thumbnail((args.thumb_size, args.thumb_size), Image.Resampling.LANCZOS)
                x = col * args.thumb_size + (args.thumb_size - image.width) // 2
                y = row * (args.thumb_size + 34) + (args.thumb_size - image.height) // 2
                sheet.paste(image, (x, y))
            label = f"{entry.index:02d} {entry.path.name[:8]}"
            draw.text(
                (col * args.thumb_size + 6, row * (args.thumb_size + 34) + args.thumb_size + 6),
                label,
                fill="black",
                font=font,
            )
        output_path = output_dir / f"sheet_{sheet_index + 1:02d}.jpg"
        sheet.save(output_path, quality=args.quality)
        sheet_paths.append(output_path)

    write_preview_files(entries, raw_dir, output_dir)
    write_preview_html(entries, sheet_paths, output_dir)

    print(f"raw_dir: {raw_dir}")
    print(f"images: {len(entries)}")
    print(f"preview_dir: {output_dir}")
    print(f"preview_html: {output_dir / 'preview.html'}")
    print(f"mapping_file: {output_dir / 'mapping.json'}")
    print("sheets:")
    for path in sheet_paths:
        print(f"  {path}")
    print("next:")
    print(f"  1. Edit {output_dir / 'mapping.json'}")
    default_base_dir = raw_dir.parent / "items"
    print(
        "  2. uv run python .codex/skills/organize-food-notes/scripts/organize_food_notes.py "
        f"check {raw_dir} --base-dir {default_base_dir} --mapping {output_dir / 'mapping.json'}"
    )
    return 0


def write_preview_html(entries: list[ImageEntry], sheet_paths: list[Path], output_dir: Path) -> None:
    sheet_sections = "\n".join(
        f'<section><h2>{html.escape(path.name)}</h2><img src="{html.escape(path.name)}" /></section>'
        for path in sheet_paths
    )
    rows = "\n".join(
        "<tr>"
        f"<td>{entry.index:02d}</td>"
        f"<td><code>{html.escape(entry.path.name)}</code></td>"
        f"<td>{entry.width}x{entry.height}</td>"
        "</tr>"
        for entry in entries
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Food Notes Preview</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
    img {{ max-width: 100%; border: 1px solid #ddd; }}
    section {{ margin-bottom: 32px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
    code {{ font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Food Notes Preview</h1>
  {sheet_sections}
  <h2>Index</h2>
  <table>
    <thead><tr><th>#</th><th>filename</th><th>size</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
    (output_dir / "preview.html").write_text(document, encoding="utf-8")


def read_mapping_data(mapping_path: Path) -> tuple[dict[str, Any], list[Any]]:
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Mapping must be a JSON object.")

    if "groups" in data:
        groups = data["groups"]
        if not isinstance(groups, dict):
            raise SystemExit("Mapping field 'groups' must be an object.")
        exclude = data.get("exclude", [])
        if not isinstance(exclude, list):
            raise SystemExit("Mapping field 'exclude' must be a list.")
        return groups, exclude

    groups = {
        name: items
        for name, items in data.items()
        if not name.startswith("_") and name not in LEGACY_EXCLUDE_KEYS | LEGACY_IGNORED_KEYS
    }
    exclude: list[Any] = []
    for key in LEGACY_EXCLUDE_KEYS:
        if key in data:
            if not isinstance(data[key], list):
                raise SystemExit(f"Mapping field '{key}' must be a list.")
            exclude.extend(data[key])
    return groups, exclude


def resolve_mapping_item(item: Any, by_index: dict[int, ImageEntry], by_name: dict[str, ImageEntry]) -> ImageEntry:
    if isinstance(item, int):
        if item in by_index:
            return by_index[item]
        raise ValueError(f"Image index not found: {item}")

    if isinstance(item, str):
        stripped = item.strip()
        if stripped.isdigit() and int(stripped) in by_index:
            return by_index[int(stripped)]
        if stripped in by_name:
            return by_name[stripped]
        raise ValueError(f"Image filename or index not found: {item}")

    raise ValueError(f"Mapping item must be an integer index or filename string: {item!r}")


def build_plan(args: argparse.Namespace) -> OrganizePlan:
    raw_dir = args.raw_dir.expanduser().resolve()
    base_dir = args.base_dir.expanduser().resolve()
    mapping_path = args.mapping.expanduser().resolve()

    entries = collect_entries(raw_dir)
    by_index = {entry.index: entry for entry in entries}
    by_name = {entry.path.name: entry for entry in entries}
    groups_data, exclude_items = read_mapping_data(mapping_path)

    errors: list[str] = []
    groups: list[GroupPlan] = []
    used_indexes: list[int] = []

    if not groups_data:
        errors.append("Mapping has no groups.")

    seen_safe_names: set[str] = set()
    for food_name, items in groups_data.items():
        if not isinstance(food_name, str):
            errors.append(f"Food name must be a string: {food_name!r}")
            continue
        if not isinstance(items, list):
            errors.append(f"Group '{food_name}' must be a list.")
            continue
        if not items:
            errors.append(f"Group '{food_name}' is empty.")
            continue

        try:
            safe_name = safe_dir_name(food_name)
        except ValueError as exc:
            errors.append(f"Group '{food_name}' has invalid directory name: {exc}")
            continue

        if safe_name in seen_safe_names:
            errors.append(f"Duplicate target directory after cleanup: {safe_name}")
            continue
        seen_safe_names.add(safe_name)

        resolved_entries: list[ImageEntry] = []
        for item in items:
            try:
                entry = resolve_mapping_item(item, by_index, by_name)
            except ValueError as exc:
                errors.append(f"Group '{food_name}': {exc}")
                continue
            resolved_entries.append(entry)
            used_indexes.append(entry.index)

        groups.append(
            GroupPlan(
                name=food_name,
                safe_name=safe_name,
                entries=tuple(resolved_entries),
                output_dir=base_dir / safe_name,
            )
        )

    excluded: list[ImageEntry] = []
    for item in exclude_items:
        try:
            entry = resolve_mapping_item(item, by_index, by_name)
        except ValueError as exc:
            errors.append(f"Exclude: {exc}")
            continue
        excluded.append(entry)
        used_indexes.append(entry.index)

    duplicate_indexes = tuple(sorted(index for index, count in Counter(used_indexes).items() if count > 1))
    missing_indexes = tuple(sorted(set(by_index) - set(used_indexes)))

    return OrganizePlan(
        raw_dir=raw_dir,
        base_dir=base_dir,
        groups=tuple(groups),
        excluded=tuple(excluded),
        missing_indexes=missing_indexes,
        duplicate_indexes=duplicate_indexes,
        errors=tuple(errors),
    )


def print_plan(plan: OrganizePlan) -> None:
    print(f"raw_dir: {plan.raw_dir}")
    print(f"base_dir: {plan.base_dir}")
    print(f"groups: {len(plan.groups)}")
    for group in plan.groups:
        print(f"- {group.name} -> {group.output_dir}")
        for number, entry in enumerate(group.entries, 1):
            print(f"  {number}.jpg <= {entry.index:02d} {entry.path.name}")

    if plan.excluded:
        excluded = ", ".join(f"{entry.index:02d}" for entry in plan.excluded)
        print(f"excluded_indexes: [{excluded}]")
    else:
        print("excluded_indexes: []")
    print(f"missing_indexes: {list(plan.missing_indexes)}")
    print(f"duplicate_indexes: {list(plan.duplicate_indexes)}")
    if plan.errors:
        print("errors:")
        for error in plan.errors:
            print(f"  - {error}")


def collect_write_errors(plan: OrganizePlan, overwrite: bool, allow_missing: bool) -> list[str]:
    errors = list(plan.errors)
    if plan.duplicate_indexes:
        errors.append(f"Duplicate source indexes: {list(plan.duplicate_indexes)}")
    if plan.missing_indexes and not allow_missing:
        errors.append(f"Missing source indexes: {list(plan.missing_indexes)}")
    if not overwrite:
        for group in plan.groups:
            for number, _entry in enumerate(group.entries, 1):
                target = group.output_dir / f"{number}.jpg"
                if target.exists():
                    errors.append(f"Target exists; use --overwrite to replace: {target}")
    return errors


def check_mapping(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    print_plan(plan)
    errors = collect_write_errors(plan, overwrite=args.overwrite, allow_missing=args.allow_missing)
    if errors:
        print("status: not ready")
        for error in errors:
            if error not in plan.errors:
                print(f"  - {error}")
        return 1
    print("status: ready")
    return 0


def apply_mapping(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    print_plan(plan)
    errors = collect_write_errors(plan, overwrite=args.overwrite, allow_missing=args.allow_missing)
    if errors:
        print("status: not ready")
        for error in errors:
            if error not in plan.errors:
                print(f"  - {error}")
        return 1

    if not args.yes:
        print("status: dry-run")
        print("No files written. Add --yes to write numbered JPG files.")
        return 0

    written = 0
    for group in plan.groups:
        group.output_dir.mkdir(parents=True, exist_ok=True)
        for number, entry in enumerate(group.entries, 1):
            target = group.output_dir / f"{number}.jpg"
            with open_rgb(entry.path) as image:
                image.save(target, format="JPEG", quality=args.quality, optimize=True)
            written += 1
            print(f"wrote: {target}")

    print(f"wrote_groups: {len(plan.groups)}")
    print(f"wrote_files: {written}")
    return 0


def add_common_mapping_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow raw images to be intentionally left out of groups/exclude.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing numbered JPG files.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Organize food-note photos into per-food JPG folders.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser(
        "preview",
        aliases=["sheets"],
        help="Create contact sheets, index files, and a mapping JSON template.",
    )
    preview.add_argument("raw_dir", type=Path)
    preview.add_argument("--output-dir", type=Path, default=Path("data/food_notes/_preview"))
    preview.add_argument("--columns", type=int, default=4)
    preview.add_argument("--rows", type=int, default=4)
    preview.add_argument("--thumb-size", type=int, default=220)
    preview.add_argument("--quality", type=int, default=92)
    preview.set_defaults(func=generate_sheets)

    check = subparsers.add_parser(
        "check",
        aliases=["plan", "confirm"],
        help="Print and validate the grouping plan without writing files.",
    )
    add_common_mapping_args(check)
    check.set_defaults(func=check_mapping)

    apply = subparsers.add_parser(
        "apply",
        aliases=["organize"],
        help="Copy/convert mapped images to numbered JPGs after confirmation.",
    )
    add_common_mapping_args(apply)
    apply.add_argument("--quality", type=int, default=95)
    apply.add_argument("--yes", action="store_true", help="Actually write files.")
    apply.set_defaults(func=apply_mapping)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "quality") and not 1 <= args.quality <= 100:
        raise SystemExit("Quality must be between 1 and 100.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
