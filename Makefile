PYTHON := .venv/bin/python
CORE := pipeline/core

.PHONY: all dbt-metadata versification vrs vrs-map version-info dbt-catalog catalog-books \
        publish-dbt publish-dbt-dry cleanup-dbt cleanup-dbt-dry \
        publish-catalog publish-catalog-dry \
        cache fetch-dbt-catalog sort-dbt-catalog fetch-catalog-books align-pull align-pull-dry \
        fetch-obs-batches fetch-obs-catalog fetch-obs-repos fetch-obs-titles pull-obs-align obs-metadata publish-obs publish-obs-dry \
        langs-catalog check help

help: ## Show available targets
	@echo "bibles — CDN publish pipeline"
	@echo ""
	@echo "  Metadata generation"
	@echo "  ───────────────────"
	@echo "  make dbt-metadata     Generate all CDN artifacts into export/"
	@echo "  make vrs              Stage .vrs scheme files"
	@echo "  make vrs-map          Build cross-scheme verse maps (/_vrs/map/)"
	@echo "  make versification    Fingerprint versification schemes"
	@echo "  make version-info     Generate version-info artifact"
	@echo "  make dbt-catalog      Generate catalog-text.json / catalog-audio.json"
	@echo "  make catalog-books    Generate per-language /catalog/<iso[0]>/<iso>/books.json"
	@echo ""
	@echo "  CDN publishing"
	@echo "  ──────────────"
	@echo "  make publish-dbt      Upload export/ to cdn.bibel.wiki (incremental)"
	@echo "  make publish-dbt-dry  Dry-run (no writes to CDN)"
	@echo "  make cleanup-dbt      Delete orphaned files from CDN"
	@echo "  make cleanup-dbt-dry  Dry-run orphan cleanup"
	@echo "  make publish-catalog     Upload export/catalog/ to cdn.bibel.wiki/catalog/"
	@echo "  make publish-catalog-dry Dry-run (no writes to CDN)"
	@echo "  make publish-obs         Upload export/obs/ to cdn.bibel.wiki/obs/"
	@echo "  make publish-obs-dry     Dry-run (no writes to CDN)"
	@echo ""
	@echo "  Data fetch"
	@echo "  ──────────"
	@echo "  make cache            Fetch API data (helloAO + DBS)"
	@echo "  make fetch-dbt-catalog Fetch DBT's raw bible catalog into internal-data/api-cache/"
	@echo "  make sort-dbt-catalog Derive internal-data/sorted/BB/ from the fetched catalog"
	@echo "  make fetch-catalog-books Fetch PKF + helloAO per-language book data (for catalog-books)"
	@echo "  make align-pull       Pull new audio-sync align/ output into internal-data/align-cache/"
	@echo "  make align-pull-dry   Dry-run align pull (no writes)"
	@echo "  make fetch-obs-batches Fetch OBS narration batch manifests into internal-data/obs-batches/"
	@echo "  make fetch-obs-catalog Fetch door43's OBS catalog stats, text+audio (existence source of truth)"
	@echo "  make fetch-obs-repos  Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)"
	@echo "  make fetch-obs-titles Fetch per-story vernacular titles for every OBS language (run fetch-obs-repos first)"
	@echo "  make pull-obs-align   Pull real audio-sync OBS alignment output into internal-data/obs-align-cache/"
	@echo "  make obs-metadata     Generate export/obs/<iso>/{media,timing}.json + catalog/obs-index.json"
	@echo "  make langs-catalog    Generate catalog/langs.json + langs-mini.json (run dbt-metadata + obs-metadata first)"
	@echo ""
	@echo "  Pass extra args via ARGS, e.g.:"
	@echo "    make versification ARGS=\"--fetch\""
	@echo "    make vrs-map TVTMS_REV=abc1234"
	@echo ""
	@echo "  Pipeline code lives under pipeline/ (see pipeline/README.md)."
	@echo "  Using this data in your own app? Start at doc/README.md instead."

# ---------------------------------------------------------------------------
# Metadata generation
# ---------------------------------------------------------------------------

dbt-metadata: ## Generate media.json + per-book timing + versification for CDN
	$(PYTHON) $(CORE)/generate_vrs.py
	$(MAKE) vrs-map
	$(PYTHON) $(CORE)/fingerprint_versification.py
	$(PYTHON) $(CORE)/generate_audio_metadata.py
	$(PYTHON) $(CORE)/generate_timing_by_book.py
	$(PYTHON) $(CORE)/generate_helloao_crosswalk.py
	$(PYTHON) $(CORE)/generate_dbt_catalog.py

vrs: ## Verify + stage the standard .vrs scheme files
	$(PYTHON) $(CORE)/generate_vrs.py $(ARGS)

vrs-map: ## Build cross-scheme verse maps from pinned TVTMS baselines
	@for s in lxx vul org orgw rso catm; do \
	  $(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme $$s \
	    --crosswalk data/vrs/crosswalk-$$s.toml \
	    --mapping data/vrs/tvtms-$$s-to-eng.baseline.tsv \
	    --tvtms-rev $(TVTMS_REV) $(ARGS) ; \
	done

TVTMS_REV ?= UNPINNED

versification: ## Fingerprint DBT versification schemes
	$(PYTHON) $(CORE)/fingerprint_versification.py $(ARGS)

version-info: ## Generate version-info artifact
	$(PYTHON) $(CORE)/generate_version_info.py $(ARGS)

dbt-catalog: ## Generate catalog-text.json / catalog-audio.json from the fetched DBT catalog
	$(PYTHON) $(CORE)/generate_dbt_catalog.py $(ARGS)

catalog-books: ## Generate per-language /catalog/<iso[0]>/<iso>/books.json (run fetch-catalog-books first)
	$(PYTHON) $(CORE)/generate_catalog_books.py $(ARGS)

langs-catalog: ## Generate catalog/langs.json + langs-mini.json (Phase 2 — self-derived, no external dependency; run dbt-metadata + obs-metadata first)
	$(PYTHON) pipeline/comparison/generate_langs_catalog.py $(ARGS)

obs-metadata: ## Generate export/obs/<iso>/{media,timing}.json + catalog/obs-index.json (run fetch-obs-catalog, fetch-obs-repos, fetch-obs-titles, pull-obs-align first; fetch-obs-batches optional, enrichment only)
	$(PYTHON) $(CORE)/generate_obs_metadata.py $(ARGS)
	$(PYTHON) $(CORE)/generate_obs_timing.py $(ARGS)
	$(PYTHON) pipeline/comparison/generate_obs_index.py $(ARGS)

# ---------------------------------------------------------------------------
# CDN publishing
# ---------------------------------------------------------------------------

publish-dbt: ## Upload dbt/ metadata to cdn.bibel.wiki (incremental delta)
	bash $(CORE)/publish-dbt.sh

publish-dbt-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-dbt.sh

cleanup-dbt: ## Delete orphaned files from CDN
	CLEANUP=1 bash $(CORE)/publish-dbt.sh

cleanup-dbt-dry: ## Dry-run orphan cleanup (no deletes)
	CLEANUP=1 DRY_RUN=1 bash $(CORE)/publish-dbt.sh

publish-catalog: ## Upload export/catalog/ to cdn.bibel.wiki/catalog/
	bash $(CORE)/publish-catalog.sh

publish-catalog-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-catalog.sh

publish-obs: ## Upload export/obs/ to cdn.bibel.wiki/obs/
	bash $(CORE)/publish-obs.sh

publish-obs-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-obs.sh

# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

cache: ## Fetch API data (helloAO + DBS) into api-cache/
	$(PYTHON) $(CORE)/fetch_helloao_cache.py
	$(PYTHON) $(CORE)/fetch_dbs_cache.py

fetch-dbt-catalog: ## Fetch DBT's raw bible catalog into internal-data/api-cache/ (needs BIBLE_API_KEY)
	$(PYTHON) $(CORE)/fetch_api_cache.py $(ARGS)

sort-dbt-catalog: ## Derive internal-data/sorted/BB/ from the fetched DBT catalog (run after fetch-dbt-catalog)
	$(PYTHON) $(CORE)/sort_cache_data.py

fetch-catalog-books: ## Fetch PKF + helloAO per-language book data into internal-data/api-cache/ (resumable)
	$(PYTHON) $(CORE)/fetch_pkf_book_data.py
	$(PYTHON) $(CORE)/fetch_helloao_book_data.py

align-pull: ## Pull new audio-sync align/ output (Contract B) into internal-data/align-cache/
	$(PYTHON) $(CORE)/pull_align_cache.py

align-pull-dry: ## Dry-run align pull (no writes)
	$(PYTHON) $(CORE)/pull_align_cache.py --dry-run

fetch-obs-batches: ## Fetch OBS narration batch manifests into internal-data/obs-batches/
	$(PYTHON) $(CORE)/fetch_obs_batches.py

fetch-obs-catalog: ## Fetch door43's OBS catalog stats, text+audio (existence source of truth)
	$(PYTHON) $(CORE)/fetch_obs_catalog.py

fetch-obs-repos: ## Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)
	$(PYTHON) $(CORE)/fetch_obs_repos.py

fetch-obs-titles: ## Fetch per-story vernacular titles for every OBS language (run fetch-obs-repos first)
	$(PYTHON) $(CORE)/fetch_obs_titles.py $(ARGS)

pull-obs-align: ## Pull real audio-sync OBS alignment output into internal-data/obs-align-cache/
	$(PYTHON) $(CORE)/pull_obs_align.py

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

check: ## Verify installation
	$(PYTHON) --version
	@echo "rclone: $$(rclone version 2>/dev/null | head -1 || echo 'not found')"

clean: ## Remove generated export/
	rm -rf export/
