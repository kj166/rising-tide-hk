PY := uv run python

.PHONY: public public-verify data geocode assets assets-pilot footprint-rules apply-seeds apply-touching model site-assets site site-build serve site-test mockup all test clean

# Cache only, no network: rebuilds data/interim/geocode_accepted.csv, which step 1 reads.
# The ALS fetch (scripts/geocode_als.py without --parse) is run by hand on an HK connection.
geocode:
	$(PY) scripts/geocode_als.py --parse

# Step 1 reads iB1000 sheets and LiDAR tiles from data/raw; they are downloaded by hand with
# scripts/fetch_terrain.py (--plan, --ib1000 --delete-zips, then --lidar after step 1 lists
# the tiles in data/interim/lidar_tiles_needed.csv, then --sources).
assets: geocode
	$(PY) pipeline/01_assets.py

assets-pilot: geocode
	$(PY) pipeline/01_assets.py --pilot

# rule_v1 decisions on touching unnamed blocks (data/manual/footprint_overrides.csv), then step 1
footprint-rules:
	$(PY) scripts/footprint_rules.py
	$(PY) pipeline/01_assets.py

# "yes" rows of data/manual/seed_decisions.csv -> iB1000 alias rows; rerun step 1, then
# rule_v1 on the new footprints' touching blocks (+ step 1 again)
apply-seeds:
	$(PY) scripts/apply_seed_suggestions.py
	$(PY) pipeline/01_assets.py
	$(MAKE) footprint-rules

# Decisions typed into data/interim/touching_review.csv -> footprint_overrides.csv, then step 1.
# ACCEPT_SUGGESTIONS=1 also applies every remaining "include" suggestion (rows not marked).
apply-touching:
	$(PY) scripts/apply_touching_review.py $(if $(filter 1,$(ACCEPT_SUGGESTIONS)),--accept-suggestions)
	$(PY) pipeline/01_assets.py

data: assets
	$(PY) pipeline/02_values.py
	$(PY) pipeline/03_hazards.py

model:
	$(PY) pipeline/04_exposure.py
	$(PY) pipeline/05_impact.py
	$(PY) pipeline/06_ranking.py

# Rising Tide site (SvelteKit, site/): export -> web photos -> OG image -> dev server or static build.
# GitHub Pages: BASE_PATH=/repo-name SITE_URL=https://user.github.io/repo-name make site-build
# Until LandsD confirms the logo file: SHOW_LANDSD_AERIAL=false make site-build (PUBLISH_MANIFEST item 7).
# Without the model outputs (public repo: no Link inputs) the site runs on the published data in site/public/data.
MODEL_OUT := data/interim/asset_values.csv
site-assets:
	@if [ -f $(MODEL_OUT) ]; then $(PY) pipeline/07_export.py && $(PY) scripts/web_photos.py; \
	else echo "Model outputs not present ($(MODEL_OUT)): using the published data in site/public/data as is."; fi
	cd site && npm ci --no-audit --no-fund
	@if [ -f $(MODEL_OUT) ]; then cd site && npm run og; fi

site: site-assets
	cd site && npm run dev

site-build: site-assets
	cd site && npm run build

serve: site-build
	cd site && npm run serve

# Playwright smoke test (builds with SHOW_LANDSD_AERIAL true and false)
site-test: site-assets
	cd site && npm run test:e2e

# Public repo dry run / build (decision 2026-10-12): fresh tree in ../rising-tide-hk-public, gates, one commit.
# Never pushes. ALLOW_TODO=1 is for dry runs only. The deploy uses SHOW_LANDSD_AERIAL=false until LandsD confirms.
public:
	$(PY) scripts/build_public.py $(if $(ALLOW_TODO),--allow-todo,)

# Verify the public tree: pytest, site build under BASE_PATH=/rising-tide-hk (SITE_URL from the environment),
# Playwright with SHOW_LANDSD_AERIAL=false, link check.
public-verify:
	$(PY) scripts/build_public.py --verify

all: data model site-build

test:
	uv run pytest


# Phase 1 redesign mockups (docs/DESIGN_BRIEF.md): export (incl. terrain tiles) + web photos, then dev server on :5174
mockup:
	$(PY) pipeline/07_export.py
	$(PY) scripts/web_photos.py --out site-mockup/public/img
	cd site-mockup && npm ci --no-audit --no-fund && npm run dev -- --port 5174

# Never touches data/raw.
clean:
	find data/interim data/processed -mindepth 1 ! -name .gitkeep -exec rm -rf {} +
	rm -rf site/public/data
