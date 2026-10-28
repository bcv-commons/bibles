#!/usr/bin/env python3
"""Our abbreviation for every Biblica (openbible) project, so no published file needs Biblica's
hex project ids: data/openbible-abbr.toml (tracked, editable) -> catalog/openbible-abbr.json.

data/openbible-abbr.toml has two parts:
  - above the marker line, the rule (edited by hand): the pattern for a new project's
    abbreviation and the codes for Biblica's `scope` and `type`;
  - below it, [abbr]: one line per Biblica project, `"<project id>" = "<ABBR>"`, written by this
    script. A value edited there is kept: this script only adds projects it hasn't seen, and
    never changes or reuses an abbreviation once given (clients key on them).

A new project gets, in this order:
  1. its yaapi.bible abbreviation, where yaapi.bible carries the project
     (internal-data/openbible-editions.json, generate_openbible_abbr.py): the id already used as
     o:<abbr> in catalog/overlap.json and text-route.json;
  2. otherwise the rule's pattern, "{ISO}ob{SCOPE}{TYPE}": TAWobNT (text NT), TAWobNTA
     (audio). The lower-case "ob" marks the ones we made, and keeps them apart from
     yaapi.bible's (all capitals), now and later;
  3. if that is taken, the same with 2, 3, ... appended.
New projects are taken oldest first (originalArchiveDate, then id), so numbering is stable.

Output: export/catalog/openbible-abbr.json, enabled projects only:
    {"schema_version": 1, "generated_at": null, "source": "<Biblica projects URL>",
     "entries": {"<ABBR>": {"id": "<project id>", "iso": "...", "type": "text|audio|video",
                            "scope": "...", "title": "..."}}}

Usage: python3 pipeline/core/generate_openbible_abbr_table.py [--check]
  --check: report what would be added, write nothing.
"""
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR, DATA, OPENBIBLE_EDITIONS_FILE  # noqa: E402

TABLE = DATA / "openbible-abbr.toml"
PROJECTS = API_CACHE / "openbible" / "projects.json"
OUT = CATALOG_DIR / "openbible-abbr.json"
SOURCE_URL = "https://openbible-api-1.biblica.com/projects"
MARKER = "# ---- generated below by generate_openbible_abbr_table.py"
ABBR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,23}$")   # yaapi: PBV-POY; ours: TAWobNT


def toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def main():
    check = "--check" in sys.argv
    text = TABLE.read_text(encoding="utf-8")
    if MARKER not in text:
        sys.exit(f"[openbible-abbr] {TABLE}: marker line missing ({MARKER!r})")
    header = text[:text.index(MARKER)]
    config = tomllib.loads(text)
    rule = config["rule"]
    table: dict = dict(config.get("abbr", {}))

    bad = [f"{pid} = {a!r}" for pid, a in table.items() if not ABBR_RE.match(a)]
    taken: dict = {}
    for pid, abbr in table.items():
        if abbr in taken:
            bad.append(f"{abbr!r} used twice: {taken[abbr]}, {pid}")
        taken[abbr] = pid
    if bad:
        sys.exit("[openbible-abbr] fix data/openbible-abbr.toml:\n  " + "\n  ".join(bad))

    projects = {p["id"]: p for p in json.loads(PROJECTS.read_text())}
    yaapi = json.loads(OPENBIBLE_EDITIONS_FILE.read_text())["entries"] if OPENBIBLE_EDITIONS_FILE.exists() else {}

    def derived(p: dict) -> str:
        scope = rule["scope"].get(p.get("scope") or "", rule["scope_other"])
        kind = rule["type"].get(p.get("type") or "", "")
        return rule["pattern"].format(ISO=(p.get("languageCode") or "XXX").upper(),
                                      SCOPE=scope.upper(), TYPE=kind.upper())

    added = []
    new = sorted((p for pid, p in projects.items() if pid not in table),
                 key=lambda p: (p.get("originalArchiveDate") or "", p["id"]))
    for p in new:
        base = yaapi.get(p["id"], {}).get("abbr") or derived(p)
        base = re.sub(r"[^A-Za-z0-9-]", "", base)
        abbr, n = base, 2
        while abbr in taken:
            abbr, n = f"{base}{n}", n + 1
        table[p["id"]] = abbr
        taken[abbr] = p["id"]
        added.append((abbr, p))

    mismatch = [(pid, table[pid], e["abbr"]) for pid, e in yaapi.items()
                if e.get("abbr") and pid in table and table[pid] != e["abbr"]]
    for pid, ours, theirs in mismatch:
        print(f"[openbible-abbr] WARNING {pid}: table has {ours}, openbible-editions.json {theirs} "
              f"(catalog/overlap.json uses the latter)", file=sys.stderr)

    print(f"[openbible-abbr] {len(table)} projects in the table, {len(added)} new"
          + (f": {', '.join(a for a, _ in added[:12])}{' ...' if len(added) > 12 else ''}" if added else ""))
    if check:
        return

    lines = [header.rstrip("\n"), "", MARKER + "; values may be edited, see the top of this file ----",
             "", "[abbr]"]
    for pid, abbr in sorted(table.items(), key=lambda kv: (projects.get(kv[0], {}).get("languageCode") or "~", kv[1])):
        p = projects.get(pid)
        note = (f"{p.get('languageCode')} {p.get('type')} {p.get('scope') or '-'}: {p.get('title') or ''}"
                + (" (disabled)" if p.get("disabled") else "")) if p else "(no longer listed by Biblica)"
        note = note.replace("\n", " ")
        lines.append(f"{toml_str(pid)} = {toml_str(abbr)}  # {note}")
    TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    entries = {}
    for pid, abbr in sorted(table.items(), key=lambda kv: kv[1]):
        p = projects.get(pid)
        if not p or p.get("disabled"):
            continue
        entries[abbr] = {"id": pid, "iso": p.get("languageCode"), "type": p.get("type"),
                         "scope": p.get("scope"), "title": p.get("title")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema_version": 1, "generated_at": None, "source": SOURCE_URL,
                               "entries": entries}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"[openbible-abbr] {len(entries)} enabled projects -> {OUT}")


def abbr_by_project() -> dict:
    """{Biblica project id: our abbreviation}, for other generators (catalog books)."""
    return dict(tomllib.loads(TABLE.read_text(encoding="utf-8")).get("abbr", {}))


if __name__ == "__main__":
    main()
