# `openbible-abbr.json`

`https://cdn.bibel.wiki/catalog/openbible-abbr.json`

Our abbreviation for every Biblica (openbible) project, and the Biblica project id behind it.
Every catalog file names openbible editions `o:<abbreviation>`, never by Biblica's hex project
id; this table is the bridge for anyone who needs the id (Biblica's own API,
`openbible-api-1.biblica.com/projects/{id}`).

```json
{
  "schema_version": 1,
  "source": "https://openbible-api-1.biblica.com/projects",
  "entries": {
    "TAWobNT": {"id": "61f979a5c26fb60d495dfa37", "iso": "taw", "type": "text",
                "scope": "New Testament", "title": "Jisas Klays Takaw Teplep Ne"},
    "PBV-POY": {"id": "68deba2941a2a80e0f09bd24", "iso": "poy", "type": "text",
                "scope": "Bible", "title": "Pogoro Bible Version"}
  }
}
```

All enabled Biblica projects are listed (942 on 2026-10-28): text, audio and video.

## How an abbreviation is chosen

1. **yaapi.bible's**, where yaapi.bible carries the project (307): `YALUNKA`, `LBV`,
   `PBV-POY`. These are the ids `overlap.json`, `text-route.json` and `edition-struct.json`
   have always used.
2. **Ours** for the rest (635): `<ISO>ob<ID>`, the language code in capitals, `ob`, and a code
   for Biblica's scope and type: `TAWobNT` (Tay, text, New Testament), `ENGobNTA` (English,
   audio, NT), `WOLobSA` (Wolof, audio, Selections), `TURobBIB` (Turkish, text, whole Bible).
   The lower-case `ob` marks the ones we made: yaapi.bible's abbreviations are all capitals, so
   ours can't collide with one, now or later. (Every source has its own prefix, `o:`, `d:`,
   `h:`, so ids of different sources can't collide anyway.)
3. Where that's taken, a number is appended: `KFFobNTA`, `KFFobNTA2`.

| scope | code | | type | code |
|---|---|---|---|---|
| Bible | `BIB` | | text | (none) |
| Bible with Deuterocanon | `DC` | | audio | `A` |
| New Testament | `NT` | | video | `V` |
| New Testament+ (with OT portions) | `NTP` | | | |
| Old Testament | `OT` | | | |
| Portions | `P` | | | |
| Selections | `S` | | | |

**An abbreviation never changes once given**, and is never reused. The table lives in
[`data/openbible-abbr.toml`](../data/openbible-abbr.toml): the rule at the top can be edited,
and so can any single abbreviation below it; `make openbible-abbr` adds new Biblica projects
and keeps everything already there.

Built by `make openbible-abbr` (also run by `make catalog-books`).
