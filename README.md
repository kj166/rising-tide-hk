# Rising Tide: physical climate risk in Link REIT's Hong Kong portfolio

An independent student project that estimates physical climate risk (coastal flooding, rain flooding,
landslides and heat) for the 130 Hong Kong properties of Link REIT under the 1995–2014
climate, SSP2-4.5 and SSP5-8.5 to 2050 (SSP5-8.5 to 2100 as a sensitivity), and compares the result with
Link's own climate disclosure. The results are published as a static website built from this repository.

It is written for readers who want to see what a property-level physical risk assessment of a listed
Hong Kong landlord looks like: students, analysts and investors interested in climate risk disclosure,
and anyone checking how the numbers were made.

Independent student project; not endorsed by GEO, CEDD, LandsD, HKO or Link REIT.

## Findings

All figures below come from the published export in `site/public/data/` (2050 = SSP2-4.5, 2041–2060;
money in HK$, nominal, two significant figures, shown as ranges).

1. **Small but concentrated.** 17 of Link's 129 assessed Hong Kong properties
   carry all of its modelled coastal flood risk by 2050, and three of them (Chai Wan Car Service Centre, Hung Hom Car Service Centre and Lek Yuen Plaza) carry
   42–56% of it.
2. **Rising.** Expected annual coastal flood loss goes from HK$1.8–6.8M in the 1995–2014 climate to
   HK$7.2–23M by 2050, 3.4–4.0 times as much, or 0.092–0.3% of Link's Hong Kong net income.
3. **Barriers can pay for themselves.** A 0.5 m flood barrier at the 10 most
   exposed properties pays for itself at any cost below HK$40–64M over 25 years
   (discounted at 4% a year). No Hong Kong barrier costs were found, so these are
   break-even budgets, not prices.

## What is (and is not) in this repository

**Link inputs are not included.** Link's valuation report, rents, floor areas and every other
third-party table we transcribed (`config/local/`, `data/manual_local/`, `data/raw/`) stay private.
The repository holds our code, our derived results (rounded and banded) and citations.
Third-party data must be obtained from the sources listed in `data/SOURCES.md`.

What you **can** re-run from this repository:

- **The website**, from the published data in `site/public/data/`: `make site` (or
  `cd site && npm ci && npm run dev`). Needs Node.js and npm. `make site` detects that the model outputs
  are absent and uses the published data as is.
- **The published tests**: `uv sync && uv run pytest` (Python 3.11+ with uv) runs the export-contract and
  publication-scan tests against `site/public/data/`; a test that needs a private input is skipped.
  `cd site && npm run test:e2e` builds the site and runs the site tests (Playwright).

Pipeline unit tests are not published because they contain third-party tables; the export-contract, publication-scan
and site tests are.

What you **cannot** re-run from this repository:

- **The model run** (`make data`, `make model` and the export step `pipeline/07_export.py`). The pipeline code is
  published, but it cannot be run end to end from this repository: it needs
  Link's valuation report (as at 31 March 2026) and the transcribed configuration values in
  `config/local/`, which are not included. The tracked `config/assumptions.yaml` and
  `config/scenarios.yaml` hold `null` for those values, with their source and page reference.

## Limits

- **Still-water coastal flooding only.** Extreme sea level plus sea-level rise and storm surge
  increase; waves and wave overtopping are not modelled, so seafront results are a lower bound.
- **Screening indicators.** The rain-flood and landslide layers are screening indicators, not
  probabilities or losses.
- **±0.15 m.** Ground, entrance and floor levels come from CEDD 2020 LiDAR, whose vertical accuracy is not
  stated; every coastal result is computed with the onset level ±0.15 m and shown as a range. Absolute
  site levels are not published.
- Business interruption uses Hazus maximum restoration times (US defaults), an upper bound; expected
  annual loss is shown with and without events rarer than 1-in-200 years.

The website's Method page explains every step and lists all sources.

## Licences

- **Code** (Python pipeline, tests, site source, build files): MIT, see `LICENSE`.
- **Derived data files and the website's text and charts**: CC BY-NC 4.0, see `LICENSE-DATA.md`.
  Non-commercial because the GEO Historical Landslide Catchments data are licensed to this project for
  non-commercial, educational and research use only.
- **Third-party material** keeps its own licence and attribution: GEO's landslide catchments
  (`site/public/data/hlc.geojson`), and Wikimedia Commons photos and their crops.
  The licence of every file is listed in `docs/PUBLISH_MANIFEST.md`.

## Attributions

- Historical Landslide Catchments: Geotechnical Engineering Office, Civil Engineering and Development
  Department (GEO, CEDD). Our landslide indicator is our own derived metric, not GEO data.
- Building footprints derived from iB1000 Digital Topographic Map, Lands Department, HKSAR Government,
  via the CSDI Portal. Intellectual property rights in the data belong to the HKSAR Government.
- Terrain derived from the LandsD 5 m Digital Terrain Model, HKSAR Government, via the CSDI Portal. Ground levels: CEDD 2020 LiDAR Digital Terrain Model via the CSDI Portal.
- Climate projection figures: Hong Kong Observatory. The Government of the HKSAR owns the intellectual
  property rights; figures are cited, not reproduced as tables.
- Basemap: OpenFreeMap © OpenMapTiles, data from OpenStreetMap contributors.
- Photos: Wikimedia Commons; credits in `data/manual/photo_credits.csv` and under each photo on the site.

Built with Claude Code.
