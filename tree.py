#!/usr/bin/env python3
import os
import sys
from pathlib import Path

EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
EXCLUDED_FILES = {".DS_Store"}

def print_tree(root: Path, prefix: str = ""):
    # Filter entries, skip excluded dirs/files
    try:
        entries = [
            e for e in root.iterdir()
            if not (e.is_dir() and e.name in EXCLUDED_DIRS)
            and not (e.is_file() and e.name in EXCLUDED_FILES)
        ]
    except PermissionError:
        return

    # Sort: directories first, then files
    entries.sort(key=lambda e: (e.is_file(), e.name.lower()))
    last_index = len(entries) - 1

    for index, entry in enumerate(entries):
        connector = "└── " if index == last_index else "├── "
        print(prefix + connector + entry.name)

        if entry.is_dir():
            child_prefix = prefix + ("    " if index == last_index else "│   ")
            print_tree(entry, child_prefix)

if __name__ == "__main__":
    # Get folder path from command-line argument
    if len(sys.argv) < 2:
        print("Usage: python tree.py /path/to/folder")
        sys.exit(1)

    root_path = Path(sys.argv[1]).resolve()

    if not root_path.exists():
        print(f"Error: path does not exist: {root_path}")
        sys.exit(1)

    print(root_path.name)
    print_tree(root_path)
