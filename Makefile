PYTHON := .venv/bin/python
CORE := pipeline/core

.PHONY: all dbt-metadata versification vrs vrs-map version-info dbt-catalog catalog-books languages \
        publish-dbt publish-dbt-dry cleanup-dbt cleanup-dbt-dry \
        publish-catalog publish-catalog-dry sofria-ebible stage-ebible publish-ebible publish-ebible-dry text-route edition-struct \
        crosswire-usj sofria-crosswire stage-crosswire publish-crosswire publish-crosswire-dry \
        door43-usj sofria-door43 stage-door43 publish-door43 publish-door43-dry \
        publish-openbible publish-openbible-dry \
        publish-audiobiblia publish-audiobiblia-dry mirror-audiobiblia-audio publish-audiobiblia-audio publish-audiobiblia-audio-dry \
        sofria-openbible sofria-audiobiblia stage-sofria openbible-editions publish-sofria publish-sofria-meta publish-sofria-dry retire-verse-json retire-verse-json-dry \
        publish-vrs-maps publish-vrs-maps-dry publish-vrs-index publish-vrs-index-dry vrs-check \
        cache fetch-dbt-catalog sort-dbt-catalog fetch-catalog-books align-pull align-pull-dry fetch-dbt-timing fetch-pkf-audio \
        fetch-obs-batches fetch-obs-catalog fetch-obs-repos fetch-obs-titles fetch-obs-video obs-metadata publish-obs publish-obs-dry \
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
	@echo "  make dbt-catalog      Generate catalog/text.json / catalog/audio.json / catalog/audio-index.json"
	@echo "  make text-route       Generate catalog/text-route.json (canonical text + reading route per edition)"
	@echo "  make edition-struct   Generate catalog/edition-struct.json (per-edition metadata: script, direction, normalization, ...)"
	@echo "  make catalog-books    Generate per-language /catalog/<iso[0]>/<iso>/books.json"
	@echo "  make languages        Language names, audio-only list, availability.json, langs.json"
	@echo ""
	@echo "  CDN publishing"
	@echo "  ──────────────"
	@echo "  make publish-dbt      Upload export/ to cdn.bibel.wiki (incremental)"
	@echo "  make publish-dbt-dry  Dry-run (no writes to CDN)"
	@echo "  make cleanup-dbt      Delete orphaned files from CDN"
	@echo "  make cleanup-dbt-dry  Dry-run orphan cleanup"
	@echo "  make publish-catalog     Upload export/catalog/ to cdn.bibel.wiki/catalog/"
	@echo "  make publish-catalog-dry Dry-run (no writes to CDN)"
	@echo "  make publish-openbible   Upload staged Sofria + USJ (make stage-sofria) to cdn.bibel.wiki/openbible/"
	@echo "  make publish-openbible-dry Dry-run (no writes to CDN)"
	@echo "  make publish-audiobiblia Upload staged Sofria + USJ (make stage-sofria) to cdn.bibel.wiki/audiobiblia/"
	@echo "  make publish-audiobiblia-dry Dry-run (no writes to CDN)"
	@echo "  make mirror-audiobiblia-audio Download BLL's public-domain chapter audio from audiobiblia.org"
	@echo "  make publish-audiobiblia-audio Upload it to cdn.bibel.wiki/audiobiblia/spa/BLL/audio/ (-dry: no writes)"
	@echo "  make publish-obs         Upload export/obs/ to cdn.bibel.wiki/obs/"
	@echo "  make publish-obs-dry     Dry-run (no writes to CDN)"
	@echo "  make publish-vrs-maps     Upload _vrs/map/{org,orgw,catm,rso,vul,lxx}-to-eng.json + multiverse files, verify live sha256"
	@echo "  make publish-vrs-maps-dry Dry-run the verse-map upload (no writes)"
	@echo "  make vrs-check        Verify pinned TVTMS input, re-derive org->eng, rebuild maps"
	@echo ""
	@echo "  Data fetch"
	@echo "  ──────────"
	@echo "  make cache            Fetch API data (helloAO + DBS)"
	@echo "  make fetch-dbt-catalog Fetch DBT's raw bible catalog into internal-data/api-cache/"
	@echo "  make sort-dbt-catalog Derive internal-data/sorted/BB/ from the fetched catalog"
	@echo "  make fetch-catalog-books Fetch PKF + helloAO per-language book data (for catalog-books)"
	@echo "  make align-pull       Index audio-sync's align/ (Bible text + OBS) into internal-data/{align,obs-align}-index.json"
	@echo "  make align-pull-dry   Dry-run align pull (no writes)"
	@echo "  make fetch-pkf-audio  Index PKF's audio and timing into internal-data/pkf-audio-index.json (also in dbt-metadata)"
	@echo "  make fetch-dbt-timing Check which DBT audio filesets have DBT timing (REV 15 / PSA 117) into internal-data/dbt-timing-index.json"
	@echo "  make fetch-obs-batches Fetch OBS narration batch manifests into internal-data/obs-batches/"
	@echo "  make fetch-obs-catalog Fetch door43's OBS catalog stats, text+audio (existence source of truth)"
	@echo "  make fetch-obs-repos  Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)"
	@echo "  make fetch-obs-titles Fetch per-story vernacular titles for every OBS language (run fetch-obs-repos first)"
	@echo "  make fetch-obs-video  Fetch video-sync's YouTube ids for video-only OBS languages (also runs as part of obs-metadata)"
	@echo "  make obs-metadata     Generate export/obs/<iso>/media.json + catalog/obs-index.json (pulls audio-sync's OBS align existence and video-sync's YouTube ids itself)"
	@echo "  make langs-catalog    Generate catalog/langs.json + langs-mini.json (also runs dbt-metadata + obs-metadata first)"
	@echo ""
	@echo "  Pass extra args via ARGS, e.g.:"
	@echo "    make versification ARGS=\"--fetch\""
	@echo ""
	@echo "  Pipeline code lives under pipeline/ (see pipeline/README.md)."
	@echo "  Using this data in your own app? Start at doc/README.md instead."

# ---------------------------------------------------------------------------
# Metadata generation
# ---------------------------------------------------------------------------

dbt-metadata: ## Generate media.json + versification + DBT catalogs for CDN
	$(PYTHON) $(CORE)/generate_vrs.py
	$(MAKE) vrs-map
	$(PYTHON) $(CORE)/fingerprint_versification.py
	$(PYTHON) $(CORE)/pull_align_manifests.py
	$(PYTHON) $(CORE)/fetch_pkf_audio_index.py
	$(PYTHON) $(CORE)/publish_timing_raw.py
	$(PYTHON) $(CORE)/generate_audio_metadata.py
	$(PYTHON) $(CORE)/generate_sync_candidates.py
	$(PYTHON) $(CORE)/generate_dbt_coverage.py
	$(PYTHON) $(CORE)/generate_helloao_crosswalk.py
	$(PYTHON) $(CORE)/generate_dbt_catalog.py
	$(PYTHON) pipeline/comparison/generate_catalog_audio_index.py

vrs: ## Verify + stage the standard .vrs scheme files
	$(PYTHON) $(CORE)/generate_vrs.py $(ARGS)

vrs-map: ## Build cross-scheme verse maps (all derived from pinned TVTMS), <scheme>-to-org maps + nt-variants.json
	$(PYTHON) $(CORE)/generate_nt_variants.py
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme lxx \
	  --crosswalk data/vrs/crosswalk-lxx.toml \
	  --mapping data/vrs/tvtms-lxx-to-eng.derived.tsv \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme vul \
	  --crosswalk data/vrs/crosswalk-vul.toml \
	  --mapping data/vrs/tvtms-vul-to-eng.derived.tsv \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
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
	@# catm's rows are org's minus the chapters catm numbers as English (derive_tvtms_org_eng.py).
	@# --compare-vrs so real catm/org shape divergence gets recorded honestly
	@# instead of silently falling through classify_exceptions()'s blind spot
	@# for chapters the reused map never had a row for.
	$(PYTHON) $(CORE)/generate_vrs_map.py --source-scheme catm \
	  --crosswalk data/vrs/crosswalk-catm.toml \
	  --mapping data/vrs/tvtms-catm-to-eng.derived.tsv \
	  --compare-vrs org \
	  --tvtms-rev $(TVTMS_ORG_REV) $(ARGS)
	@# <scheme>-to-org: the maps above composed with org-to-eng inverted (needs them first).
	$(PYTHON) $(CORE)/generate_vrs_to_org.py
	@# Old Testament layouts that vary within a scheme (needs eng-to-org.json, above).
	$(PYTHON) $(CORE)/generate_ot_variants.py

TVTMS_ORG_REV := 902681f77a4a2975b809555ff3c35ffe3c48a1d5

versification: ## Fingerprint DBT versification schemes
	$(PYTHON) $(CORE)/fingerprint_versification.py $(ARGS)

version-info: ## Generate version-info artifact
	$(PYTHON) $(CORE)/generate_version_info.py $(ARGS)

dbt-catalog: ## Generate catalog/text.json / catalog/audio.json from the fetched DBT catalog, and catalog/audio-index.json (all sources)
	$(PYTHON) $(CORE)/generate_dbt_catalog.py $(ARGS)
	$(PYTHON) pipeline/comparison/generate_catalog_audio_index.py

catalog-books: ## Generate per-language /catalog/<iso[0]>/<iso>/books.json (run fetch-catalog-books first)
	$(PYTHON) $(CORE)/generate_catalog_books.py $(ARGS)

languages: dbt-metadata obs-metadata ## Language names, audio-only list, per-language availability.json and catalog/langs.json (after the catalog index + overlap; publish with publish-dbt and publish-catalog)
	$(PYTHON) $(CORE)/generate_language_names.py
	$(PYTHON) $(CORE)/generate_audio_only.py
	$(PYTHON) $(CORE)/generate_language_availability.py
	$(PYTHON) pipeline/comparison/generate_langs_catalog.py $(ARGS)

langs-catalog: languages ## Same as languages (old name)

obs-metadata: ## Generate export/obs/<iso>/media.json + catalog/obs-index.json (run fetch-obs-catalog, fetch-obs-repos, fetch-obs-titles first; fetch-obs-batches optional, enrichment only)
	$(PYTHON) $(CORE)/pull_align_manifests.py
	$(PYTHON) $(CORE)/fetch_obs_video.py
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

publish-openbible: ## Upload the staged Sofria + USJ + _meta.json (make stage-sofria) to cdn.bibel.wiki/openbible/
	bash $(CORE)/publish-openbible.sh

publish-openbible-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-openbible.sh

publish-audiobiblia: ## Upload the staged Sofria + USJ + _meta.json (make stage-sofria) to cdn.bibel.wiki/audiobiblia/
	bash $(CORE)/publish-audiobiblia.sh

publish-audiobiblia-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-audiobiblia.sh

AUDIOBIBLIA_AUDIO = SOURCE_DIR=internal-data/downloads/audiobiblia-audio RCLONE_EXTRA="--include */*/audio/*.m4a"

mirror-audiobiblia-audio: ## Download BLL's public-domain chapter audio from audiobiblia.org (needs the BLL USJ)
	$(PYTHON) $(CORE)/mirror_audiobiblia_audio.py $(ARGS)

# The staged _meta.json goes up with the audio: its formats.audio is what tells a client the audio
# exists (2026-10-28: the audio was published alone on 10-27 and the live _meta.json didn't list it).
publish-audiobiblia-audio: ## Upload the mirrored audio to cdn.bibel.wiki/audiobiblia/<iso>/<edition>/audio/, with the staged _meta.json
	$(AUDIOBIBLIA_AUDIO) bash $(CORE)/publish-audiobiblia.sh
	RCLONE_EXTRA="--include */*/_meta.json" SOURCE_DIR=$(SOFRIA_STAGE)/audiobiblia bash $(CORE)/publish-audiobiblia.sh

publish-audiobiblia-audio-dry: ## Dry-run CDN upload (no writes)
	$(AUDIOBIBLIA_AUDIO) DRY_RUN=1 bash $(CORE)/publish-audiobiblia.sh
	RCLONE_EXTRA="--include */*/_meta.json" SOURCE_DIR=$(SOFRIA_STAGE)/audiobiblia DRY_RUN=1 bash $(CORE)/publish-audiobiblia.sh

SOFRIA_OUT := export/publish/sofria
SOFRIA_STAGE := export/publish/stage

sofria-openbible: ## Convert openbible USJ to per-chapter Sofria
	node tools/usj-to-sofria/convert_batch.mjs export/openbible-usj $(SOFRIA_OUT)/openbible

sofria-audiobiblia: ## Convert audiobiblia USJ to per-chapter Sofria
	node tools/usj-to-sofria/convert_batch.mjs export/audiobiblia-usj $(SOFRIA_OUT)/audiobiblia

crosswire-usj: ## Generate export/crosswire-usj/ (USJ + _meta.json) from CrossWire SWORD modules (generate_crosswire_usj.py)
	$(PYTHON) $(CORE)/generate_crosswire_usj.py $(ARGS)

sofria-crosswire: ## Convert CrossWire USJ to per-chapter Sofria
	node tools/usj-to-sofria/convert_batch.mjs export/crosswire-usj $(SOFRIA_OUT)/crosswire

stage-crosswire: ## Stage CrossWire USJ, Sofria and _meta.json as hard links
	$(PYTHON) $(CORE)/stage_sofria_usj.py export/crosswire-usj $(SOFRIA_OUT)/crosswire $(SOFRIA_STAGE)/crosswire

publish-crosswire: ## Upload the staged CrossWire Sofria + USJ + _meta.json (make stage-crosswire) to cdn.bibel.wiki/crosswire/
	bash $(CORE)/publish-crosswire.sh

publish-crosswire-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-crosswire.sh

door43-usj: ## Generate export/door43-usj/ (USJ + _meta.json) from Door43 aligned Bibles at pinned commits (generate_door43_usj.py)
	$(PYTHON) $(CORE)/generate_door43_usj.py $(ARGS)

sofria-door43: ## Convert Door43 USJ to per-chapter Sofria
	node tools/usj-to-sofria/convert_batch.mjs export/door43-usj $(SOFRIA_OUT)/door43

stage-door43: ## Stage Door43 USJ, Sofria and _meta.json as hard links
	$(PYTHON) $(CORE)/stage_sofria_usj.py export/door43-usj $(SOFRIA_OUT)/door43 $(SOFRIA_STAGE)/door43

publish-door43: ## Upload the staged Door43 Sofria + USJ + _meta.json (make stage-door43) to cdn.bibel.wiki/door43/
	bash $(CORE)/publish-door43.sh

publish-door43-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-door43.sh

sofria-ebible: ## Convert eBible USJ to per-chapter Sofria
	node tools/usj-to-sofria/convert_batch.mjs export/ebible-usj $(SOFRIA_OUT)/ebible

stage-ebible: ## Stage eBible USJ, Sofria and _meta.json as hard links (after sofria-ebible)
	$(PYTHON) $(CORE)/stage_sofria_usj.py export/ebible-usj $(SOFRIA_OUT)/ebible $(SOFRIA_STAGE)/ebible

publish-ebible: ## Upload the staged eBible Sofria + USJ + _meta.json (make stage-ebible) to cdn.bibel.wiki/ebible/
	bash $(CORE)/publish-ebible.sh

publish-ebible-dry: ## Dry-run CDN upload (no writes)
	DRY_RUN=1 bash $(CORE)/publish-ebible.sh

stage-sofria: ## Stage USJ (<BOOK>.usj.json), Sofria (<BOOK>/<ch>.sofria.json) and _meta.json as hard links
	$(PYTHON) $(CORE)/stage_sofria_usj.py export/openbible-usj $(SOFRIA_OUT)/openbible $(SOFRIA_STAGE)/openbible
	$(PYTHON) $(CORE)/stage_sofria_usj.py export/audiobiblia-usj $(SOFRIA_OUT)/audiobiblia $(SOFRIA_STAGE)/audiobiblia

text-route: ## Generate catalog/text-route.json: each edition's canonical text and reading route (after the catalog + stage steps)
	$(PYTHON) pipeline/comparison/generate_text_route.py $(ARGS)

edition-struct: ## Generate catalog/edition-struct.json; edition_script.py first reads each edition's text (after text-route)
	$(PYTHON) pipeline/comparison/edition_script.py $(ARGS)
	$(PYTHON) pipeline/comparison/edition_struct.py --scan

catalog-split: ## Per-language copies of catalog/{audio,text,text-route,overlap}.json + dbt/_vrs/index.json (after edition-struct, before publish-catalog)
	$(PYTHON) pipeline/comparison/split_catalog.py $(ARGS)

openbible-editions: ## Add published/books/canon/licenses/path to internal-data/openbible-editions.json (after stage-sofria)
	$(PYTHON) $(CORE)/enrich_openbible_editions.py

publish-sofria: ## Upload the staged USJ + Sofria to cdn.bibel.wiki/{openbible,audiobiblia}/
	SOURCE_DIR=$(SOFRIA_STAGE)/openbible bash $(CORE)/publish-openbible.sh
	SOURCE_DIR=$(SOFRIA_STAGE)/audiobiblia bash $(CORE)/publish-audiobiblia.sh

publish-sofria-meta: ## Upload only the staged _meta.json files (with formats)
	RCLONE_EXTRA="--include */*/_meta.json" SOURCE_DIR=$(SOFRIA_STAGE)/openbible bash $(CORE)/publish-openbible.sh
	RCLONE_EXTRA="--include */*/_meta.json" SOURCE_DIR=$(SOFRIA_STAGE)/audiobiblia bash $(CORE)/publish-audiobiblia.sh

retire-verse-json-dry: ## List the verse-json chapter files that retire-verse-json would delete
	bash $(CORE)/retire-verse-json.sh

retire-verse-json: ## Delete verse-json chapters from the CDN (needs CONFIRM=delete; Sofria replaces them)
	bash $(CORE)/retire-verse-json.sh

publish-sofria-dry: ## Dry-run of publish-sofria (no writes)
	DRY_RUN=1 SOURCE_DIR=$(SOFRIA_STAGE)/openbible bash $(CORE)/publish-openbible.sh
	DRY_RUN=1 SOURCE_DIR=$(SOFRIA_STAGE)/audiobiblia bash $(CORE)/publish-audiobiblia.sh

publish-vrs-index: ## Upload only dbt/_vrs/index.json + irregular.json, verify live sha256
	$(PYTHON) $(CORE)/publish_vrs_index.py

publish-vrs-index-dry: ## Dry-run of publish-vrs-index
	$(PYTHON) $(CORE)/publish_vrs_index.py --dry-run

publish-vrs-maps: ## Upload export/_vrs/map/{org,orgw,catm,rso,vul,lxx}-to-eng.json + multiverse files, verify live sha256
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

align-pull: ## Index audio-sync's align/ (Bible text + OBS) into internal-data/{align,obs-align}-index.json, compared with their _runs/ manifests (also runs as part of dbt-metadata/obs-metadata)
	$(PYTHON) $(CORE)/pull_align_manifests.py

align-pull-dry: ## Dry-run align pull (no writes)
	$(PYTHON) $(CORE)/pull_align_manifests.py --dry-run

fetch-dbt-timing: ## Check which DBT audio filesets have DBT's own timing (one probe per testament) into internal-data/dbt-timing-index.json
	$(PYTHON) $(CORE)/fetch_dbt_timing_index.py $(ARGS)

fetch-pkf-audio: ## Index PKF's audio and timing (DBT filesets PKF timed, and PKF's own audio) from pkf/<iso>/info.json, no key, into internal-data/pkf-audio-index.json; also run by dbt-metadata
	$(PYTHON) $(CORE)/fetch_pkf_audio_index.py

fetch-obs-batches: ## Fetch OBS narration batch manifests into internal-data/obs-batches/
	$(PYTHON) $(CORE)/fetch_obs_batches.py

fetch-obs-catalog: ## Fetch door43's OBS catalog stats, text+audio (existence source of truth)
	$(PYTHON) $(CORE)/fetch_obs_catalog.py

fetch-obs-repos: ## Resolve door43 detail (content, license, audio) for every OBS language (run fetch-obs-catalog first)
	$(PYTHON) $(CORE)/fetch_obs_repos.py

fetch-obs-video: ## Fetch video-sync's YouTube ids for video-only OBS languages (also runs as part of obs-metadata)
	$(PYTHON) $(CORE)/fetch_obs_video.py

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
