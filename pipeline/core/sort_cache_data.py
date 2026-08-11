#!/usr/bin/env python3
"""
Sort and organize API cache data into a downloads-like directory structure.

This script computes all categorization logic directly from
internal-data/api-cache/ (see pipeline/paths.py's API_CACHE).

Key features:
- Single script execution: internal-data/api-cache/ -> internal-data/sorted/BB/
- Computes syncable pairs on-the-fly
- Filters dramatized versions automatically
- Determines book sets from fileset structure
- Matches audio to text by prefix
- Identifies timing availability
- Creates comprehensive metadata for each fileset

Usage:
    python sort_cache_data.py

Output:
    internal-data/sorted/BB/{iso}/{fileset_id}/metadata.json — read directly
    by generate_audio_metadata.py's count_audio_books() and
    generate_version_info.py's get_sorted_meta(), both of which import
    SORTED_DIR from pipeline/paths.py the same way this script does.

Requirements:
    - internal-data/api-cache/bibles/bibles_page_*.json (Bible catalog) —
      run fetch_api_cache.py first if missing or stale.
    - internal-data/api-cache/samples/audio_timestamps_filesets.json
      (Timing data list) — also produced by fetch_api_cache.py.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import API_CACHE, SORTED_DIR  # noqa: E402


# Helper functions for simplification
def _safe_get_list(data_dict: dict, key: str) -> list:
    """Safely get a list from dict, returning empty list if not found or wrong type."""
    result = data_dict.get(key)
    return result if isinstance(result, list) else []


def _safe_append_if_not_exists(lst: list, item) -> None:
    """Append item to list if it doesn't already exist."""
    if item not in lst:
        lst.append(item)


def _is_audio_type(fileset_type: str) -> bool:
    """Check if fileset type is audio."""
    return fileset_type in [
        "audio",
        "audio_stream",
        "audio_drama",
        "audio_drama_stream",
    ]


def _is_text_type(fileset_type: str) -> bool:
    """Check if fileset type is text."""
    return fileset_type.startswith("text")


class IndependentCacheDataSorter:
    """Sort cache data independently - no stats/ dependencies."""

    def __init__(self, cache_dir: Path = API_CACHE, output_dir: Path = SORTED_DIR):
        self.cache_dir = Path(cache_dir)
        self.bibles_dir = self.cache_dir / "bibles"
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Data structures
        self.all_bibles = []
        self.timing_filesets = set()
        self.timing_bibles_metadata = {}  # Map bible abbr to extended metadata
        self.bible_details_metadata = {}  # Map bible abbr to {direction, script}

        # Language data organized by ISO
        self.language_data = defaultdict(
            lambda: {
                "language_info": None,
                "audio_filesets": [],
                "text_filesets": [],
                "audio_details": [],
                "text_details": [],
            }
        )

        self.processed_filesets = set()

        # Exclusion tracking
        self.exclusions = {
            "sa_versions": [],  # Streaming-only Story Adaptations (SA suffix)
            "partial_content": [],  # Partial OT/NT (OTP, NTP, etc.)
            "story_adaptations": [],  # True story adaptations from video filesets
        }

    def load_timing_filesets(self):
        """Load the list of filesets that have timing data."""
        timing_file = self.cache_dir / "samples" / "audio_timestamps_filesets.json"
        if not timing_file.exists():
            print(f"Warning: {timing_file} not found")
            return

        with open(timing_file) as f:
            data = json.load(f)
            for item in data:
                self.timing_filesets.add(item["fileset_id"])

        print(f"Loaded {len(self.timing_filesets)} filesets with timing data")

    def load_timing_bibles_metadata(self):
        """
        Load extended metadata from timing_bibles API endpoint.

        Note: These fields (mark, country, description, vdescription) are Bible-level
        metadata, NOT timing-specific. They're only available in the timing_bibles
        API endpoint currently, but organize_language_data() also checks the regular
        API for future-proofing.
        """
        timing_bibles_dir = self.bibles_dir / "timing_bibles"
        if not timing_bibles_dir.exists():
            print(
                "Note: No timing_bibles directory found - extended metadata will only come from regular API"
            )
            return

        timing_bible_files = list(timing_bibles_dir.glob("*.json"))

        for timing_file in timing_bible_files:
            try:
                with open(timing_file) as f:
                    data = json.load(f)
                    bible_data = data.get("data", {})

                    abbr = bible_data.get("abbr")
                    if not abbr:
                        continue

                    # Extract extended metadata fields
                    extended_meta = {}
                    if bible_data.get("mark"):
                        extended_meta["mark"] = bible_data["mark"]
                    if bible_data.get("country"):
                        extended_meta["country"] = bible_data["country"]
                    if bible_data.get("description"):
                        extended_meta["description"] = bible_data["description"]
                    if bible_data.get("vdescription"):
                        extended_meta["vdescription"] = bible_data["vdescription"]

                    if extended_meta:
                        self.timing_bibles_metadata[abbr] = extended_meta
            except Exception as e:
                print(f"Warning: Could not load timing bible {timing_file.name}: {e}")
                continue

        if self.timing_bibles_metadata:
            print(
                f"Loaded extended metadata from timing_bibles endpoint for {len(self.timing_bibles_metadata)} bibles"
            )

    def load_bible_details_metadata(self):
        """
        Load alphabet/direction metadata from bible detail API responses.

        Reads from api-cache/bibles/bible_details/{ABBR}.json, extracting:
        - alphabet.direction (ltr/rtl)
        - alphabet.script (e.g., Arab, Latn, Hebr)

        Also extracts extended metadata (mark, country, description, vdescription)
        and merges into timing_bibles_metadata for backward compatibility.
        """
        bible_details_dir = self.bibles_dir / "bible_details"
        if not bible_details_dir.exists():
            print(
                "Note: No bible_details directory found - direction data will not be available"
            )
            return

        detail_files = list(bible_details_dir.glob("*.json"))
        direction_count = 0
        extended_count = 0

        for detail_file in detail_files:
            try:
                with open(detail_file) as f:
                    data = json.load(f)
                    bible_data = data.get("data", {})

                    abbr = bible_data.get("abbr")
                    if not abbr:
                        continue

                    # Extract alphabet/direction info
                    alphabet = bible_data.get("alphabet")
                    if alphabet and isinstance(alphabet, dict):
                        direction = alphabet.get("direction")
                        script = alphabet.get("script")
                        if direction:
                            self.bible_details_metadata[abbr] = {
                                "direction": direction,
                                "script": script or "",
                            }
                            direction_count += 1

                    # Also extract extended metadata (mark, country, etc.)
                    # and merge into timing_bibles_metadata
                    extended_meta = {}
                    if bible_data.get("mark"):
                        extended_meta["mark"] = bible_data["mark"]
                    if bible_data.get("country"):
                        extended_meta["country"] = bible_data["country"]
                    if bible_data.get("description"):
                        extended_meta["description"] = bible_data["description"]
                    if bible_data.get("vdescription"):
                        extended_meta["vdescription"] = bible_data["vdescription"]

                    if extended_meta:
                        if abbr not in self.timing_bibles_metadata:
                            self.timing_bibles_metadata[abbr] = extended_meta
                        else:
                            for key, value in extended_meta.items():
                                if key not in self.timing_bibles_metadata[abbr]:
                                    self.timing_bibles_metadata[abbr][key] = value
                        extended_count += 1

            except Exception as e:
                print(f"Warning: Could not load bible detail {detail_file.name}: {e}")
                continue

        if direction_count:
            print(
                f"Loaded direction data for {direction_count} bibles from bible_details"
            )
        if extended_count:
            print(
                f"Loaded extended metadata for {extended_count} bibles from bible_details"
            )

    def resolve_language_script_info(self, iso: str) -> dict:
        """
        Collect all unique scripts and directions for a language ISO code.

        Returns dict with:
          - "directions": list of unique directions, most common first
          - "scripts": list of unique script codes, most common first
          - "is_multi_script": True if more than one script found
          - "is_multi_direction": True if more than one direction found
        """
        from collections import Counter

        if not self.bible_details_metadata:
            return {
                "directions": [],
                "scripts": [],
                "is_multi_script": False,
                "is_multi_direction": False,
            }

        directions = []
        scripts = []
        for bible in self.all_bibles:
            if bible.get("iso") != iso:
                continue
            abbr = bible.get("abbr", "")
            detail = self.bible_details_metadata.get(abbr)
            if detail:
                if detail.get("direction"):
                    directions.append(detail["direction"])
                if detail.get("script"):
                    scripts.append(detail["script"])

        # Order by frequency (most common first)
        unique_dirs = [d for d, _ in Counter(directions).most_common()]
        unique_scripts = [s for s, _ in Counter(scripts).most_common()]

        return {
            "directions": unique_dirs,
            "scripts": unique_scripts,
            "is_multi_script": len(unique_scripts) > 1,
            "is_multi_direction": len(unique_dirs) > 1,
        }

    def load_all_bibles(self):
        """Load all Bible data from paginated cache files."""
        bible_files = sorted(self.bibles_dir.glob("bibles_page_*.json"))

        if not bible_files:
            print(f"Error: No Bible files found in {self.bibles_dir}")
            sys.exit(1)

        for bible_file in bible_files:
            with open(bible_file) as f:
                data = json.load(f)
                self.all_bibles.extend(data["data"])

        print(f"Loaded {len(self.all_bibles)} Bibles from {len(bible_files)} files")

    def normalize_fileset_id(self, fileset_id: str) -> str:
        """Remove suffixes like -opus16 to get base fileset ID."""
        for suffix in ["-opus16", "-opus32", "-mp3", "-64", "-128", "16"]:
            if fileset_id.endswith(suffix):
                return fileset_id[: -len(suffix)]
        return fileset_id

    def normalize_bible_abbr(self, abbr: str) -> str:
        """
        Normalize bible abbreviation to 6 letters.

        The 7th character (if present) indicates canon: N=NT, O=OT, C=FULL
        We strip it since we have a separate canon field.

        Examples:
            INDALA -> INDALA (already 6 letters)
            INDALAO -> INDALA (strip O)
            INDALAN -> INDALA (strip N)
        """
        if len(abbr) > 6:
            # Strip the 7th character (canon indicator)
            return abbr[:6]
        return abbr

    def filter_dramatized_versions(self, filesets: list[str]) -> list[str]:
        """
        Filter out dramatized versions when non-dramatized version exists.

        Dramatized check: Position -3 (third from end) == '2'
        Non-dramatized: Position -3 == '1'

        Example:
            If both ENGWEBN1DA and ENGWEBN2DA exist, keep only ENGWEBN1DA

        Args:
            filesets: List of fileset IDs

        Returns:
            Filtered list with dramatized versions removed where non-dramatized exists
        """
        # Group by base pattern (all except position -3)
        base_groups = defaultdict(list)

        for fs_id in filesets:
            if len(fs_id) >= 3:
                # Create base key: everything except position -3
                base = fs_id[:-3] + fs_id[-2:]
                base_groups[base].append(fs_id)

        filtered = []
        for base, fs_list in base_groups.items():
            # Check for version 1 and version 2
            has_version_1 = any(len(fs) >= 3 and fs[-3] == "1" for fs in fs_list)
            version_2_ids = [fs for fs in fs_list if len(fs) >= 3 and fs[-3] == "2"]

            if has_version_1 and version_2_ids:
                # Keep only non-dramatized (version 1)
                filtered.extend([fs for fs in fs_list if fs not in version_2_ids])
            else:
                # Keep all
                filtered.extend(fs_list)

        return filtered

    def match_audio_to_text(
        self, audio_fileset_id: str, text_filesets: list[str]
    ) -> list[str]:
        """
        Find text filesets that match an audio fileset by prefix comparison.

        Matching logic:
        - Compare first 7 characters of audio ID with text ID
        - If text ID is shorter than 7, use text ID length for comparison

        Examples:
            ENGWEBN1DA matches ENGWEB (first 6 chars)
            ENGWEBN1DA matches ENGWEBN_ET (first 7 chars)

        Args:
            audio_fileset_id: Audio fileset ID to match
            text_filesets: List of text fileset IDs to search

        Returns:
            List of matching text fileset IDs
        """
        if len(audio_fileset_id) < 6:
            return []

        matches = []
        for text_id in text_filesets:
            # Use minimum of 7 or text ID length
            compare_length = min(7, len(text_id))

            if len(audio_fileset_id) >= compare_length:
                if audio_fileset_id[:compare_length] == text_id[:compare_length]:
                    matches.append(text_id)

        return sorted(matches)

    def determine_book_set(self, fileset_id: str, size: str) -> str:
        """
        Determine book set from fileset structure and size field.

        Fileset ID structure (position 6, 0-indexed):
        - O = Old Testament
        - N = New Testament
        - C = Complete Bible
        - P = Partial
        - S = Story

        Size field values:
        - C, NTOTP = Complete Bible
        - NT, NTP = New Testament
        - OT, OTP = Old Testament

        Args:
            fileset_id: Fileset identifier
            size: Size field from fileset

        Returns:
            Book set category: FULL, OT, NT, PARTIAL, STORY, or VARIOUS
        """
        book_set = None

        # Check fileset ID structure (position 6)
        if len(fileset_id) >= 7:
            collection = fileset_id[6]
            if collection == "O":
                book_set = "OT"
            elif collection == "N":
                book_set = "NT"
            elif collection == "C":
                book_set = "FULL"
            elif collection == "P":
                book_set = "PARTIAL"
            elif collection == "S":
                book_set = "STORY"

        # Validate/enhance with size field, but respect PARTIAL collections
        # Don't override PARTIAL with OT/NT based on size alone
        if book_set == "PARTIAL":
            # Keep as PARTIAL - these are incomplete book sets
            pass
        elif size in ["C", "NTOTP"]:
            book_set = "FULL"
        elif size in ["NT", "NTP"]:
            if book_set not in ["OT", "FULL"]:
                book_set = "NT"
        elif size in ["OT", "OTP"]:
            if book_set not in ["NT", "FULL"]:
                book_set = "OT"

        return book_set or "VARIOUS"

    def organize_language_data(self):
        """
        Organize all bibles by language ISO code.
        Categorize filesets as audio or text.
        Store details for later analysis.
        """
        for bible in self.all_bibles:
            iso = bible.get("iso")
            if not iso:
                continue

            language_id = bible.get("language_id")
            language_name = bible.get("language")
            autonym = bible.get("autonym")

            # Store language info (first occurrence)
            if self.language_data[iso]["language_info"] is None:
                language_rolv_code = bible.get("language_rolv_code")
                lang_info = {
                    "iso": iso,
                    "language_id": language_id,
                    "name": language_name,
                    "autonym": autonym or "",
                }
                # Add language_rolv_code if available
                if language_rolv_code:
                    lang_info["language_rolv_code"] = language_rolv_code
                # Add script and direction info
                script_info = self.resolve_language_script_info(iso)
                if script_info["directions"]:
                    if script_info["is_multi_direction"]:
                        lang_info["direction"] = script_info["directions"]
                    elif script_info["directions"][0] == "rtl":
                        lang_info["direction"] = "rtl"
                if script_info["scripts"]:
                    if script_info["is_multi_script"]:
                        lang_info["script"] = script_info["scripts"]
                    else:
                        lang_info["script"] = script_info["scripts"][0]
                self.language_data[iso]["language_info"] = lang_info  # type: ignore[index]

            # Also capture extended metadata if available in regular API (future-proof)
            bible_abbr = bible.get("abbr")
            if bible_abbr:
                # Normalize to 6 letters for metadata storage
                normalized_abbr = self.normalize_bible_abbr(bible_abbr)

                extended_meta = {}
                if bible.get("mark"):
                    extended_meta["mark"] = bible["mark"]
                if bible.get("country"):
                    extended_meta["country"] = bible["country"]
                if bible.get("description"):
                    extended_meta["description"] = bible["description"]
                if bible.get("vdescription"):
                    extended_meta["vdescription"] = bible["vdescription"]

                # Store or merge with existing timing_bibles_metadata
                if extended_meta:
                    if normalized_abbr not in self.timing_bibles_metadata:
                        self.timing_bibles_metadata[normalized_abbr] = extended_meta
                    else:
                        # Merge - prefer timing_bibles data if it exists
                        for key, value in extended_meta.items():
                            if key not in self.timing_bibles_metadata[normalized_abbr]:
                                self.timing_bibles_metadata[normalized_abbr][key] = (
                                    value
                                )

            # Process filesets
            filesets = bible.get("filesets", {})
            for storage_key, fileset_list in filesets.items():
                for fileset in fileset_list:
                    fileset_id = fileset.get("id")
                    fileset_type = fileset.get("type", "")
                    size = fileset.get("size", "")

                    if not fileset_id:
                        continue

                    # Categorize and store
                    canon = self.determine_book_set(fileset_id, size)

                    # Normalize bible abbreviation to 6 letters
                    normalized_bible = bible.copy()
                    if "abbr" in normalized_bible:
                        normalized_bible["abbr"] = self.normalize_bible_abbr(
                            normalized_bible["abbr"]
                        )

                    fileset_detail = {
                        "fileset": fileset,
                        "bible": normalized_bible,
                        "canon": canon,
                        "original_canon": canon,  # Track original before expansion
                    }

                    if _is_audio_type(fileset_type):
                        audio_filesets = _safe_get_list(
                            self.language_data[iso], "audio_filesets"
                        )
                        audio_details = _safe_get_list(
                            self.language_data[iso], "audio_details"
                        )
                        if fileset_id not in audio_filesets:
                            audio_filesets.append(fileset_id)
                            audio_details.append(fileset_detail)
                    elif _is_text_type(fileset_type):
                        text_filesets = _safe_get_list(
                            self.language_data[iso], "text_filesets"
                        )
                        text_details = _safe_get_list(
                            self.language_data[iso], "text_details"
                        )
                        if fileset_id not in text_filesets:
                            text_filesets.append(fileset_id)
                            # Expand FULL text to both NT and OT
                            if canon == "FULL":
                                for expanded_canon in ["NT", "OT"]:
                                    expanded_detail = fileset_detail.copy()
                                    expanded_detail["canon"] = expanded_canon
                                    # Keep original_canon as FULL
                                    text_details.append(expanded_detail)
                            else:
                                text_details.append(fileset_detail)

        print(f"Organized data for {len(self.language_data)} languages")

        # Report extended metadata captured from regular API
        regular_api_extended = sum(
            1
            for abbr, meta in self.timing_bibles_metadata.items()
            if any(
                k in meta for k in ["mark", "country", "description", "vdescription"]
            )
        )
        if regular_api_extended > 0:
            print(
                f"  + Extended metadata captured from regular API for {regular_api_extended} additional bibles"
            )

    def compute_syncable_pairs(self, iso: str) -> list[dict]:
        """
        Compute which audio-text pairs are syncable for a language.

        A pair is syncable when:
        1. Audio does NOT have timing data already
        2. Audio matches text by prefix
        3. After filtering dramatized versions

        Args:
            iso: Language ISO code

        Returns:
            List of dictionaries with audio_fileset_id and text_fileset_id
        """
        lang_data = self.language_data[iso]
        audio_filesets = lang_data.get("audio_filesets", [])
        text_filesets: list[str] = lang_data.get("text_filesets") or []

        # Filter out audio that already has timing
        audio_without_timing = [
            fs
            for fs in (audio_filesets or [])
            if self.normalize_fileset_id(fs) not in self.timing_filesets
        ]

        # Filter dramatized versions
        audio_filtered = self.filter_dramatized_versions(audio_without_timing)

        # Match to text
        syncable_pairs = []
        for audio_id in audio_filtered:
            matching_text = self.match_audio_to_text(audio_id, text_filesets)
            if matching_text:
                syncable_pairs.append(
                    {
                        "audio_fileset_id": audio_id,
                        "text_fileset_id": matching_text,
                    }
                )

        return syncable_pairs

    def determine_data_source(
        self, fileset_id: str, is_audio: bool, syncable_pairs: list[dict]
    ) -> Optional[str]:
        """
        Determine data source category for a fileset.

        Categories:
        - "timing": Audio has timing data
        - "sync": Audio can be synced with text (no timing yet)
        - None: Not categorized

        Args:
            fileset_id: Fileset identifier
            is_audio: Whether this is an audio fileset
            syncable_pairs: List of syncable pairs for this language

        Returns:
            Data source string or None
        """
        if not is_audio:
            # Check if this text is part of a syncable pair
            for pair in syncable_pairs:
                if fileset_id in pair["text_fileset_id"]:
                    return "sync"
            return None

        # Check timing availability
        normalized = self.normalize_fileset_id(fileset_id)
        if normalized in self.timing_filesets:
            return "timing"

        # Check if syncable
        for pair in syncable_pairs:
            if pair["audio_fileset_id"] == fileset_id:
                return "sync"

        return None

    def is_syncable(self, fileset_id: str, syncable_pairs: list[dict]) -> bool:
        """
        Check if this audio fileset is part of a syncable pair.

        Args:
            fileset_id: Audio fileset identifier
            syncable_pairs: List of syncable pairs

        Returns:
            True if syncable, False otherwise
        """
        for pair in syncable_pairs:
            if pair["audio_fileset_id"] == fileset_id:
                return True
        return False

    def determine_category(
        self, iso: str, distinct_id: str, canon: str
    ) -> Optional[str]:
        """
        Determine category for a distinct_id/canon combination.

        Categories (in priority order):
        - partial: PARTIAL canon (highest priority, overrides all else)
        - with-timecode: Has text, audio, AND timing
        - audio-with-timecode: Has audio + timing (no text)
        - syncable: Has both text and audio, but NO timing
        - text-only: Has ONLY text
        - audio-only: Has ONLY audio

        Args:
            iso: Language code
            distinct_id: Bible abbreviation (e.g., ENGWEB, LEZIBT)
            canon: Canon (NT, OT, PARTIAL)

        Returns:
            Category string, or None if no valid category
        """
        lang_data = self.language_data.get(iso)
        if not lang_data:
            return None

        # FIRST PRIORITY: Check if canon is PARTIAL
        # PARTIAL overrides all other categorization logic
        if canon == "PARTIAL":
            return "partial"

        # Collect audio and text filesets for this distinct_id/canon
        audio_filesets = []
        text_filesets = []
        has_timing = False

        # Collect audio filesets
        for audio_detail in lang_data.get("audio_details") or []:
            bible_abbr = audio_detail.get("bible", {}).get("abbr", "")
            detail_canon = audio_detail.get("canon", "")
            fileset_id = audio_detail.get("fileset", {}).get("id", "")

            if bible_abbr == distinct_id and detail_canon == canon:
                audio_filesets.append(fileset_id)
                # Check if any audio fileset has timing
                if self.normalize_fileset_id(fileset_id) in self.timing_filesets:
                    has_timing = True

        # Collect text filesets
        for text_detail in lang_data.get("text_details") or []:
            bible_abbr = text_detail.get("bible", {}).get("abbr", "")
            detail_canon = text_detail.get("canon", "")
            fileset_id = text_detail.get("fileset", {}).get("id", "")

            if bible_abbr == distinct_id and detail_canon == canon:
                text_filesets.append(fileset_id)

        # Determine flags
        # Since filesets are already filtered by distinct_id and canon,
        # if both audio and text exist, they belong to the same Bible version
        has_audio = len(audio_filesets) > 0
        has_text = len(text_filesets) > 0

        # Apply categorization logic
        if has_timing:
            if has_text and has_audio:
                return "with-timecode"
            elif has_audio and not has_text:
                return "audio-with-timecode"
            elif has_text and not has_audio:
                # Text + timing (without audio) -> treat as text-only
                return "text-only"
            else:
                # Edge case: timing alone without any content - skip
                return None
        else:
            if has_text and has_audio:
                return "syncable"
            elif has_text and not has_audio:
                return "text-only"
            elif has_audio and not has_text:
                return "audio-only"
            else:
                return None  # No content - skip

    def determine_fileset_category(self, fileset_detail: dict) -> str:
        """
        Determine category for individual fileset based on its own capabilities.

        Returns individual fileset capability:
        - "text": Text-only fileset
        - "audio": Audio-only fileset
        - "timing": Timing data fileset
        """
        fileset_type = fileset_detail["fileset"].get("type", "")
        fileset_id = fileset_detail["fileset"].get("id", "")

        is_audio = fileset_type in [
            "audio",
            "audio_drama",
            "audio_stream",
            "audio_drama_stream",
        ]
        is_text = fileset_type.startswith("text")
        has_timing = self.normalize_fileset_id(fileset_id) in self.timing_filesets

        if has_timing:
            return "timing"
        elif is_audio:
            return "audio"
        elif is_text:
            return "text"
        else:
            return "unknown"

    def create_metadata(
        self, iso: str, fileset_detail: dict, syncable_pairs: list[dict]
    ) -> dict:
        """Create comprehensive metadata for a fileset."""
        fileset = fileset_detail["fileset"]
        bible = fileset_detail["bible"]
        canon = fileset_detail["canon"]

        fileset_id = fileset.get("id", "")
        fileset_type = fileset.get("type", "")

        is_audio = fileset_type in [
            "audio",
            "audio_drama",
            "audio_stream",
            "audio_drama_stream",
        ]
        is_text = fileset_type.startswith("text")

        # Get syncable pairs for this fileset
        audio_text_pairs = []
        if is_audio and self.is_syncable(fileset_id, syncable_pairs):
            for pair in syncable_pairs:
                if pair["audio_fileset_id"] == fileset_id:
                    audio_text_pairs.append(pair)

        # Check timing availability
        has_timing = self.normalize_fileset_id(fileset_id) in self.timing_filesets

        # Determine categories
        distinct_id = bible.get("abbr", "")
        individual_category = self.determine_fileset_category(fileset_detail)
        aggregate_category = self.determine_category(iso, distinct_id, canon)

        # Check aggregate capabilities for this (distinct_id, canon) combination
        canon_has_text = False
        canon_has_audio = False
        canon_has_timing = False

        lang_data = self.language_data.get(iso)
        if lang_data:
            # Check audio filesets for this distinct_id/canon
            for audio_detail in lang_data.get("audio_details") or []:
                bible_abbr = audio_detail.get("bible", {}).get("abbr", "")
                detail_canon = audio_detail.get("canon", "")
                audio_fileset_id = audio_detail.get("fileset", {}).get("id", "")

                if bible_abbr == distinct_id and detail_canon == canon:
                    canon_has_audio = True
                    if (
                        self.normalize_fileset_id(audio_fileset_id)
                        in self.timing_filesets
                    ):
                        canon_has_timing = True

            # Check text filesets for this distinct_id/canon
            for text_detail in lang_data.get("text_details") or []:
                bible_abbr = text_detail.get("bible", {}).get("abbr", "")
                detail_canon = text_detail.get("canon", "")

                if bible_abbr == distinct_id and detail_canon == canon:
                    canon_has_text = True

        metadata = {
            "language": self.language_data[iso]["language_info"],
            "bible": {
                "abbr": bible.get("abbr", ""),
                "name": bible.get("name", ""),
                "vname": bible.get("vname", ""),
            },
            "fileset": {
                "id": fileset_id,
                "type": fileset_type,
                "size": fileset.get("size", ""),
                "volume": fileset.get("volume", ""),
                "date": bible.get("date") or fileset.get("date") or "",
            },
            "individual_category": individual_category,
            "aggregate_category": aggregate_category,
            "canon": canon,
            "category": aggregate_category,  # Backward compatibility - use aggregate
            "categorization": {
                # Individual fileset capabilities
                "has_text": is_text,
                "has_audio": is_audio,
                "has_timing": has_timing,
                # Aggregate (distinct_id, canon) capabilities
                "canon_has_text": canon_has_text,
                "canon_has_audio": canon_has_audio,
                "canon_has_timing": canon_has_timing,
                # Other fields
                "data_source": self.determine_data_source(
                    fileset_id, is_audio, syncable_pairs
                ),
                "syncable": self.is_syncable(fileset_id, syncable_pairs),
                "audio_text_pairs": audio_text_pairs,
            },
            "download_ready": {
                "text_fileset": fileset_id if is_text else None,
                "audio_fileset": fileset_id if is_audio else None,
                "timing_available": has_timing,
            },
        }

        # Add collection info if available (position 6 in fileset ID)
        if len(fileset_id) >= 7:
            collection = fileset_id[6]
            fileset_dict = metadata.get("fileset")
            if fileset_dict is not None:
                fileset_dict["collection"] = collection

        # Add extended metadata from timing_bibles if available
        bible_abbr = bible.get("abbr", "")
        if bible_abbr in self.timing_bibles_metadata:
            extended = self.timing_bibles_metadata[bible_abbr]
            bible_dict = metadata.get("bible")
            if bible_dict is not None:
                if extended.get("mark"):
                    bible_dict["mark"] = extended["mark"]
                if extended.get("country"):
                    bible_dict["country"] = extended["country"]
                if extended.get("description"):
                    bible_dict["description"] = extended["description"]
                if extended.get("vdescription"):
                    bible_dict["vdescription"] = extended["vdescription"]

        # Add per-resource script/direction for multi-script languages
        lang_info = self.language_data[iso]["language_info"]
        if lang_info and (
            isinstance(lang_info.get("script"), list)
            or isinstance(lang_info.get("direction"), list)
        ):
            detail = self.bible_details_metadata.get(bible_abbr)
            if detail:
                bible_dict = metadata.get("bible")
                if bible_dict is not None:
                    if detail.get("script"):
                        bible_dict["script"] = detail["script"]
                    if detail.get("direction"):
                        bible_dict["direction"] = detail["direction"]

        return metadata

    def track_exclusions(
        self,
        iso: str,
        bible: dict,
        fileset: dict,
        fileset_id: str,
        fileset_type: str,
        canon: str,
    ):
        """Track exclusions and reasons."""

        def create_exclusion_record(reason: str, **extra_fields):
            """Create a standard exclusion record."""
            record = {
                "iso": iso,
                "language": bible.get("language", ""),
                "bible_abbr": bible.get("abbr", ""),
                "bible_name": bible.get("name", ""),
                "fileset_id": fileset_id,
                "type": fileset_type,
                "size": fileset.get("size", ""),
                "reason": reason,
            }
            record.update(extra_fields)
            return record

        # Check for streaming-only story adaptations (SA suffix)
        if fileset_id.endswith("SA"):
            self.exclusions["sa_versions"].append(
                create_exclusion_record("Streaming-only Story Adaptation (SA suffix)")
            )

        # Check for partial content (collection P)
        if canon == "PARTIAL":
            self.exclusions["partial_content"].append(
                create_exclusion_record(
                    "Partial content (collection P - incomplete book set)",
                    book_set=canon,
                )
            )

        # Check for story adaptations from video filesets
        if "story" in fileset_type.lower() or "video" in fileset_type.lower():
            self.exclusions["story_adaptations"].append(
                create_exclusion_record("Video/Story adaptation format")
            )

    def save_metadata(
        self,
        iso: str,
        fileset_id: str,
        metadata: dict,
        canon: Optional[str] = None,
        original_canon: Optional[str] = None,
    ):
        """Save metadata to the appropriate directory.

        For expanded FULL filesets, append canon suffix to create separate directories.
        """
        # If this is an expanded FULL fileset, append canon to directory name
        if original_canon == "FULL" and canon in ["NT", "OT"]:
            output_path = self.output_dir / iso / f"{fileset_id}-{canon.lower()}"
        else:
            output_path = self.output_dir / iso / fileset_id

        output_path.mkdir(parents=True, exist_ok=True)

        metadata_file = output_path / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def process_all_languages(self):
        """
        Process all languages and create sorted directory structure.

        For each language:
        1. Compute syncable pairs
        2. Create metadata for each fileset
        3. Save to sorted/{iso}/{fileset_id}/metadata.json
        """
        processed_count = 0

        for iso, lang_data in self.language_data.items():
            # Compute syncable pairs for this language
            syncable_pairs = self.compute_syncable_pairs(iso)

            # Process audio filesets
            for audio_detail in lang_data.get("audio_details") or []:
                fileset_id = audio_detail["fileset"]["id"]

                # For expanded FULL filesets, include canon in key to allow duplicate processing
                canon_for_key = audio_detail.get("canon", "")
                original_canon = audio_detail.get("original_canon", canon_for_key)
                if original_canon == "FULL":
                    fileset_key = f"{iso}/{fileset_id}/{canon_for_key}"
                else:
                    fileset_key = f"{iso}/{fileset_id}"

                if fileset_key in self.processed_filesets:
                    continue

                self.processed_filesets.add(fileset_key)

                metadata = self.create_metadata(iso, audio_detail, syncable_pairs)
                canon = metadata.get("canon")
                original_canon = audio_detail.get("original_canon", canon)
                self.save_metadata(iso, fileset_id, metadata, canon, original_canon)

                # Track exclusions
                bible = audio_detail.get("bible", {})
                fileset = audio_detail.get("fileset", {})
                fileset_type = fileset.get("type", "")
                canon = metadata["canon"]
                self.track_exclusions(
                    iso, bible, fileset, fileset_id, fileset_type, canon
                )

                processed_count += 1

            # Process text filesets
            for text_detail in lang_data.get("text_details") or []:
                fileset_id = text_detail["fileset"]["id"]

                # For expanded FULL filesets, include canon in key to allow duplicate processing
                canon_for_key = text_detail.get("canon", "")
                original_canon = text_detail.get("original_canon", canon_for_key)
                if original_canon == "FULL":
                    fileset_key = f"{iso}/{fileset_id}/{canon_for_key}"
                else:
                    fileset_key = f"{iso}/{fileset_id}"

                if fileset_key in self.processed_filesets:
                    continue

                self.processed_filesets.add(fileset_key)

                metadata = self.create_metadata(iso, text_detail, syncable_pairs)
                canon = metadata.get("canon")
                original_canon = text_detail.get("original_canon", canon)
                self.save_metadata(iso, fileset_id, metadata, canon, original_canon)

                # Track exclusions
                bible = text_detail.get("bible", {})
                fileset = text_detail.get("fileset", {})
                fileset_type = fileset.get("type", "")
                canon = metadata["canon"]
                self.track_exclusions(
                    iso, bible, fileset, fileset_id, fileset_type, canon
                )

                processed_count += 1

            if processed_count % 1000 == 0:
                print(f"Processed {processed_count} filesets...")

        print("\nProcessing complete:")
        print(f"  - Processed: {processed_count} filesets")
        print(f"  - Languages: {len(self.language_data)}")
        print(f"  - Output directory: {self.output_dir}")

        # Save exclusion data
        self.save_exclusions()

    def save_exclusions(self):
        """Save exclusion data to sorted/BB/exclude_download.json."""
        exclusion_file = self.output_dir / "exclude_download.json"

        # Create summary statistics
        summary = {
            "generated": datetime.now().isoformat(),
            "summary": {
                "sa_versions": len(self.exclusions["sa_versions"]),
                "partial_content": len(self.exclusions["partial_content"]),
                "story_adaptations": len(self.exclusions["story_adaptations"]),
                "total_excluded": sum(len(v) for v in self.exclusions.values()),
            },
            "exclusions": self.exclusions,
        }

        with open(exclusion_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print("\nExclusion tracking:")
        print(
            f"  - SA versions (streaming-only): {len(self.exclusions['sa_versions'])}"
        )
        print(
            f"  - Partial content (OTP/NTP): {len(self.exclusions['partial_content'])}"
        )
        print(
            f"  - Story adaptations (video): {len(self.exclusions['story_adaptations'])}"
        )
        print(f"  - Total excluded: {sum(len(v) for v in self.exclusions.values())}")
        print(f"  - Saved to: {exclusion_file}")

    def generate_summary(self):
        """Generate a summary of what was sorted."""
        summary = {
            "total_languages": len(self.language_data),
            "total_filesets": len(self.processed_filesets),
            "timing_filesets_available": len(self.timing_filesets),
        }

        # Count by category
        syncable_count = 0
        timing_count = 0
        audio_count = 0
        text_count = 0

        for iso, lang_data in self.language_data.items():
            syncable_pairs = self.compute_syncable_pairs(iso)
            syncable_count += len(syncable_pairs)

            for audio_detail in lang_data.get("audio_details") or []:
                audio_count += 1
                fileset_id = audio_detail["fileset"]["id"]
                if self.normalize_fileset_id(fileset_id) in self.timing_filesets:
                    timing_count += 1

            text_details = lang_data.get("text_details")
            if text_details:
                text_count += len(text_details)

        summary["syncable_pairs"] = syncable_count
        summary["filesets_with_timing"] = timing_count
        summary["audio_filesets"] = audio_count
        summary["text_filesets"] = text_count

        summary_file = self.output_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print("\nSummary:")
        print(f"  - Total languages: {summary['total_languages']}")
        print(f"  - Total filesets: {summary['total_filesets']}")
        print(f"  - Audio filesets: {summary['audio_filesets']}")
        print(f"  - Text filesets: {summary['text_filesets']}")
        print(f"  - Syncable pairs: {summary['syncable_pairs']}")
        print(f"  - With timing: {summary['filesets_with_timing']}")

    def run(self):
        """Run the complete sorting process - FULLY INDEPENDENT."""
        print("=" * 70)
        print("INDEPENDENT Cache Data Sorter")
        print("=" * 70)

        steps = [
            ("Loading timing filesets", self.load_timing_filesets),
            (
                "Loading extended metadata from timing bibles",
                self.load_timing_bibles_metadata,
            ),
            ("Loading bible details metadata", self.load_bible_details_metadata),
            ("Loading all Bibles", self.load_all_bibles),
            ("Organizing language data", self.organize_language_data),
            ("Processing filesets and creating metadata", self.process_all_languages),
            ("Generating summary", self.generate_summary),
        ]

        for i, (desc, func) in enumerate(steps, 1):
            print(f"\nStep {i}: {desc}...")
            func()

        print("\n" + "=" * 70)
        print("Sorting complete!")
        print("=" * 70)
        print()
        print("All categorization was computed directly from api-cache.")
        print()
        print(f"Output: {self.output_dir}/")


def main():
    sorter = IndependentCacheDataSorter()
    sorter.run()


if __name__ == "__main__":
    main()
