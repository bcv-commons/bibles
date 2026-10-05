# dbt-sofria-decode-py

Reference decoder for DBT's `text_json` fileset shape — a real, separate
format from PKF's `.pkf` succinct docSet, despite sharing the same
underlying Proskomma "Sofria" document family. See
[`doc/sources.md`](../../doc/sources.md) for how this fileset shape
surfaces in the real DBT API, and why it's easy to mistake for plain
text (a real client crash, caught 2026-10-02, traced to exactly this).

## What this handles

A DBT text fileset's response is one of two real shapes:

- `{"type": "verses", "data": [...]}` — inline per-verse text, the
  common case, not this tool's concern.
- `{"type": "path", "data": <signed CDN URL>}` — the downloaded document
  at that URL is a raw, uncompressed Proskomma Sofria JSON document
  (`schema.constraints[].name == "sofria"`). **This** is what this tool
  decodes.

## Usage

```
python3 decode.py <sofria.json>
```

Prints `{chapter: {verse: text}}` as JSON. Or import directly:

```python
from decode import extract_verses_from_sofria
chapters = extract_verses_from_sofria(json.load(open("sofria.json")))
```

## Scope

Deliberately minimal, same spirit as [`tools/pkf-decode/`](../pkf-decode/):
walks `sequence.blocks`, skips `"graft"` sub-sequences entirely
(footnotes, headings, cross-references — real content, just not verse
text), tracks verse boundaries via `verses_label` marks, collects plain
text. **Not** a full Sofria renderer — no tables, no milestones, no
`meta_content`, no real HTML/USFM rendering. For that, the authoritative
reference is `proskomma-json-tools`'s
[`SofriaRenderFromJson.js`](https://github.com/Proskomma/proskomma-json-tools/blob/main/src/render/renderers/SofriaRenderFromJson.js).

Verified against real content: `ADXNVSO_ET-json` (Tibetan), Psalm 119 —
all 176 verses extracted correctly, matching an independent extraction
built separately by a real client (audio-sync) against the same file.
