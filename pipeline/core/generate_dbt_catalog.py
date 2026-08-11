#!/usr/bin/env python3
"""Generate DBT's compact text/audio catalogs — the two-file replacement
for MONO's combined `_catalog.json` (see
internal-docs/catalog-audio-ownership-architecture.md §5 for the full
design discussion this implements).

Source: ONLY internal-data/api-cache/bibles/bibles_page_*.json (the raw
paginated DBT bible listing) — confirmed 2026-07-28 that every field this
script needs (iso, distinct_id/abbr, per-fileset id/type/size/bitrate/
codec/timing_est_err) is already flat in that raw data. Deliberately does
NOT read bible_details/ (per-bible detail calls — expensive, and only ever
feeds script/direction fields this catalog doesn't need) or the *derived*
internal-data/api-cache/samples/audio_timestamps_filesets.json (a local
summary of the same timing_est_err field this script now reads directly
from the raw pages — reading the raw field itself makes that derived
summary redundant, not a second source).

timing_est_err IS published (2026-08-11, as audio variant.dbtTiming) —
DBT's own catalog-level, unverified claim of per-fileset timing. This is
explicitly NOT the confirmed answer to "does this have real, working
timing" — that stronger question is still only answered by
generate_audio_metadata.py's media.json (timingBooks), sourced from real
alignment work. Publishing DBT's own claim alongside the confirmed one
(clearly named, never conflated — see doc/catalog-audio.md) was judged
worth doing once a client asked whether this signal was available at all;
before that it was withheld specifically to avoid the two being confused
for each other in a file with no field distinguishing them.

Two separate output files, not MONO's combined `a:`/`A:`/`t:`/`T:` row
encoding — single-purpose files, matching this project's established
pattern (catalog-index.json / catalog-overlap.json are also each
single-purpose). No eBible/helloAO naming-convention fallback either
(MONO's `_find_helloao_id`/`_get_external_text_source`) — discarded as a
guess this project's "verified only, never inferred" principle (see
doc/catalog-overlap.md) doesn't allow.

Shape (both files): entries["<iso>:<canon>"]["<distinct_id>"] = [variant, ...]
  Audio variant: {"id": "<encoded>", "br": <int, kbps>, "c": "<codec>",
                   "dbtTiming": "<raw timing_est_err value>"}
    "br"/"c" omitted when the source data has them empty (confirmed
    real: ~10% of audio filesets have blank bitrate/codec). "dbtTiming"
    omitted when DBT's catalog has no timing_est_err for this fileset
    (the common case — see doc/catalog-audio.md for what the real
    observed values mean, and the explicit warning that this is DBT's
    own unverified claim, not media.json's confirmed timingBooks).
  Text variant:  {"id": "<encoded>", "fmt": ["pl"|"u"|"j"|"f", ...]}
    fmt <- text_plain/text_usx/text_json/text_format, first-letter-ish
    codes chosen 2026-07-28 to avoid "p" colliding with the "p:"
    PKF-source-prefix convention used elsewhere in this id space.
    ALWAYS a list, even for a single format — confirmed real (2026-07-28,
    all 63 raw pages): 197 cases exist where DBT lists the exact same
    fileset id under two different `type`s (always the same combination,
    text_format + text_plain) — consolidated here into one variant with
    both format codes, rather than two separate variants sharing an id
    (which would make "id" silently non-unique within the list — a real
    trap for any client keying by id alone). Kept as a list unconditionally
    rather than sometimes-string/sometimes-list, matching catalog-overlap.json's
    "ids" field always being a list — one type to handle, never a surprise.
    Audio does NOT get the same treatment: a same-id/different-br-or-codec
    collision on the audio side would be a genuine anomaly (different
    actual encoded files), not the same "identical resource under two
    catalog type tags" pattern text has — flagged as a warning if it ever
    occurs, never silently merged.
  "id" encoding: same a:/A: (audio) or t:/T: (text) convention as MONO's
  original — lowercase means "append to distinct_id to reconstruct",
  uppercase means "this is the literal full id, use verbatim" (real,
  confirmed case — fileset ids don't always share distinct_id's prefix).
  canon is "nt"/"ot", with a trailing "p" (-> "ntp"/"otp") when the
  fileset's own `size` code doesn't certify whole-testament coverage —
  same Portions/uncertain convention as catalog-index.json.

NOT YET VALIDATED AT FULL SCALE / NOT YET PUBLISHED — see
internal-docs/catalog-audio-ownership-architecture.md §5's own caution
(quoting MONO's review): the compact-encoding scheme deserves the same
multiple rounds of real verification MONO's own version got before it's
trustworthy. This run is exactly that verification pass, not a publish.

Usage:
    python3 generate_dbt_catalog.py [--text-out PATH] [--audio-out PATH]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, CATALOG_DIR  # noqa: E402

BIBLES_DIR = API_CACHE / "bibles"
TEXT_OUT = CATALOG_DIR / "text.json"
AUDIO_OUT = CATALOG_DIR / "audio.json"

AUDIO_TYPES = {"audio", "audio_drama", "audio_stream", "audio_drama_stream"}
FMT_CODE = {"text_plain": "pl", "text_usx": "u", "text_json": "j", "text_format": "f"}

# Per-fileset `size` code -> certainty of whole-testament coverage per canon.
# True = certain (whole-testament), False = uncertain (Portions — the book
# being present is DBT's optimistic claim, not confirmed), None = this
# fileset doesn't apply to that canon at all. Derived directly from the
# real size-code vocabulary found in the raw catalog (2026-07-28 survey:
# NT, NTP, OT, OTP, NTPOTP, C, S, NTOTP, OTNTP, P) — a superset of what
# MONO's own generate_catalog_export.py's CERTAIN_SIZE_CODES covered (that
# dict never accounted for NTPOTP or the generic P/S codes at all).
SIZE_CANON = {
    "C": {"nt": True, "ot": True},
    "NT": {"nt": True, "ot": None},
    "OT": {"nt": None, "ot": True},
    "NTP": {"nt": False, "ot": None},
    "OTP": {"nt": None, "ot": False},
    "NTOTP": {"nt": True, "ot": False},
    "OTNTP": {"nt": False, "ot": True},
    "NTPOTP": {"nt": False, "ot": False},
    "S": {"nt": None, "ot": None},  # Story selections — not real testament coverage
    "P": {"nt": False, "ot": False},  # generic Partial, testament unspecified — optimistic both
}


def canon_certainty(size_code: str) -> dict:
    return SIZE_CANON.get(size_code, {"nt": False, "ot": False})  # unknown code: never assume certainty


def encode_id(distinct_id: str, fileset_id: str) -> tuple[str, bool]:
    """(value, is_suffix). is_suffix=True -> lowercase tag, reconstruct as
    distinct_id + value. False -> uppercase tag, value is the literal id."""
    if fileset_id.upper().startswith(distinct_id.upper()):
        return fileset_id[len(distinct_id):], True
    return fileset_id, False


def parse_bitrate(raw: str) -> int | None:
    if not raw or not raw.endswith("kbps"):
        return None
    try:
        return int(raw[:-4])
    except ValueError:
        return None


def load_raw_entries() -> list:
    entries = []
    for p in sorted(BIBLES_DIR.glob("bibles_page_*.json")):
        data = json.loads(p.read_text())
        entries.extend(data.get("data", []))
    return entries


def main():
    args = sys.argv[1:]
    text_out = Path(args[args.index("--text-out") + 1]) if "--text-out" in args else TEXT_OUT
    audio_out = Path(args[args.index("--audio-out") + 1]) if "--audio-out" in args else AUDIO_OUT

    entries = load_raw_entries()
    print(f"[dbt-catalog] {len(entries)} raw bible entries loaded from {BIBLES_DIR}")

    # text_entries[key][distinct_id] = {encoded_id: {fmt_code, ...}} — grouped
    # by id FIRST so the same id under multiple `type`s (confirmed real, see
    # module docstring) merges into one variant instead of silently
    # duplicating the id across separate variant objects.
    text_entries: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    # audio_entries[key][distinct_id] = {encoded_id: (br, c) -> variant dict}
    # — audio does NOT merge; a same-id collision here is a genuine anomaly
    # (different actual encoded files), tracked separately to warn on, never
    # silently combined.
    audio_entries: dict = defaultdict(lambda: defaultdict(dict))
    audio_id_collisions = []
    skipped_unknown_size = set()

    for entry in entries:
        iso = entry.get("iso", "")
        distinct_id = entry.get("abbr", "")
        if not iso or not distinct_id:
            continue

        for filesets in entry.get("filesets", {}).values():
            for fs in filesets:
                fileset_id = fs.get("id", "")
                fs_type = fs.get("type", "")
                size = fs.get("size", "")
                if not fileset_id or not fs_type:
                    continue
                if size not in SIZE_CANON:
                    skipped_unknown_size.add(size)

                certainty = canon_certainty(size)
                is_text = fs_type.startswith("text")
                is_audio = fs_type in AUDIO_TYPES
                if not is_text and not is_audio:
                    continue

                for canon in ("nt", "ot"):
                    certain = certainty.get(canon)
                    if certain is None:
                        continue
                    canon_key = canon if certain else f"{canon}p"
                    value, is_suffix = encode_id(distinct_id, fileset_id)

                    if is_text:
                        fmt = FMT_CODE.get(fs_type)
                        if not fmt:
                            continue
                        tag = "t" if is_suffix else "T"
                        encoded_id = f"{tag}:{value}"
                        text_entries[f"{iso}:{canon_key}"][distinct_id][encoded_id].add(fmt)
                    else:
                        tag = "a" if is_suffix else "A"
                        encoded_id = f"{tag}:{value}"
                        br = parse_bitrate(fs.get("bitrate", ""))
                        codec = (fs.get("codec") or "").lower()
                        dbt_timing = fs.get("timing_est_err") or None
                        key = f"{iso}:{canon_key}"
                        existing = audio_entries[key][distinct_id].get(encoded_id)
                        if existing is not None and (
                            (existing.get("br"), existing.get("c"), existing.get("dbtTiming"))
                            != (br, codec or None, dbt_timing)
                        ):
                            audio_id_collisions.append((key, distinct_id, encoded_id))
                        variant = {"id": encoded_id}
                        if br is not None:
                            variant["br"] = br
                        if codec:
                            variant["c"] = codec
                        if dbt_timing is not None:
                            variant["dbtTiming"] = dbt_timing
                        audio_entries[key][distinct_id][encoded_id] = variant

    if skipped_unknown_size:
        print(f"[dbt-catalog] WARNING: unknown size codes encountered (treated as uncertain-both): "
              f"{sorted(skipped_unknown_size)}")
    if audio_id_collisions:
        print(f"[dbt-catalog] WARNING: {len(audio_id_collisions)} audio id(s) seen with differing "
              f"br/codec across raw entries (NOT merged - see log): {audio_id_collisions[:10]}")

    def finalize_text(grouped: dict) -> dict:
        out = {}
        for key in sorted(grouped):
            out[key] = {
                did: sorted(
                    ({"id": eid, "fmt": sorted(fmts)} for eid, fmts in id_map.items()),
                    key=lambda v: v["id"],
                )
                for did, id_map in sorted(grouped[key].items())
            }
        return out

    def finalize_audio(grouped: dict) -> dict:
        out = {}
        for key in sorted(grouped):
            out[key] = {
                did: sorted(id_map.values(), key=lambda v: v["id"])
                for did, id_map in sorted(grouped[key].items())
            }
        return out

    text_output = {"entries": finalize_text(text_entries)}
    audio_output = {"entries": finalize_audio(audio_entries)}

    for out_path, output, label in ((text_out, text_output, "text"), (audio_out, audio_output, "audio")):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        n_groups = len(output["entries"])
        n_versions = sum(len(v) for v in output["entries"].values())
        n_variants = sum(len(vs) for v in output["entries"].values() for vs in v.values())
        print(f"[dbt-catalog] {label}: {n_groups} (iso,canon) groups, {n_versions} versions, "
              f"{n_variants} variants -> {out_path}")


if __name__ == "__main__":
    main()
