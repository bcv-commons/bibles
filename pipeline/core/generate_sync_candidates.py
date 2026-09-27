#!/usr/bin/env python3
"""Generate /dbt/_app/sync-candidates.json — actionable alignment worklist
for audio-sync.

Every entry here is a real DBT edition with genuine, paired audio AND text
but no confirmed per-verse timing anywhere yet (not DBT's own declared
timing, not bibles' own owned sources, not audio-sync's real work) — i.e.
exactly the population generate_audio_metadata.py classifies "syncable"
and, by design, excludes from media.json's filesets[] (that exclusion is
itself a useful signal to other clients: "audio+text both exist, but not
ready to consume as synced playback yet"). This file is the other half —
the positive, actionable input FOR audio-sync to pick its next batches
from, using the same field names as align/_runs/<batch_id>.json's own
manifest schema (iso, canon, distinct_id, audio_fileset — snake_case,
confirmed 2026-09-14 to be their real convention) so no translation layer
is needed on their side.

Nothing needs to change here or in generate_audio_metadata.py when
audio-sync actually processes a candidate: once they publish it (a
manifest result with status "ok"), the next run of
pull_align_manifests.py folds it into the local digest, and that
edition's real audio automatically satisfies timing_index.resolved_of()
and graduates out of "syncable" into "with-timecode"/"audio-with-timecode"
— and out of this candidate list — on its own.

Output: export/dbt/_app/sync-candidates.json, shape:
    {"candidates": [
        {"iso": "eng", "canon": "nt", "distinct_id": "ENGBER",
         "audio_fileset": "ENGBERN1DA", "text_fileset": "ENGBERN_ET"},
        ...
    ]}

Usage:
    python3 pipeline/core/generate_sync_candidates.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timing_index import load_resolved, resolved_of  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import EXPORT, SORTED_DIR  # noqa: E402

OUTPUT_DIR = EXPORT / "dbt"

# Prefer a plain-text fileset over usx/json when both exist for the same
# edition — matches get_text_content()'s own resolution preference
# elsewhere in this repo (plain text is directly usable; usx/json need
# extra parsing audio-sync would rather not redo per candidate).
TEXT_TYPE_PRIORITY = {"text_plain": 0, "text_format": 1, "text_json": 2, "text_usx": 3}


def _normalize_fileset_id(fileset_id):
    """Strip encoding-variant suffixes (e.g. "-opus16") to get the base
    fileset id — same stripping sort_cache_data.py's normalize_fileset_id()
    does (duplicated here for the same reason _best_audio_variant() is: no
    standalone equivalent to import). Needed here specifically because
    resolved_of() does an exact-string match — without this, an encoding
    variant of an ALREADY-timed recording (e.g. FRNTLSN2DA-opus16, a
    different literal fileset id from the FRNTLSN2DA that's actually in
    align-index.json) would wrongly look untimed and get proposed as a
    "new" candidate for content that's really already aligned (found
    2026-09-19 investigating the fra/JHN report, once the edition-level
    skip that had been masking it was fixed)."""
    for suffix in ["-opus16", "-opus32", "-mp3", "-64", "-128", "16"]:
        if fileset_id.endswith(suffix):
            return fileset_id[: -len(suffix)]
    return fileset_id


# Real priority order for audio fileset variants of the same edition, per
# audio-sync's own stated policy (2026-09-17): prefer downloadable over
# streaming, and within each format prefer standard over dramatized — but
# streaming IS an acceptable last resort when no downloadable variant
# exists at all, in either generation. See _best_audio_variant()'s
# docstring for the two real corrections that got this here.
_AUDIO_VARIANT_TIER = {
    ("1", "DA"): 0,  # standard, downloadable
    ("2", "DA"): 1,  # dramatized, downloadable
    ("1", "SA"): 2,  # standard, streaming
    ("2", "SA"): 3,  # dramatized, streaming
}


def _select_candidates(untimed_ids, already_timed_ids):
    """Among audio fileset ids for the SAME base edition/generation
    family, propose only the best (lowest-tier) UNTIMED variant — and
    only if no ALREADY-TIMED sibling in that same base group is already
    equal-or-better. See _AUDIO_VARIANT_TIER for the tier order.

    History (real, from external catches, not our own testing):
    1. Originally assumed "DA"/"SA" (fileset id's last 2 chars) meant
       dramatized/standard. WRONG — caught by audio-sync checking DBT's
       own `type` field directly (queried DBT's real API for ACNBSM,
       AIAWBT, AKABSG, BFABSS, FRNTLS to confirm). "DA"/"SA" is a
       downloadable/streaming FORMAT distinction; the real dramatized
       marker is the digit at position -3 (1=standard, 2=dramatized).
    2. Fixed to exclude streaming entirely from candidacy. Also not quite
       right — audio-sync's actual policy treats streaming as an
       acceptable LAST RESORT when no downloadable variant exists at all,
       not something to exclude outright.
    3. Fixed to include streaming as a last resort, but only checked "is
       this the best tier AMONG UNTIMED ids" — never checked whether an
       ALREADY-TIMED sibling in the SAME base group was already as good
       or better. Real, confirmed bug (audio-sync checked all 69
       streaming candidates from that pass directly against DBT: 65/69
       were exactly this — e.g. kum/KUMIBTN2SA proposed as streaming
       "last resort" while kum/KUMIBTN2DA, a real downloadable recording
       of the same edition, was sitting right there already aligned).
       Fixed: now takes BOTH untimed and already-timed ids together, so
       a worse-tier untimed variant is never proposed when a
       same-or-better-tier sibling is already done.

    Duplicated from sort_cache_data.py's select_best_audio_variant() (an
    instance method, no standalone equivalent to import) — kept in sync
    by cross-reference."""
    def _tier(fs_id):
        return _AUDIO_VARIANT_TIER.get((fs_id[-3], fs_id[-2:])) if len(fs_id) >= 3 else None

    base_groups = defaultdict(lambda: {"untimed": [], "timed": []})
    for fs_id in untimed_ids:
        base_groups[fs_id[:-3] if len(fs_id) >= 3 else fs_id]["untimed"].append(fs_id)
    for fs_id in already_timed_ids:
        base_groups[fs_id[:-3] if len(fs_id) >= 3 else fs_id]["timed"].append(fs_id)

    kept = []
    for base, group in base_groups.items():
        untimed_ranked = [(t, fs) for fs in group["untimed"] for t in [_tier(fs)] if t is not None]
        untimed_unranked = [fs for fs in group["untimed"] if _tier(fs) is None]
        timed_tiers = [t for fs in group["timed"] for t in [_tier(fs)] if t is not None]
        best_timed = min(timed_tiers, default=None)

        if not untimed_ranked:
            # Nothing recognized among untimed ids for this base — keep
            # as-is (don't guess), UNLESS something already-timed exists
            # here at all (in which case an unranked id is more likely a
            # stray/malformed variant than a genuine gap).
            if not group["timed"]:
                kept.extend(untimed_unranked)
            continue

        best_untimed = min(t for t, _ in untimed_ranked)
        if best_timed is not None and best_timed <= best_untimed:
            continue  # already-timed sibling is as good or better — nothing to propose
        kept.extend(fs for t, fs in untimed_ranked if t == best_untimed)
    return kept


def main():
    if not SORTED_DIR.is_dir():
        print(f"[generate-sync-candidates] {SORTED_DIR} not found. Run: make sort-dbt-catalog")
        return

    resolved = load_resolved()

    # (iso, abbr, canon) -> {"audio": {fileset_id: type}, "text": {fileset_id: type}}
    grouped: dict[tuple, dict] = defaultdict(lambda: {"audio": {}, "text": {}})

    for iso_dir in sorted(p for p in SORTED_DIR.iterdir() if p.is_dir()):
        iso = iso_dir.name
        for fileset_dir in sorted(p for p in iso_dir.iterdir() if p.is_dir()):
            meta_path = fileset_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue

            abbr = meta.get("bible", {}).get("abbr", "")
            if not abbr:
                continue
            canon_raw = meta.get("canon", "")
            fs = meta.get("fileset", {})
            fs_id = fs.get("id", "")
            fs_type = fs.get("type", "")
            fs_size = fs.get("size", "")

            canons = set()
            if canon_raw == "NT":
                canons.add("nt")
            elif canon_raw == "OT":
                canons.add("ot")
            elif canon_raw == "FULL":
                canons.update({"nt", "ot"})
            elif canon_raw == "PARTIAL":
                # FIXED 2026-09-17 (real, confirmed bug — caught by
                # audio-sync directly checking DBT's real per-fileset book
                # coverage): a PARTIAL-canon fileset's metadata.json
                # `books` field is NOT that fileset's own real book
                # coverage — sort_cache_data.py's create_metadata() only
                # filters `books` by testament for canon "NT"/"OT", so a
                # PARTIAL fileset gets the WHOLE BIBLE's book list
                # (spanning both testaments) unfiltered. The old fallback
                # here inferred canon membership from that unfiltered list
                # and so treated e.g. BAMLSBP1DA (a real OT-Portions-only
                # product, DBT's own `size: "OTP"`) as if it covered NT
                # too — a totally unrelated recording got proposed as an
                # "NT sync candidate", confirmed directly against DBT's
                # real per-fileset book/chapter list (all 5 "priority fix"
                # candidates from the previous worklist turned out to be
                # this exact bug). Use DBT's own `fileset.size` instead —
                # a direct, reliable per-FILESET signal (unlike `books`),
                # confirmed values: C/NTOTP=both, NT/NTP=nt-only,
                # OT/OTP=ot-only.
                if fs_size in ("C", "NTOTP"):
                    canons.update({"nt", "ot"})
                elif fs_size in ("NT", "NTP"):
                    canons.add("nt")
                elif fs_size in ("OT", "OTP"):
                    canons.add("ot")
                # An unrecognized/blank size on a PARTIAL fileset is
                # skipped entirely (canons stays empty) rather than
                # guessed at — matches this file's existing philosophy of
                # not proposing a candidate without real evidence it
                # covers the canon in question.

            # Streaming ("audio_stream"/"audio_drama_stream") is included
            # here deliberately — _best_audio_variant() below is what
            # enforces "prefer downloadable, streaming only as a last
            # resort" (see its docstring for the real policy history).
            is_audio = fs_type in ("audio", "audio_drama", "audio_stream", "audio_drama_stream")
            is_text = fs_type.startswith("text")

            for canon in canons:
                key = (iso, abbr, canon)
                if is_audio and fs_id:
                    grouped[key]["audio"][fs_id] = fs_type
                if is_text and fs_id:
                    grouped[key]["text"][fs_id] = fs_type

    candidates = []
    # Edition already has a real alignment done, but a STRICTLY BETTER
    # tier (per _AUDIO_VARIANT_TIER) exists untimed — the genuine "wrong
    # one got aligned first" case worth flagging as a priority fix
    # (renamed twice from earlier, narrower/wrong versions of this same
    # idea — first "sa_priority_fixes" [wrong DA/SA premise], then
    # "non_dramatized_priority_fixes" [only handled the dramatized-vs-
    # standard axis, not the full downloadable-vs-streaming one too]).
    better_variant_priority_fixes = []
    for (iso, abbr, canon), info in sorted(grouped.items()):
        if not info["audio"] or not info["text"]:
            continue

        # FIXED 2026-09-19 (real, confirmed bug — found investigating a
        # real client report for fra/JHN): this used to skip the entire
        # edition once ANY of its audio filesets had confirmed timing —
        # so once FRNTLSN2DA got aligned, its untimed FRNTLSN2SA sibling
        # never got proposed as a candidate at all, forever. Now checks
        # PER FILESET: an edition can have some variants already timed
        # and others still needing it (exactly the DA-timed/SA-untimed
        # case this was built to prevent going forward).
        # Dedupe encoding variants (e.g. FRNTLSN2DA / FRNTLSN2DA-opus16) to
        # one representative real id per normalized base — prefer the
        # shortest (no-suffix, canonical) form when more than one variant
        # is present.
        by_normalized: dict[str, str] = {}
        for fs_id in info["audio"]:
            norm = _normalize_fileset_id(fs_id)
            if norm not in by_normalized or len(fs_id) < len(by_normalized[norm]):
                by_normalized[norm] = fs_id

        already_timed_norm = resolved_of(resolved, iso, by_normalized.keys())
        untimed_real_ids = [real for norm, real in by_normalized.items() if norm not in already_timed_norm]
        if not untimed_real_ids:
            continue  # every audio variant already has confirmed timing

        already_timed_real = {by_normalized[n] for n in already_timed_norm if n in by_normalized}
        filtered_audio = _select_candidates(sorted(untimed_real_ids), sorted(already_timed_real))
        if not filtered_audio:
            continue  # every base group here already has an equal-or-better already-timed sibling

        best_text = min(info["text"], key=lambda fid: TEXT_TYPE_PRIORITY.get(info["text"][fid], 99))
        for audio_fs in filtered_audio:
            candidates.append({
                "iso": iso,
                "canon": canon,
                "distinct_id": abbr,
                "audio_fileset": audio_fs,
                "text_fileset": best_text,
            })
            # A genuine priority fix: this candidate's own base group has
            # an already-timed sibling too (just a worse tier — otherwise
            # _select_candidates() would have dropped this candidate
            # entirely) — e.g. the dramatized recording got aligned
            # first, but the standard one exists and was never touched.
            base = audio_fs[:-3] if len(audio_fs) >= 3 else audio_fs
            if any((fs[:-3] if len(fs) >= 3 else fs) == base for fs in already_timed_real):
                better_variant_priority_fixes.append(
                    {"iso": iso, "canon": canon, "distinct_id": abbr, "audio_fileset": audio_fs})

    if better_variant_priority_fixes:
        # Deliberately NOT under export/ — this is a local-only worklist
        # for coordinating with audio-sync directly (e.g. attaching to a
        # message), not part of the published sync-candidates.json schema
        # (see this file's own docstring on why that schema is kept
        # minimal and matched to their manifest format exactly).
        priority_path = SORTED_DIR.parent / "sync-candidates-better-variant-priority.json"
        priority_path.write_text(
            json.dumps({"candidates": better_variant_priority_fixes}, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[generate-sync-candidates] {len(better_variant_priority_fixes)} better-variant-priority-fix "
              f"candidates (edition already has a real alignment at a worse tier) -> {priority_path} (local only, not published)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app_dir = OUTPUT_DIR / "_app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "sync-candidates.json").write_text(
        json.dumps({"candidates": candidates}, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[generate-sync-candidates] {len(candidates)} candidates "
          f"({len({(c['iso'], c['canon'], c['distinct_id']) for c in candidates})} editions) "
          f"-> {app_dir / 'sync-candidates.json'}")


if __name__ == "__main__":
    main()
