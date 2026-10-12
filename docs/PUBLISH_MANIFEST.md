# Publish manifest

The public repo is created later (Week 6) as a **new repo with one commit**, built from
this manifest. This working repo (and its private backup) keeps full history and is
never made public.

Rule (2026-09-24): code, our derived results and citations only. Individual cited
figures with page refs are fine in public docs; tables and verbatim passages from
restricted sources (publication = cite-only or internal in data/SOURCES.md) are not.

## Public

| path | note |
|---|---|
| `pipeline/` | pipeline code; config values are tracked `null`s, so it cannot run end to end without the private inputs |
| `tests/test_07_export.py`, `tests/test_publish_manifest.py`, `tests/conftest.py` | public tests (decision 2026-10-12): the export contract and the publication scan; conftest skips tests whose only failure is a missing private input. The site tests (Playwright) are in `site/tests/`. |
| `Makefile`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore` | build and environment |
| `config/assumptions.yaml`, `config/scenarios.yaml` | tracked config only: keys, `null` for transcribed values, sources and page refs; no `config/local/` overlay |
| `README.md` | rendered by `scripts/build_public.py` from `publish/README.template.md` with figures from the export (replaces the working README); incl. "Third-party data must be obtained from the sources listed in data/SOURCES.md." |
| `LICENSE`, `LICENSE-DATA.md` | generated: copied from `publish/` (MIT for code; CC BY-NC 4.0 for derived data, site text and charts) |
| `.github/workflows/pages.yml` | generated: copied from `publish/pages.yml` (GitHub Pages build and deploy) |
| `data/SOURCES.md` | citations, licence / terms, publication status |
| `data/manual/asset_name_aliases.csv` | our own mapping; page refs only for Link |
| `docs/methodology*` (to be written) | methodology page |
| `docs/PUBLISH_MANIFEST.md` | this file |
| `site/` (SvelteKit source, `site/public/img/`, `site/public/og.png`, Playwright tests in `site/tests/`) and `site/public/data/*.json|geojson` | the website and its derived outputs (incl. `flood_extents.geojson`, our bathtub polygons from the LandsD 5 m DTM, and `terrain/` tiles derived from the same DTM, attribution "Terrain derived from the LandsD 5 m Digital Terrain Model, HKSAR Government, via the CSDI Portal") |
| `data/manual/photo_credits.csv` | photo credits, captions, alt text (our record; Commons metadata) |
| `data/processed/` derived outputs | only those exported to the site, and nothing derived from an `internal` source; HLC-derived outputs only under the HLC conditions below |

Checked by `tests/test_publish_manifest.py`: no file in this table may contain an mPD water or sill level next to a
named asset (asset name or "no. N").

## Site levels (decision 2026-10-12)

Absolute ground, entrance, floor or sill levels are never published as numbers. Results are published as return periods with their ±0.15 m range, which bound those levels; this is accepted because the levels derive from open CEDD LiDAR and the published form carries its uncertainty. Relative margins in cm are published only for The Quayside and Chai Wan Car Service Centre.

Checked by `tests/test_07_export.py` (`test_export_margins_exception_only_two_named_assets`: no `*_mpd` / `*_mcd` key except the cited HKO gauge reading; cm margins only for nos. 126 and 129).

## Public repo and build (decision 2026-10-12)

- Name `rising-tide-hk`; GitHub Pages URL `https://<github-username>.github.io/rising-tide-hk/`; `BASE_PATH=/rising-tide-hk`.
  `SITE_URL` is supplied at build time with the real username (the Pages workflow derives it from the repository owner,
  or takes the `SITE_URL` repository variable); a build with `BASE_PATH` and no `SITE_URL` fails with a message.
- `make public` (scripts/build_public.py) builds a fresh tree in `../rising-tide-hk-public` from this manifest, adds
  README.md, LICENSE, LICENSE-DATA.md and .github/workflows/pages.yml from `publish/`, runs the gates (placeholder markers in site copy,
  never-public paths, identity, config/local and Link values, site levels, LandsD logo and aerial line, licence rows),
  then `git init` and one commit "Initial public release". It refuses to commit unless PUBLIC_GIT_NAME and
  PUBLIC_GIT_EMAIL are set and the email ends in `@users.noreply.github.com` (dry runs included). It never pushes. `make public-verify` runs pytest, the base-path build,
  Playwright (SHOW_LANDSD_AERIAL=false) and a link check on that tree. Number-gate exemptions (coincidences and figures
  already approved for publication, no values) live in `publish/gate_exemptions.yaml` and are printed on every run.

## Licences (decision 2026-10-12)

Code is MIT; derived data files and the site's text and charts are CC BY-NC 4.0, because the GEO Historical
Landslide Catchments data are licensed to this project for non-commercial use only, so the published derived data
cannot be more open. Third-party files keep their own licence and attribution. Every file in the public tree must
match a row below (glob; `**` = any depth); `make public` fails otherwise. First matching row wins.

| pattern | licence | note |
|---|---|---|
| `site/public/data/hlc.geojson` | third-party (attribution) | GEO, CEDD Historical Landslide Catchments; GEO Open Data Portal Terms of Use; non-commercial, educational and research use (GEO confirmation 2026-10-06); reprojected and subset only |
| `site/public/data/terrain/**` | CC BY-NC 4.0 | derived from the LandsD 5 m DTM; attribution "Terrain derived from the LandsD 5 m Digital Terrain Model, HKSAR Government, via the CSDI Portal" |
| `site/public/data/footprints.geojson` | CC BY-NC 4.0 | derived from iB1000 (LandsD, CSDI); iB1000 attribution required |
| `site/public/data/*` | CC BY-NC 4.0 | our derived results |
| `site/public/og.png` | third-party (attribution) | adaptation of Wikimedia Commons photo #3 (Benh LIEU SONG (Flickr), CC BY-SA 4.0); credited in the image |
| `site/public/img/landsd_logo.jpg` | third-party (attribution) | LandsD logo, Imagery Map API terms; in the public tree only once pre-push item 7 is ticked (decision 2026-10-12) |
| `site/public/img/photos.json` | CC BY-NC 4.0 | our record of photo credits, captions and alt text |
| `site/public/img/wm*` | third-party (attribution) | Wikimedia Commons: #1 Mk2010 CC BY-SA 3.0; #3 Benh LIEU SONG (Flickr) CC BY-SA 4.0; #4 Wpcpey CC BY-SA 4.0; #5 Anthony Ivanoff CC0; crops are adaptations under the photo's licence (data/manual/photo_credits.csv) |
| `site/public/robots.txt` | MIT | build file |
| `site/src/**` | MIT (code) + CC BY-NC 4.0 (page text and charts) | site source; the rendered text and charts are CC BY-NC 4.0 |
| `site/**` | MIT | build config, scripts, Playwright tests |
| `pipeline/**`, `tests/**`, `.github/**` | MIT | code |
| `Makefile`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `LICENSE` | MIT | build and environment; MIT licence text |
| `config/*.yaml` | MIT | our assumptions with sources; transcribed values are `null` |
| `data/processed/.gitkeep` | MIT | placeholder |
| `README.md`, `LICENSE-DATA.md`, `docs/*.md`, `data/SOURCES.md` | CC BY-NC 4.0 | our text |
| `data/manual/*.csv` | CC BY-NC 4.0 | our mappings and photo-credit record |

## iB1000 (resolved 2026-10-08)

iB1000 is an Open Digital Map (LandsD Annual Open Data Plan); its free download is governed by the CSDI
Portal Terms of Use (distribution and reproduction allowed, commercial and non-commercial, with the
Government and the CSDI Portal identified as source and Government IP acknowledged). Footprint polygons
and iB1000-derived points may be exported to the site with the attribution above. Saved terms:
`data/raw/ib1000/licence/` (SOURCES.md).

## HLC conditions (GEO confirmation, 2026-10-06)

Basis: GEO's written confirmation (2026-10-06) that the GEO Open Data Portal Terms of Use
permit this use, subject to the standard disclaimer (reply in
`docs/internal/licences/geo_hlc_permission.md`, internal, never public; Terms of Use incl.
its "Disclaimer and Limitation of Liability" section: see data/SOURCES.md). Scope: "use,
copy, and redistribute the dataset for non-commercial, educational and research purposes".

**Redistribution:** HLC data in `site/public/data/` is downloadable by visitors. That is
redistribution, and it is covered by this scope.

GEO's conditions (wording of GEO's reply):

1. The source is clearly acknowledged as "Geotechnical Engineering Office, Civil
   Engineering and Development Department" or "GEO, CEDD".
2. The dataset is not used in a manner that implies official endorsement by the GEO or CEDD.
3. No modification is made to the dataset that could misrepresent its original meaning or
   context.

Our implementation of GEO's conditions (our rules, not GEO's wording):

- **Attribution (1):** the text exactly as above, shown on every map layer or chart that
  uses HLC and on the sources page.
- **No implied endorsement (2):** the site footer/methodology says "Independent student
  project; not endorsed by GEO or CEDD." No GEO/CEDD logos.
- **No misrepresenting modification (3):** allowed: reprojection (e.g. to EPSG:4326),
  spatial subsetting to the study area, and display styling. Not allowed: changing
  attribute values, merging/reclassifying records, or presenting our derived landslide
  score as GEO data.
- **Use:** non-commercial, educational/research only.
- **Sources page** cites the GEO Open Data Portal Terms of Use and its disclaimer.
  Planned sources-page text:
  > Historical Landslide Catchments: Geotechnical Engineering Office, Civil Engineering and
  > Development Department (GEO, CEDD), via the GEO Data Portal. Intellectual property
  > rights in the data belong to the HKSAR Government. Used under the GEO Data Portal
  > Terms of Use.

## Never public

- `docs/internal/` (notes, disclosure extract, feasibility)
- `data/manual_local/` (third-party transcriptions)
- `config/local/` (transcribed config values)
- `data/raw/` (downloads)
- `CLAUDE.md`, `docs/ROADMAP.md`, `docs/PROMPTS.md` (working files; decision 2026-09-24)
- `data/interim/`
- `notebooks/` (revisited in Week 6)
- `tests/test_03_hazards.py`, `tests/test_05_impact.py`, `tests/test_hazard_layers.py`, `tests/test_impact_heat.py`,
  `tests/test_02_values.py`, `tests/test_hand_footprint_review.py` (decision 2026-10-12: they embed transcribed
  third-party tables (PWDM, HKO, JRC, tariffs) or a Link input (reported GFA); kept as they are, not rewritten)
- `tests/test_01_assets.py`, `tests/test_06_ranking.py`, `tests/test_config.py`, `tests/test_datum.py`,
  `tests/test_hazard_extents.py`, `tests/test_terrain_tiles.py`, `tests/test_smoke.py`, `tests/test_site_copy.py`,
  `tests/test_build_public.py`, `tests/test_colour_check.py`, `tests/test_fetch_terrain.py`, `tests/test_geocode_als.py`,
  `tests/test_geocode_district_check.py`, `tests/test_triage_scripts.py`, `tests/test_web_photos.py` (decision
  2026-10-12: public tests are the export contract, the publication scan and the site tests only; the rest are
  pipeline unit tests or test private scripts)
- `scripts/`, `site-mockup/`, `docs/DESIGN_BRIEF.md` (decision 2026-10-12)
- `publish/` (sources of the generated public files and the gate exemptions)

The Claude Code workflow is described for the public in the Method page's "How I built this" section (decision
2026-10-12), not by publishing the working files.

## Pre-push audit (Week 6)

1. Copy only the paths under "Public" into a fresh directory; `git init`; one commit (`make public`, see above).
2. Check that no path from "Never public" is present.
3. Search every file for tables or verbatim passages from `cite-only` / `internal`
   sources (Link, CEDD/PWDM, DSD, HKO); keep individual cited figures with page refs.
4. HLC: the GEO layer's attribute values and records match the source (only reprojection,
   subsetting to the study area and styling applied; nothing merged or reclassified); every HLC map
   layer / chart and the sources page carry the GEO, CEDD attribution; the footer/methodology
   carries the no-endorsement line; no GEO/CEDD logos; our landslide score is labelled as our
   own derived metric; the sources page cites the GEO Open Data Portal Terms of Use and its
   disclaimer; GEO's reply (docs/internal/licences/) is not in the copy.
5. iB1000 licence resolved 2026-10-08 (Open Digital Map; CSDI Terms of Use; NOTES). Check the iB1000
   attribution is on the map and the sources page: "Building footprints derived from iB1000 Digital
   Topographic Map, Lands Department, HKSAR Government, via the CSDI Portal. Intellectual property rights
   in the data belong to the HKSAR Government."
6. `uv run pytest` passes in the fresh copy.
7. [ ] LandsD logo confirmed by email, OR set SHOW_LANDSD_AERIAL=false before deploy. (Tick the box only after LandsD
   confirms. While it is unticked (decision 2026-10-12), `make public` leaves `site/public/img/landsd_logo.jpg` out of the
   tree and strips the LandsD aerial marker blocks (aerial thumbnail, logo, the footer's aerial attribution line and the
   Imagery Map API terms section of SOURCES.md) from the public copy, and fails if either remains or SHOW_LANDSD_AERIAL is not false.) (Aerial thumbnail and logo on the
   asset panel; `site/.env` / build environment; both states covered by the Playwright smoke test.)
8. docs/DESIGN_BRIEF.md stays private (decision 2026-10-12; it quotes The Quayside water levels in section 9).
