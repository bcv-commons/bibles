"""Shared loader for version-exclude.toml.

Usage:
    from version_exclude import load_excludes, is_excluded

    excludes = load_excludes()
    if is_excluded(excludes, "fra", "FRALSN", scope="align"):
        skip...
"""

import sys
import tomllib
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import VERSION_EXCLUDE_FILE  # noqa: E402

EXCLUDE_FILE = VERSION_EXCLUDE_FILE


def load_excludes() -> Dict[Tuple[str, str], dict]:
    """Load exclusion config. Returns {(iso, distinct_id): {reason, scope}}."""
    if not EXCLUDE_FILE.exists():
        return {}
    with open(EXCLUDE_FILE, "rb") as f:
        data = tomllib.load(f)

    excludes = {}
    for key, value in data.items():
        # Key format: "fra.FRALSN" → parsed by TOML as nested: data["fra"]["FRALSN"]
        if isinstance(value, dict):
            iso = key
            for did, entry in value.items():
                if isinstance(entry, dict):
                    excludes[(iso, did)] = {
                        "reason": entry.get("reason", ""),
                        "scope": entry.get("scope", "align"),
                    }
    return excludes


def is_excluded(
    excludes: Dict[Tuple[str, str], dict],
    iso: str,
    distinct_id: str,
    scope: str = "align",
) -> bool:
    """Check if a fileset is excluded for the given scope.

    scope="align" matches entries with scope "align" or "all"
    scope="all" only matches entries with scope "all"
    """
    entry = excludes.get((iso, distinct_id))
    if not entry:
        return False
    entry_scope = entry.get("scope", "align")
    if scope == "align":
        return entry_scope in ("align", "all")
    elif scope == "all":
        return entry_scope == "all"
    return False


def excluded_set(
    excludes: Dict[Tuple[str, str], dict],
    scope: str = "align",
) -> Set[Tuple[str, str]]:
    """Return set of (iso, distinct_id) tuples excluded for the given scope."""
    return {
        key for key, entry in excludes.items()
        if is_excluded(excludes, key[0], key[1], scope)
    }
