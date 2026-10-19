"""
json_cache.py — file-based JSON storage.

All persistence goes through JSON files in the data/ directory.
This module provides a simple load/save API compatible with the old database-backed version.
"""
import copy
import json
import os
from typing import Any

from config import DATA_DIR


# Per-request memo for caching
_memo: dict[str, Any] = {}


def _get_filepath(filename: str) -> str:
    """Get the full path to a data file."""
    return os.path.join(DATA_DIR, filename)


def load_cached(filename: str) -> Any:
    """Return the data for ``filename`` (a fresh copy the caller may mutate)."""
    if filename in _memo:
        return copy.deepcopy(_memo[filename])

    filepath = _get_filepath(filename)
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError):
        # Return empty list for list-type files, empty dict for others
        if filename.endswith('.json'):
            data = [] if filename != 'compliance.json' else {}
        else:
            data = []

    _memo[filename] = data
    return copy.deepcopy(data)


def save_cached(filename: str, data: Any) -> None:
    """Write data to JSON file."""
    filepath = _get_filepath(filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except OSError as e:
        print(f'[json_cache] ERROR saving {filename}: {e}')
        raise

    _memo[filename] = data


def invalidate(filename: str | None = None) -> None:
    """Forget cached data (next load re-reads from disk)."""
    global _memo
    if filename is None:
        _memo.clear()
    else:
        _memo.pop(filename, None)


def invalidate_all() -> None:
    """Forget all cached data."""
    _memo.clear()