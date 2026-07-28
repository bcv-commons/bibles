#!/usr/bin/env python3
"""Generate a discovery report of potential text sources for audio-only languages.

Uses versions-data/{iso}/versions.json as the single source of truth.
Prioritizes eBible (new, actionable) over helloAO (already integrated).

Output: docs/source-discovery.md
"""

import json
from collections import defaultdict
from pathlib import Path

VERSIONS_DIR = Path("export/versions-data")
CROSSREF = Path("data/version-crossref.json")
OUTPUT = Path("docs/source-discovery.md")


def main():
    if not VERSIONS_DIR.is_dir():
        print("[ERROR] export/versions-data not found. Run generate_version_info.py first.")
        return

    xref = {}
    if CROSSREF.exists():
        with open(CROSSREF) as f:
            xref = json.load(f)

    # ISOs with any presence in export
    existing_isos = set()
    for canon_dir in Path("export/ALL-langs").iterdir():
        if not canon_dir.is_dir():
            continue
        for cat_dir in canon_dir.iterdir():
            if not cat_dir.is_dir():
                continue
            for iso_dir in cat_dir.iterdir():
                if iso_dir.is_dir():
                    existing_isos.add(iso_dir.name)

    # Scan versions.json and categorize
    # eBible categories (not covered by helloAO)
    eb_syncable = []       # same vid: dbt audio + ebible text (no helloao)
    eb_new_version = []    # ebible text for a vid without dbt audio
    eb_new_lang = []       # language has no prior export presence

    # helloAO categories (already integrated)
    hao_syncable = []
    hao_new_version = []
    hao_new_lang = []

    # DBS-only (no ebible/helloao)
    dbs_only = []

    # No source at all
    no_source_isos = set()

    # Track all audio-only (iso, vid, testament) for counting
    all_audio_only = []

    for iso_dir in sorted(VERSIONS_DIR.iterdir()):
        if not iso_dir.is_dir():
            continue
        iso = iso_dir.name
        versions = json.load(open(iso_dir / "versions.json"))
        iso_has_any_text = False

        for vid, entry in versions.items():
            title = entry.get("title", "")
            for testament in ("nt", "ot"):
                sources = entry.get(testament, {})
                if not sources:
                    continue

                dbt = sources.get("dbt", "")
                has_dbt_audio = "a" in dbt
                has_dbt_text = "t" in dbt
                has_ebible = sources.get("ebible") == "t"
                has_helloao = sources.get("helloao") == "t"
                has_contrib = bool(sources.get("contrib"))

                if has_ebible or has_helloao or has_dbt_text or has_contrib:
                    iso_has_any_text = True

                # Audio-only from DBT (no text from DBT)
                if has_dbt_audio and not has_dbt_text:
                    all_audio_only.append((iso, vid, testament))

                    # Same-version syncable: dbt audio + external text
                    if has_ebible and not has_helloao:
                        eb_syncable.append((iso, vid, testament, title))
                    elif has_helloao:
                        hao_syncable.append((iso, vid, testament, title))

                # Text-only version (no dbt audio for this vid)
                # Skip if same vid already has DBT text (helloAO/eBible is redundant)
                if not has_dbt_audio and not has_contrib and not has_dbt_text:
                    if has_ebible and not has_helloao:
                        if iso not in existing_isos:
                            eb_new_lang.append((iso, vid, testament, title))
                        else:
                            eb_new_version.append((iso, vid, testament, title))
                    elif has_helloao and not has_ebible:
                        if iso not in existing_isos:
                            hao_new_lang.append((iso, vid, testament, title))
                        else:
                            hao_new_version.append((iso, vid, testament, title))

        if not iso_has_any_text and iso in existing_isos:
            # Check DBS crossref for potential
            xref_langs = xref.get(iso, {})
            has_dbs = any(
                e.get("dbt") is False and not e.get("ebible") and not e.get("helloao")
                for e in xref_langs.values()
            )
            if has_dbs:
                dbs_only.append(iso)
            else:
                no_source_isos.add(iso)

    # Deduplicate by (iso, vid) — keep NT if both
    def dedup(entries):
        seen = set()
        result = []
        for iso, vid, testament, title in entries:
            key = (iso, vid)
            if key not in seen:
                seen.add(key)
                result.append((iso, vid, testament, title))
        return result

    eb_syncable = dedup(eb_syncable)
    eb_new_version = dedup(eb_new_version)
    eb_new_lang = dedup(eb_new_lang)
    hao_syncable = dedup(hao_syncable)
    hao_new_version = dedup(hao_new_version)
    hao_new_lang = dedup(hao_new_lang)

    # Find truly no-source ISOs: audio-only versions where no text exists anywhere
    ao_isos = set(iso for iso, _, _ in all_audio_only)
    text_isos = set()
    for iso_dir in VERSIONS_DIR.iterdir():
        if not iso_dir.is_dir():
            continue
        iso = iso_dir.name
        versions = json.load(open(iso_dir / "versions.json"))
        for vid, entry in versions.items():
            for t in ("nt", "ot"):
                sources = entry.get(t, {})
                if any(sources.get(s) == "t" for s in ("ebible", "helloao")) or "t" in sources.get("dbt", ""):
                    text_isos.add(iso)

    no_source_final = sorted((ao_isos - text_isos - set(dbs_only)) | no_source_isos)

    # Build report
    lines = []
    lines.append("# Text Source Discovery Report")
    lines.append("")
    ao_unique_isos = len(set(iso for iso, _, _ in all_audio_only))
    lines.append(f"**{ao_unique_isos}** languages have at least one audio-only version (DBT audio, no text).")
    lines.append("")

    # Summary table
    lines.append("| Source | Syncable | New version | New language | Status |")
    lines.append("|--------|----------|-------------|-------------|--------|")
    lines.append(f"| eBible.org | {len(eb_syncable)} | {len(eb_new_version)} | {len(eb_new_lang)} | Actionable — not yet in release |")
    lines.append(f"| helloAO | {len(hao_syncable)} | {len(hao_new_version)}* | {len(hao_new_lang)} | Already integrated in release |")
    lines.append(f"| DBS catalog | — | {len(dbs_only)} | — | Discoverable, needs API access |")
    lines.append(f"| No source | — | — | {len(no_source_final)} | Needs contributed text |")
    lines.append("")

    # Count partial helloAO translations (< 27 books, not in export)
    partial_hao = 0
    if Path("api-cache/helloao/available_translations.json").exists():
        with open("api-cache/helloao/available_translations.json") as f:
            hao_data = json.load(f)
        for t in hao_data.get("translations", []):
            if isinstance(t, dict):
                iso = t.get("language", "")
                n_books = t.get("numberOfBooks", 0)
                if iso and iso not in existing_isos and n_books < 27:
                    partial_hao += 1
    if partial_hao:
        lines.append(f"> **Note:** {partial_hao} additional languages exist in helloAO as partial translations (<27 books).")
        lines.append("> These are not included above since they lack a full NT, which is required for template coverage.")
        lines.append("")

    # ---- eBible section (top priority — actionable) ----
    eb_total = len(eb_syncable) + len(eb_new_version) + len(eb_new_lang)
    if eb_total:
        lines.append(f"## eBible.org — {eb_total} versions (not covered by helloAO)")
        lines.append("")
        lines.append("### Client access to eBible text")
        lines.append("")
        lines.append("| Method | URL pattern | Use case |")
        lines.append("|--------|-------------|----------|")
        lines.append("| HTML per chapter | `https://ebible.org/{tid}/{BOOK}{ch}.htm` | On-the-fly |")
        lines.append("| USFM zip | `https://ebible.org/Scriptures/{tid}_usfm.zip` | Bulk download |")
        lines.append("")
        lines.append("In `data.json`: `\"t\": \"ebible:{tid}\"`. The `{tid}` maps to the URL patterns above.")
        lines.append("")
        lines.append("> **Note:** Recommended client access pattern pending — contact eBible.org for guidance.")
        lines.append("")

    def write_group(title, entries, actionable=True):
        if not entries:
            return
        isos = sorted(set(iso for iso, _, _, _ in entries))
        lines.append(f"### {title} ({len(entries)} versions, {len(isos)} languages)")
        lines.append("")
        if actionable:
            lines.append("```bash")
            lines.append(f"make align ISO=\"{','.join(isos[:30])}\"")
            if len(isos) > 30:
                lines.append(f"# ... plus {len(isos) - 30} more")
            lines.append("```")
            lines.append("")
        for iso, vid, testament, title_str in entries:
            t_label = f"[{testament.upper()}]" if testament else ""
            title_part = f" — {title_str}" if title_str else ""
            lines.append(f"- {iso}/{vid} {t_label}{title_part}")
        lines.append("")

    if eb_syncable:
        write_group("Syncable — same version has DBT audio + eBible text", eb_syncable)
    if eb_new_version:
        write_group("New version — text added for existing language", eb_new_version, actionable=False)
    if eb_new_lang:
        write_group("New language — no previous Bible source", eb_new_lang, actionable=False)

    # ---- DBS section ----
    if dbs_only:
        lines.append(f"## DBS catalog — {len(dbs_only)} languages")
        lines.append("")
        lines.append("Text exists somewhere (bible.com, bible.is, etc.) but requires manual fetch or API access.")
        lines.append("See `data/version-crossref.json` for version details and source URLs.")
        lines.append("")
        sorted_dbs = sorted(dbs_only)
        for i in range(0, len(sorted_dbs), 20):
            chunk = sorted_dbs[i:i+20]
            lines.append("> " + " ".join(chunk) + "  ")
        lines.append("")

    # ---- No source ----
    lines.append(f"## No known text source — {len(no_source_final)} languages")
    lines.append("")
    lines.append("These need contributed text via `contrib/`. See [contrib/README.md](../contrib/README.md).")
    lines.append("")
    for i in range(0, len(no_source_final), 20):
        chunk = no_source_final[i:i+20]
        lines.append("> " + " ".join(chunk) + "  ")
    lines.append("")

    # ---- helloAO section (last — already integrated) ----
    hao_total = len(hao_syncable) + len(hao_new_version) + len(hao_new_lang)
    if hao_total:
        lines.append(f"## helloAO — {hao_total} versions (already integrated in release)")
        lines.append("")
        lines.append("These are already included in the released data. Listed for reference.")
        lines.append("")

        if hao_syncable:
            hao_sync_isos = sorted(set(iso for iso, _, _, _ in hao_syncable))
            lines.append(f"### Syncable ({len(hao_syncable)} versions, {len(hao_sync_isos)} languages)")
            lines.append("")
            for iso, vid, testament, title_str in hao_syncable:
                t_label = f"[{testament.upper()}]"
                title_part = f" — {title_str}" if title_str else ""
                lines.append(f"- {iso}/{vid} {t_label}{title_part}")
            lines.append("")

        if hao_new_version:
            # Split: truly new text (language had no DBT text) vs alternative translation
            hao_truly_new = []
            hao_alt_translation = []
            for iso, vid, testament, title_str in hao_new_version:
                # Check if this language already has DBT text for this testament
                vf = VERSIONS_DIR / iso / "versions.json"
                if vf.exists():
                    versions = json.load(open(vf))
                    lang_has_dbt_text = False
                    for v, e in versions.items():
                        if "t" in e.get(testament, {}).get("dbt", ""):
                            lang_has_dbt_text = True
                            break
                    if lang_has_dbt_text:
                        hao_alt_translation.append((iso, vid, testament, title_str))
                    else:
                        hao_truly_new.append((iso, vid, testament, title_str))
                else:
                    hao_truly_new.append((iso, vid, testament, title_str))

            hao_truly_new = dedup(hao_truly_new)
            hao_alt_translation = dedup(hao_alt_translation)

            if hao_truly_new:
                lines.append(f"### New text for languages without DBT text ({len(hao_truly_new)} versions)")
                lines.append("")
                lines.append(f"Text added to {len(set(iso for iso,_,_,_ in hao_truly_new))} languages that had no text before.")
                lines.append("")
            if hao_alt_translation:
                lines.append(f"### Alternative translations ({len(hao_alt_translation)} versions)")
                lines.append("")
                lines.append(f"Additional text versions for {len(set(iso for iso,_,_,_ in hao_alt_translation))} languages that already have DBT text.")
                lines.append("")
                lines.append("> **Note:** Many of these may be the same underlying translation under a different")
                lines.append("> publisher ID (e.g., WBT/TBL/SIM are often the same text from different organizations).")
                lines.append("> Deduplication would require comparing actual text content.")
                lines.append("")

        if hao_new_lang:
            lines.append(f"### New languages ({len(hao_new_lang)} versions)")
            lines.append("")

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[INFO] Written {OUTPUT}")
    print(f"  eBible: {len(eb_syncable)} syncable, {len(eb_new_version)} new version, {len(eb_new_lang)} new lang")
    print(f"  helloAO: {len(hao_syncable)} syncable, {len(hao_new_version)} new version, {len(hao_new_lang)} new lang")
    print(f"  DBS: {len(dbs_only)}")
    print(f"  No source: {len(no_source_final)}")

    # Generate cross-source review list
    _generate_cross_source_review(xref, existing_isos)


REVIEW_OUTPUT = Path("docs/cross-source-review.md")


def _generate_cross_source_review(xref, existing_isos):
    """Generate review list of potential cross-source pairings not yet confirmed."""
    from version_exclude import load_excludes, is_excluded

    excludes = load_excludes()
    sorted_dir = Path("sorted/BB")

    # For each language, find audio-only filesets that could pair with a text fileset
    # Only include if NOT already confirmed in crossref
    review_items = []  # (iso, audio_did, audio_name, text_did, text_name, testament)
    _review_seen = set()

    if not sorted_dir.is_dir():
        return

    for iso_dir in sorted(sorted_dir.iterdir()):
        if not iso_dir.is_dir():
            continue
        iso = iso_dir.name
        if iso not in existing_isos:
            continue

        # Collect all filesets for this language by bible.abbr
        audio_filesets = []  # (bible_abbr, fileset_id, name, canon)
        text_filesets = []   # (bible_abbr, fileset_id, name, canon)

        for fs_dir in iso_dir.iterdir():
            if not fs_dir.is_dir():
                continue
            md_path = fs_dir / "metadata.json"
            if not md_path.exists():
                continue
            try:
                md = json.load(open(md_path))
            except (json.JSONDecodeError, KeyError):
                continue

            bible_abbr = md.get("bible", {}).get("abbr", "")
            fs_id = md.get("fileset", {}).get("id", "")
            fs_type = md.get("fileset", {}).get("type", "")
            fs_size = md.get("fileset", {}).get("size", "")
            bible_name = md.get("bible", {}).get("name", "")

            canon = "nt" if fs_size in ("NT", "NTP") else "ot" if fs_size in ("OT", "OTP") else ""
            if not canon:
                # Complete Bible — applies to both
                canon = "both"

            if "audio" in fs_type:
                audio_filesets.append((bible_abbr, fs_id, bible_name, canon))
            elif "text" in fs_type:
                text_filesets.append((bible_abbr, fs_id, bible_name, canon))

        if not audio_filesets or not text_filesets:
            continue

        # For each audio fileset, check if it has matching text
        for a_abbr, a_fid, a_name, a_canon in audio_filesets:
            if is_excluded(excludes, iso, a_abbr):
                continue

            # Check if this audio has its own text (same bible.abbr)
            has_own_text = any(t_abbr == a_abbr for t_abbr, _, _, _ in text_filesets)
            if has_own_text:
                continue

            # Audio-only: check if crossref confirms a pairing
            lang_xref = xref.get(iso, {})
            dbt_to_dbs = {}
            for vid, info in lang_xref.items():
                dbt_val = info.get("dbt")
                if dbt_val and dbt_val is not True and dbt_val is not False:
                    dbt_to_dbs[dbt_val] = vid

            audio_dbs = dbt_to_dbs.get(a_abbr) or dbt_to_dbs.get(a_fid)
            already_confirmed = False

            for t_abbr, t_fid, t_name, t_canon in text_filesets:
                text_dbs = dbt_to_dbs.get(t_fid) or dbt_to_dbs.get(t_abbr)
                if audio_dbs and text_dbs:
                    if audio_dbs == text_dbs:
                        already_confirmed = True
                        break
                    # Check same_text
                    a_same = lang_xref.get(audio_dbs, {}).get("same_text")
                    t_same = lang_xref.get(text_dbs, {}).get("same_text")
                    if a_same == text_dbs or t_same == audio_dbs:
                        already_confirmed = True
                        break

            if already_confirmed:
                continue

            # Not confirmed — candidate for review
            # Only list if exactly one text option (rule B)
            # Dedup text filesets by bible.abbr
            unique_text = {}
            for t_abbr, t_fid, t_name, t_canon in text_filesets:
                if t_abbr not in unique_text:
                    unique_text[t_abbr] = (t_abbr, t_fid, t_name, t_canon)
            if len(unique_text) == 1:
                t_abbr, t_fid, t_name, t_canon = list(unique_text.values())[0]
                testaments = set()
                if a_canon in ("nt", "both") and t_canon in ("nt", "both"):
                    testaments.add("nt")
                if a_canon in ("ot", "both") and t_canon in ("ot", "both"):
                    testaments.add("ot")
                for t in testaments:
                    key = (iso, a_abbr, t_abbr, t)
                    if key not in _review_seen:
                        _review_seen.add(key)
                        review_items.append((iso, a_abbr, a_name, t_abbr, t_name, t))

    # Write review file
    rlines = []
    rlines.append("# Cross-Source Pairing Review")
    rlines.append("")
    rlines.append("Languages with **one audio-only version** and **one text-only version** from different translations.")
    rlines.append("These are NOT auto-merged. Review and confirm pairings before adding to `version-crossref.json`.")
    rlines.append("")
    rlines.append(f"**{len(review_items)} potential pairings** across {len(set(i[0] for i in review_items))} languages")
    rlines.append("")

    if review_items:
        rlines.append("| Language | Audio ID — Title | Text ID — Title | Testament |")
        rlines.append("|----------|-----------------|-----------------|-----------|")
        for iso, a_abbr, a_name, t_abbr, t_name, testament in sorted(review_items):
            a_title = f" — {a_name[:35]}" if a_name else ""
            t_title = f" — {t_name[:35]}" if t_name else ""
            rlines.append(f"| {iso} | {a_abbr}{a_title} | {t_abbr}{t_title} | {testament.upper()} |")
        rlines.append("")

    rlines.append("## How to confirm a pairing")
    rlines.append("")
    rlines.append("If the audio and text are the same translation (just from different publishers),")
    rlines.append("add a `same_text` entry to `data/version-crossref.json`:")
    rlines.append("")
    rlines.append("```json")
    rlines.append('{')
    rlines.append('  "ISO": {')
    rlines.append('    "DBS_ID": { "dbt": "AUDIO_FILESET", "same_text": "TEXT_DBS_ID" }')
    rlines.append('  }')
    rlines.append('}')
    rlines.append("```")
    rlines.append("")
    rlines.append("After confirmation, run `make align ISO=<iso>` to merge and align.")
    rlines.append("")

    REVIEW_OUTPUT.write_text("\n".join(rlines) + "\n", encoding="utf-8")
    print(f"[INFO] Written {REVIEW_OUTPUT}")
    print(f"  Cross-source review: {len(review_items)} potential pairings")


if __name__ == "__main__":
    main()
