#!/usr/bin/env python3
"""Shared fetch layer for the unified comparison pipeline (compare_all.py,
pipeline/research/diagnose_all.py). Replaces the fetch logic that used to
be duplicated across five separate leg scripts (batch_compare_pkf_dbt.py,
batch_compare_helloao_dbt.py, batch_compare_pkf_helloao.py,
batch_compare_dbt_dbt.py, batch_compare_helloao_helloao.py).

The single biggest inefficiency the old five-script design had: PKF
fetch+decode (the heaviest step — network transfer + a Proskomma decode
subprocess) happened TWICE per language (once each in the pkf-dbt and
pkf-helloao legs), and helloAO chapter fetches happened up to THREE times
per translation (helloao-dbt, pkf-helloao, helloao-helloao each did their
own live HTTP GET). compare_all.py calls each of these functions AT MOST
ONCE per (iso, canon, id) and reuses the result for every pairwise
comparison that id is involved in.

DBT: local sample cache first (data/text/BB/{nt,ot}/<iso>/<distinct_id>/),
falling back to a live API call via download_language_content.get_text_content()
for any (iso, distinct_id) not yet locally sampled. The old
batch_compare_helloao_dbt.py/batch_compare_pkf_dbt.py legs already used
this cache-first order; batch_compare_dbt_dbt.py was the one inconsistent
leg (always live-fetched, even for already-sampled ids) — a real,
previously-undiagnosed inefficiency this consolidation also fixes.

helloAO: always a live HTTP GET (bible.helloao.org, unauthenticated, no
documented rate limit — still paced with a short sleep per call).

PKF: rclone fetch + tools/pkf-decode/decode.mjs, the same mechanism every
prior PKF-touching script used. No PKF text is ever retained to disk beyond
the lifetime of one language's processing — callers are responsible for
deleting the tmpdir contents immediately after use, preserving the
license-driven verdict-only discipline established from the start of the
PKF/DBT pilot (PKF is NC-ND licensed; only comparison verdicts are ever
published, never the text itself).
"""
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import download_language_content as dl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_pkf_dbt import normalize_chars, extract_pkf_chapter  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import TEXT_DIR  # noqa: E402

SAMPLE_DIR = TEXT_DIR / "BB"
HELLOAO_API = "https://bible.helloao.org/api"


def dbt_text(iso: str, canon: str, distinct_id: str, fileset_id: str, book: str, chapter: int) -> str | None:
    """Local sample cache first, live DBT API fallback. canon is the plain
    "nt"/"ot" directory name (not the ntp/otp catalog tag)."""
    base = SAMPLE_DIR / canon / iso / distinct_id
    probe = f"{book}_{chapter:03d}_"
    local_files = list(base.rglob(f"{probe}*.txt")) if base.is_dir() else []
    if local_files:
        return "".join(normalize_chars(f.read_text(encoding="utf-8")) for f in local_files) or None

    result = dl.get_text_content(fileset_id, book, chapter)
    time.sleep(0.1)
    if not result or result.get("type") != "verses":
        return None
    text = " ".join(item.get("verse_text", "") for item in result["data"])
    return normalize_chars(text) or None


def extract_helloao_chapter(chapter_json: dict) -> str:
    parts = []
    for block in chapter_json.get("content", []):
        if block.get("type") != "verse":
            continue
        for item in block.get("content", []):
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
    return normalize_chars(" ".join(parts))


def helloao_text(translation_id: str, book: str, chapter: int) -> str | None:
    try:
        r = requests.get(f"{HELLOAO_API}/{translation_id}/{book}/{chapter}.json", timeout=15)
    except requests.RequestException:
        return None
    time.sleep(0.1)
    if r.status_code != 200:
        return None
    try:
        payload = r.json()
    except ValueError:
        return None
    return extract_helloao_chapter(payload.get("chapter", {})) or None


def pkf_text(iso: str, pkf_file: str, book: str, chapter: int, env: dict, bucket: str, tmpdir: Path) -> str | None:
    safe_tag = pkf_file.replace("/", "_")
    pkf_path = tmpdir / f"{iso}_{safe_tag}.pkf"
    result = subprocess.run(
        ["rclone", "copyto", f"R2:{bucket}/pkf/{iso}/{pkf_file}", str(pkf_path)],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0 or not pkf_path.exists():
        return None
    out_dir = tmpdir / f"{iso}_{safe_tag}_out"
    subprocess.run(
        ["node", "tools/pkf-decode/decode.mjs", str(pkf_path), "--out", str(out_dir), "--book", book],
        capture_output=True, text=True,
    )
    matches = list(out_dir.glob(f"*-{book}.usfm")) if out_dir.is_dir() else []
    return extract_pkf_chapter(matches[0], chapter) if matches else None


def rclone_env():
    """Same R2/Cloudflare credential resolution as every other script that
    talks to R2 (scripts/publish-dbt.sh, pull_align_cache.py, the old
    batch_compare_pkf_*.py scripts)."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    access = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("CLOUDFLARE_ACCESS_KEY_ID", "")
    secret = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY", "")
    account = os.getenv("R2_ACCOUNT_ID") or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    bucket = os.getenv("R2_BUCKET") or os.getenv("CLOUDFLARE_BUCKET", "")
    env = os.environ.copy()
    env.update({
        "RCLONE_CONFIG_R2_TYPE": "s3",
        "RCLONE_CONFIG_R2_PROVIDER": "Cloudflare",
        "RCLONE_CONFIG_R2_ACCESS_KEY_ID": access,
        "RCLONE_CONFIG_R2_SECRET_ACCESS_KEY": secret,
        "RCLONE_CONFIG_R2_ENDPOINT": f"https://{account}.r2.cloudflarestorage.com",
        "RCLONE_CONFIG_R2_ACL": "private",
        "RCLONE_CONFIG_R2_NO_CHECK_BUCKET": "true",
    })
    return env, bucket
