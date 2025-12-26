"""Folder + file-type verification helper.

Purpose:
- Quickly validate a target import directory exists and is readable.
- Produce a Pareto-style breakdown of files by extension and total bytes.

This is intended for "Needs Verification" checks where the system is expected
to ingest/monitor an import folder.

Usage:
  python tools/verify_import_folder.py --path "C:\\...\\import" --recursive

Exit codes:
- 0: Success
- 2: Invalid path / unreadable
"""

from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FileStat:
    path: Path
    size: int


def _iter_files(root: Path, recursive: bool) -> Iterable[FileStat]:
    # Use os.scandir for speed on Windows.
    # Avoid following symlinks to prevent loops.
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                stack.append(Path(entry.path))
                            continue
                        if entry.is_file(follow_symlinks=False):
                            try:
                                size = entry.stat(follow_symlinks=False).st_size
                            except OSError:
                                # Permission/race: treat as 0 but still count.
                                size = 0
                            yield FileStat(path=Path(entry.path), size=size)
                    except OSError:
                        # Skip unreadable entries.
                        continue
        except OSError:
            # Skip unreadable directories.
            continue


def _ext_key(p: Path) -> str:
    ext = p.suffix.lower().strip()
    return ext if ext else "<no_ext>"


def _human_bytes(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for u in units:
        if value < 1024.0 or u == units[-1]:
            return f"{value:.2f}{u}" if u != "B" else f"{int(value)}B"
        value /= 1024.0
    return f"{value:.2f}TB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify import folder by file type.")
    parser.add_argument("--path", required=True, help="Folder path to scan")
    parser.add_argument("--recursive", action="store_true", help="Scan subfolders")
    parser.add_argument("--top", type=int, default=15, help="Top N extensions to print")
    parser.add_argument(
        "--limit-files",
        type=int,
        default=250_000,
        help="Safety cap on number of files to scan",
    )
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"ERROR: Not a directory: {root}")
        return 2

    ext_counts: Counter[str] = Counter()
    ext_bytes: dict[str, int] = defaultdict(int)
    total_files = 0
    total_bytes = 0

    for fs in _iter_files(root, recursive=args.recursive):
        total_files += 1
        if total_files > args.limit_files:
            print(f"ERROR: exceeded --limit-files={args.limit_files}; aborting scan")
            return 2
        total_bytes += fs.size
        k = _ext_key(fs.path)
        ext_counts[k] += 1
        ext_bytes[k] += fs.size

    print(f"Path: {root}")
    print(f"Recursive: {bool(args.recursive)}")
    print(f"Files scanned: {total_files}")
    print(f"Total size: {_human_bytes(total_bytes)}")

    if total_files == 0:
        print("No files found.")
        return 0

    # Pareto by file count
    top = ext_counts.most_common(args.top)
    print("\nTop extensions by count (Pareto):")
    running = 0
    for ext, n in top:
        running += n
        pct = (n / total_files) * 100.0
        cum = (running / total_files) * 100.0
        print(f"- {ext:10s}  {n:8d}  ({pct:5.1f}%)  cumulative {cum:5.1f}%  bytes {_human_bytes(ext_bytes[ext])}")

    # Also show top by size (useful when many small files)
    top_by_size = sorted(ext_bytes.items(), key=lambda kv: kv[1], reverse=True)[: args.top]
    print("\nTop extensions by total bytes:")
    for ext, b in top_by_size:
        print(f"- {ext:10s}  {_human_bytes(b)}  (count {ext_counts.get(ext, 0)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
