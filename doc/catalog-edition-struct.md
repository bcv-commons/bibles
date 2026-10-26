# `edition-struct.json`

`https://cdn.bibel.wiki/catalog/edition-struct.json`

One record per edition, keyed by the source ids of
[`catalog-overlap.json`](catalog-overlap.md) and [`text-route.json`](catalog-text-route.md)
(`d:` DBT, `h:` helloAO, `p:` PKF, `o:` openbible / audiobiblia, `e:` eBible, `c:`
CrossWire, `g:` Door43). It holds what is true of an edition rather than of its language:
its name and licence, its textual basis, how it presents psalm titles, and its writing
system.

## Shape

```json
{"note": "…",
 "editions": {
  "d:AAAMLT": {"iso": "aaa", "provider": "DBT (4.dbt.io)", "name": "…", "license": "…",
               "textual_basis": "tr",
               "script": "Latn", "basis": "metadata", "direction": "ltr", "normalization": "NFC"},
  "h:cmn_cuv": {"iso": "cmn", "provider": "helloAO", "…": "…",
                "script": "Hani", "basis": "detected", "direction": "ltr", "spaces": false,
                "normalization": "NFC"},
  "d:EN1ESV":  {"…": "…", "script": "Latn", "basis": "detected", "stated_script": "Shaw",
                "direction": "ltr", "normalization": "NFC"}
 }}
```

## Writing system

Added 2026-10-26 (bcv-commons/bibles issue #2, for bsb-add-books and lexeme-aligner), so that
tools read an edition's script from here instead of each detecting it.

| field | value |
|---|---|
| `script` | ISO 15924 code: `Latn`, `Arab`, `Orya`, `Mymr`, `Jpan`, … |
| `scripts` | only for an edition whose text mixes scripts: every script with at least 1% of its letters, `script` first |
| `direction` | `ltr` / `rtl`, from `script` |
| `spaces` | `false` for a script written without spaces between words (Han, Japanese, Thai, Lao, Khmer, Myanmar, Tibetan, Tai Tham, Tai Le, Tai Viet, Balinese, Javanese); absent otherwise |
| `normalization` | `NFC` / `NFD` / `mixed`: the Unicode normalization of the edition's text as its source publishes it |
| `basis` | `metadata`: the source states this script and the text agrees (or we have no text). `detected`: the source states none, or states one the text contradicts |
| `stated_script`, `stated_direction` | what the source's metadata says, where the text contradicts it |

### How `script` is decided

The text decides. Each letter (Unicode category L) of the edition's text is given its script
(ICU); common and inherited letters such as ʼ and ꞌ don't count. Hiragana or Katakana make
`Jpan`, Hangul makes `Kore`, otherwise the script with the most letters wins. The source's
metadata then only refines it (`Hans` or `Hant` for Han, `Aran` for Arabic) or stands in where
we have no text.

Metadata doesn't go first because it is wrong too often. Examples found on 2026-10-26:

- DBT, 12 of the editions we read: its ESV is labelled Shavian, a Georgian New Testament
  Cyrillic, Kayah Li, Lisu and Cree Syllabics New Testaments Latin, and two Romani editions
  have Latin and Cyrillic swapped (`RMLNEW`, `RMLNVC`).
- openbible, 4: three Latin-script Zambian editions labelled Traditional Han (`BBT`, `NKN`,
  `SSTP`), and a Kannada-script Gawli Bible labelled Devanagari.
- eBible, 3 of ours (Chinese, Japanese and Serbian Cyrillic labelled Latin). Its
  `translations.csv` also labels eight right-to-left editions (Hebrew, Persian, Urdu, Yiddish
  and others) Latin, and gives four Arabic-labelled ones as left to right.
- helloAO states only a direction, never a script.

Where the text contradicts the metadata, `stated_script` keeps what the source said.

The metadata read: DBT `alphabet` (bible_details), openbible's project `script` and
`scriptDirection`, eBible's `translations.csv` (`script`, `textDirection`) and helloAO's
`textDirection`. Script names are mapped to codes.

The text read: DBT's samples of the fileset the text route names (one or more chapters per
edition; a version's other filesets can be in another script), helloAO's chapter JSON, the
PKF collection, and every book of the editions we republish. Script and normalization don't
need more than a chapter.

### Mixed scripts

`script` is the main script; `scripts` lists the others when they reach 1% of the letters.
Titles and headings are not verse text, so a Latin title over a text in another script
doesn't count. 14 editions have `scripts` (2026-10-26). Most of them are look-alike letters
typed from another script:

- Greek έ, ί for Latin é, í (`d:ABIWBT`, `d:NZACAB`);
- Cyrillic і for Latin i (`d:GAGIBT`);
- Latin ö for Cyrillic ӧ in Komi (`d:KPVIBT`);
- Latin capitals in Greek text (`d:ELLELL`);
- Cherokee Ꮊ in Ethiopic text (`o:GYLNTETH`, `h:gyl_twf`, `o:OYDANTE`).

A word containing such a letter doesn't match the same word spelled with the right one, so
a tool that compares words may want to know.

### Normalization

Measured on the same text. An edition is `NFC` if its text equals its NFC form, `NFD` if it
equals its NFD form, and `mixed` if it equals neither or its files differ. Text with no
decomposable character at all (most Latin-script text without accents) counts as `NFC`.

We don't normalize the text we republish: our USJ keeps the source's form (checked on every
openbible edition, 2026-10-26, against the source USFM). A tool that hands text back to a
team can therefore restore the team's form from this field. Tokenizer v2 applies NFC before
cutting words, so tokens and text fingerprints don't depend on it.

## The other fields

- `textual_basis`: from `pipeline/comparison/textual_basis.py`; not every edition has one.
- `psalm_titles`, `psalm_titles_basis`: from `psalm_titles.py`. `numbered` (the title is
  counted as a verse), `mixed` (numbered in one probe psalm, not the other), `heading` (a title
  marker before verse 1, not counted), `note` (the title is only a footnote), `unmarked` (no
  marker: inline in verse 1 or left out). The basis is `markup` or `verse-count` (DBT plain
  text has no heading markup, so it can only show numbered or unmarked).

Built by `make edition-struct`: `pipeline/comparison/edition_script.py` reads each edition's
text (resumable; `--force` reads everything again), then `edition_struct.py --scan` merges.
