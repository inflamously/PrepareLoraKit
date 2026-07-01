#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from ast import walk
from collections.abc import Iterable, Iterator
from pathlib import Path

DEFAULT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".html",
    ".vue",
    ".svelte",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
}

DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
THIRD_PARTY_DIRS = {"third_party", "vendor"}
ScanRow = dict[str, str | int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List largest source files for complexity-debt triage."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument("--top", type=int, default=80, help="Number of rows to print.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="Only print files with at least this many lines.",
    )
    parser.add_argument(
        "--include-third-party",
        action="store_true",
        default=False,
        help="Include third_party and vendor folders in the main listing.",
    )
    parser.add_argument(
        "--extensions",
        action="append",
        default=None,
        help="Extension to include. Can be passed more than once. Defaults to common source extensions.",
    )
    parser.add_argument(
        "--excludes",
        action="append",
        default=None,
        help="Additional directory name to exclude. Can be passed more than once.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print results as a JSON array.",
    )
    parser.add_argument(
        "--third-party-dir",
        action="append",
        default=None,
        help="Additional directory names to include as third_party. Can be passed more than once.",
    )
    return parser.parse_args()


def normalize_extension(extension: str) -> str:
    if extension.startswith("."):
        return extension
    return f".{extension}"


def normalize_extensions(extensions: Iterable[str] | None) -> set[str]:
    return {
        normalize_extension(extension)
        for extension in (extensions or DEFAULT_EXTENSIONS)
    }


def normalize_excludes(excludes: Iterable[str] | None, third_party_dirs: Iterable[str] | None) -> set[str]:
    return set(list(DEFAULT_EXCLUDES | set(excludes or [])) + list(third_party_dirs or []))


def resolve_root(root: str) -> Path:
    return Path(root).resolve()


def should_skip_source_file(path: Path, root: Path, include_third_party: bool, excludes: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts
    return should_skip_parts(rel_parts, include_third_party, excludes)


def should_skip_parts(
        parts: tuple[str, ...],
        include_third_party: bool,
        excludes: set[str],
) -> bool:
    return has_excluded_part(parts, excludes) or has_skipped_third_party_part(
        parts,
        include_third_party,
    )


def has_excluded_part(parts: tuple[str, ...], excludes: set[str]) -> bool:
    return any(part in excludes for part in parts)


def has_skipped_third_party_part(parts: tuple[str, ...], include_third_party: bool) -> bool:
    return not include_third_party and any(part in THIRD_PARTY_DIRS for part in parts)


def should_descend_dir(
        dirname: str,
        include_third_party: bool,
        excludes: set[str]) -> bool:
    if dirname in excludes:
        return False
    if not include_third_party and dirname in THIRD_PARTY_DIRS:
        return False
    return True


def prune_dirnames(
        dirnames: list[str],
        include_third_party: bool,
        excludes: set[str],
) -> None:
    dirnames[:] = [
        dirname
        for dirname in dirnames
        if should_descend_dir(dirname, include_third_party, excludes)
    ]


def has_included_extension(path: Path, extensions: set[str]) -> bool:
    return path.suffix in extensions


def line_count(path: Path) -> int:
    try:
        with path.open("rb") as filehandle:
            return sum(1 for _ in filehandle)
    except OSError:
        return 0


def walk_source_files(
        root: Path,
        extensions: set[str],
        include_third_party: bool,
        excludes: set[str],
) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        prune_dirnames(dirnames, include_third_party, excludes)
        for filename in filenames:
            path = current / filename
            if has_included_extension(path, extensions):
                yield path


def make_row(path: Path, root: Path, count: int) -> ScanRow:
    return {
        "loc": count,
        "path": path.relative_to(root).as_posix(),
    }


def collect_rows(
        root: Path,
        extensions: set[str],
        include_third_party: bool,
        excludes: set[str],
        threshold: int,
) -> list[ScanRow]:
    rows: list[ScanRow] = []
    for sourcefile_path in walk_source_files(root, extensions, include_third_party, excludes):
        if should_skip_source_file(sourcefile_path, root, include_third_party, excludes):
            continue
        count = line_count(sourcefile_path)
        if count >= threshold:
            rows.append(make_row(sourcefile_path, root, count))
    return rows


def row_sort_key(row: ScanRow) -> tuple[int, str]:
    return int(row["loc"]), str(row["path"])


def top_rows(rows: Iterable[ScanRow], limit: int) -> list[ScanRow]:
    return sorted(rows, key=row_sort_key, reverse=True)[:limit]


def format_text_row(row: ScanRow) -> str:
    return f"loc: {row.get('loc')}; path: {row.get('path')}"


def print_json_rows(rows: list[ScanRow]) -> None:
    print(json.dumps(rows, indent=2))


def print_text_rows(rows: list[ScanRow]) -> None:
    for row in rows:
        print(format_text_row(row))


def print_rows(rows: list[ScanRow], as_json: bool) -> None:
    if as_json:
        print_json_rows(rows)
        return
    print_text_rows(rows)


def run(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    extensions = normalize_extensions(args.extensions)
    excludes = normalize_excludes(args.excludes, args.third_party_dir)
    rows = collect_rows(
        root,
        extensions,
        args.include_third_party,
        excludes,
        args.threshold,
    )
    print_rows(top_rows(rows, args.top), args.json)
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
