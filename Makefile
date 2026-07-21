PYTHON := .venv/bin/python
CORE := pipeline/core

.PHONY: all dbt-metadata versification vrs vrs-map version-info \
        publish-dbt publish-dbt-dry cleanup-dbt cleanup-dbt-dry \
        cache align-pull align-pull-dry check help

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
	@echo ""
	@echo "  CDN publishing"
	@echo "  ──────────────"
	@echo "  make publish-dbt      Upload export/ to cdn.bibel.wiki (incremental)"
	@echo "  make publish-dbt-dry  Dry-run (no writes to CDN)"
	@echo "  make cleanup-dbt      Delete orphaned files from CDN"
	@echo "  make cleanup-dbt-dry  Dry-run orphan cleanup"
	@echo ""
	@echo "  Data fetch"
	@echo "  ──────────"
	@echo "  make cache            Fetch API data (helloAO + DBS)"
	@echo "  make align-pull       Pull new audio-sync align/ output into internal-data/align-cache/"
	@echo "  make align-pull-dry   Dry-run align pull (no writes)"
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

# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

cache: ## Fetch API data (helloAO + DBS) into api-cache/
	$(PYTHON) $(CORE)/fetch_helloao_cache.py
	$(PYTHON) $(CORE)/fetch_dbs_cache.py

align-pull: ## Pull new audio-sync align/ output (Contract B) into internal-data/align-cache/
	$(PYTHON) $(CORE)/pull_align_cache.py

align-pull-dry: ## Dry-run align pull (no writes)
	$(PYTHON) $(CORE)/pull_align_cache.py --dry-run

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

check: ## Verify installation
	$(PYTHON) --version
	@echo "rclone: $$(rclone version 2>/dev/null | head -1 || echo 'not found')"

clean: ## Remove generated export/
	rm -rf export/
