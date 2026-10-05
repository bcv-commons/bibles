PYTHON := .venv/bin/python
CORE := pipeline/core

.PHONY: all dbt-metadata versification vrs vrs-map version-info dbt-catalog catalog-books \
        publish-dbt publish-dbt-dry cleanup-dbt cleanup-dbt-dry \
        publish-catalog publish-catalog-dry \
        publish-openbible publish-openbible-dry \
        publish-audiobiblia publish-audiobiblia-dry \
        publish-vrs-maps publish-vrs-maps-dry vrs-check \
        cache fetch-dbt-catalog sort-dbt-catalog fetch-catalog-books align-pull align-pull-dry \
        fetch-obs-batches fetch-obs-catalog fetch-obs-repos fetch-obs-titles obs-metadata publish-obs publish-obs-dry \
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
	@echo "  make publish-openbible   Upload export/openbible/ to cdn.bibel.wiki/openbible/"
	@echo "  make publish-openbible-dry Dry-run (no writes to CDN)"
	@echo "  make publish-audiobiblia Upload export/audiobiblia/ to cdn.bibel.wiki/audiobiblia/"
	@echo "  make publish-audiobiblia-dry Dry-run (no writes to CDN)"
	@echo "  make publish-obs         Upload export/obs/ to cdn.bibel.wiki/obs/"
	@echo "  make publish-obs-dry     Dry-run (no writes to CDN)"
	@echo "  make publish-vrs-maps     Upload _vrs/map/{org,catm,rso}-to-eng.json and verify live sha256"
	@echo "  make publish-vrs-maps-dry Dry-run the verse-map upload (no writes)"
	@echo "  make vrs-check        Verify pinned TVTMS input, re-derive org->eng, rebuild maps"
	@echo ""
	@echo "  Data fetch"
	@echo "  ──────────"
	@echo "  make cache            Fetch API data (helloAO + DBS)"
	@echo "  make fetch-dbt-catalog Fetch DBT's raw bible catalog into internal-data/api-cache/"
	@echo "  make sort-dbt-catalog Derive internal-data/sorted/BB/ from the fetched catalog"
	@echo "  make fetch-catalog-books Fetch PKF + helloAO per-language book data (for catalog-books)"
	@echo "  make align-pull       Pull new audio-sync align/_runs/ manifests (Bible text + OBS) into internal-data/{align,obs-align}-index.json"
	@echo "  make align-pull-dry   Dry-run align pull (no writes)"
	@echo "  make fetch-obs-batches Fetch OBS narration batch manifests into internal-data/obs-batches/"
	@echo "  make fetch-obs-catalog Fetch door43's OBS catalog stats, text+audio (existence source of truth)"
	@echo "  make fetch-obs-repos  Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)"
	@echo "  make fetch-obs-titles Fetch per-story vernacular titles for every OBS language (run fetch-obs-repos first)"
	@echo "  make obs-metadata     Generate export/obs/<iso>/media.json + catalog/obs-index.json (pulls audio-sync's OBS align existence itself)"
	@echo "  make langs-catalog    Generate catalog/langs.json + langs-mini.json (also runs dbt-metadata + obs-metadata first)"
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
	$(PYTHON) $(CORE)/pull_align_manifests.py
	$(PYTHON) $(CORE)/publish_timing_raw.py
	$(PYTHON) $(CORE)/generate_audio_metadata.py
	$(PYTHON) $(CORE)/generate_sync_candidates.py
	$(PYTHON) $(CORE)/generate_dbt_coverage.py
	$(PYTHON) $(CORE)/generate_helloao_crosswalk.py
	$(PYTHON) $(CORE)/generate_dbt_catalog.py

vrs: ## Verify + stage the standard .vrs scheme files
	$(PYTHON) $(CORE)/generate_vrs.py $(ARGS)

vrs-map: ## Build cross-scheme verse maps (org + catm from the derived TVTMS map, others from baselines)
	@for s in lxx vul; do \
	  $(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme $$s \
	    --crosswalk data/vrs/crosswalk-$$s.toml \
	    --mapping data/vrs/tvtms-$$s-to-eng.baseline.tsv \
	    --tvtms-rev $(TVTMS_REV) $(ARGS) ; \
	done
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme rso \
	  --crosswalk data/vrs/crosswalk-rso.toml \
	  --mapping data/vrs/tvtms-rso-to-eng.derived.tsv \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme orgw \
	  --crosswalk data/vrs/crosswalk-orgw.toml \
	  --mapping data/vrs/tvtms-orgw-to-eng.derived.tsv \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme org \
	  --crosswalk data/vrs/crosswalk-org.toml \
	  --mapping data/vrs/tvtms-org-to-eng.derived.tsv \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
	@# catm's data rows are identical to org's (verified), so it reads the same derived map.
	@# --compare-vrs so real catm/org shape divergence gets recorded honestly
	@# instead of silently falling through classify_exceptions()'s blind spot
	@# for chapters the reused map never had a row for.
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme catm \
	  --crosswalk data/vrs/crosswalk-catm.toml \
	  --mapping data/vrs/tvtms-org-to-eng.derived.tsv \
	  --compare-vrs org \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)

TVTMS_REV ?= UNPINNED
TVTMS_ORG_REV := 902681f77a4a2975b809555ff3c35ffe3c48a1d5

versification: ## Fingerprint DBT versification schemes
	$(PYTHON) $(CORE)/fingerprint_versification.py $(ARGS)

version-info: ## Generate version-info artifact
	$(PYTHON) $(CORE)/generate_version_info.py $(ARGS)

dbt-catalog: ## Generate catalog-text.json / catalog-audio.json from the fetched DBT catalog
	$(PYTHON) $(CORE)/generate_dbt_catalog.py $(ARGS)

catalog-books: ## Generate per-language /catalog/<iso[0]>/<iso>/books.json (run fetch-catalog-books first)
	$(PYTHON) $(CORE)/generate_catalog_books.py $(ARGS)

langs-catalog: dbt-metadata obs-metadata ## Generate catalog/langs.json + langs-mini.json (Phase 2 — self-derived; now chained after its two real prerequisites so it can't go stale from being forgotten)
	$(PYTHON) pipeline/comparison/generate_langs_catalog.py $(ARGS)

obs-metadata: ## Generate export/obs/<iso>/media.json + catalog/obs-index.json (run fetch-obs-catalog, fetch-obs-repos, fetch-obs-titles first; fetch-obs-batches optional, enrichment only)
	$(PYTHON) $(CORE)/pull_align_manifests.py
	$(PYTHON) $(CORE)/generate_obs_metadata.py $(ARGS)
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

publish-openbible: ## Upload export/openbible/ to cdn.bibel.wiki/openbible/
	bash $(CORE)/publish-openbible.sh

publish-openbible-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-openbible.sh

publish-audiobiblia: ## Upload export/audiobiblia/ to cdn.bibel.wiki/audiobiblia/
	bash $(CORE)/publish-audiobiblia.sh

publish-audiobiblia-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-audiobiblia.sh

publish-vrs-maps: ## Upload export/_vrs/map/{org,catm,rso}-to-eng.json and verify live sha256
	bash $(CORE)/publish-vrs-maps.sh

publish-vrs-maps-dry: ## Dry-run the verse-map upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-vrs-maps.sh

vrs-check: ## Verify pinned TVTMS input, re-derive org->eng, rebuild maps, print org row count and sha256
	$(PYTHON) $(CORE)/derive_tvtms_org_eng.py --check
	$(PYTHON) $(CORE)/derive_tvtms_org_eng.py
	$(MAKE) vrs-map
	@echo "── org-to-eng.json row count and sha256:"
	@python3 -c "import json;print(len(json.load(open('export/_vrs/map/org-to-eng.json'))['map']),'rows')"
	@shasum -a 256 export/_vrs/map/org-to-eng.json | cut -c1-64

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

align-pull: ## Pull new audio-sync align/_runs/ manifests (Bible text + OBS) into internal-data/{align,obs-align}-index.json (also runs as part of dbt-metadata/obs-metadata)
	$(PYTHON) $(CORE)/pull_align_manifests.py

align-pull-dry: ## Dry-run align pull (no writes)
	$(PYTHON) $(CORE)/pull_align_manifests.py --dry-run

fetch-obs-batches: ## Fetch OBS narration batch manifests into internal-data/obs-batches/
	$(PYTHON) $(CORE)/fetch_obs_batches.py

fetch-obs-catalog: ## Fetch door43's OBS catalog stats, text+audio (existence source of truth)
	$(PYTHON) $(CORE)/fetch_obs_catalog.py

fetch-obs-repos: ## Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)
	$(PYTHON) $(CORE)/fetch_obs_repos.py

fetch-obs-titles: ## Fetch per-story vernacular titles for every OBS language (run fetch-obs-repos first)
	$(PYTHON) $(CORE)/fetch_obs_titles.py $(ARGS)

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

check: ## Verify installation
	$(PYTHON) --version
	@echo "rclone: $$(rclone version 2>/dev/null | head -1 || echo 'not found')"

clean: ## Remove generated export/
	rm -rf export/
