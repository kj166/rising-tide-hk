"""Step 2: Attach valuations, GFA and replacement cost to each asset.

Inputs:
    data/raw/link_valuation_2026-03-31.xlsx  (sheet "Summary Report 260331")
        Money cells are plain HKD despite the "(HKD Million)" headers.
    data/raw/link_ar_fy2526_b2_financials.pdf  (GFA for the few properties that report it (pp. 220–221))
    data/interim/assets.geojson  (checked: same 130 valuation nos. and names)
    data/interim/asset_footprints.geojson  (entry_level_mpd, lowest_floor_mpd: car park type)
    config/assumptions.yaml  (`valuation`, with the config/local overlay)

Outputs:
    data/interim/asset_values.csv, one row per valuation no.:
        area_type: 'IFA' | 'GFA' | 'proposed_GFA', from the sub-table's area header.
            Area goes to ifa_m2, gfa_m2 (reported) or proposed_gfa_m2 respectively.
        gfa_method: 'reported' (B2 valuation table, pp. 220–221) or
            'estimated' (IFA / efficiency_ratio.mid; blank until the ratio is sourced).
            Blank for proposed_GFA.
        income_method: 'reported' | 'fallback_sheet' | 'yield_estimate' | 'not_applicable'.
        spaces_method: 'reported' | 'fallback_sheet' (blank when neither sheet has a number).
        status: 'operating', or 'under_development' for valuation.under_development_valuation_nos
            (no. 130, Off Anderson Road Development Site: proposed GFA and value kept for
            reference only; no income, no GFA; excluded from damage and BI; kept on the map,
            flagged).
        car_park_type: 'basement' | 'multistorey' (blank without spaces);
            car_park_type_method: 'derived_from_levels' (lowest_floor_mpd <
            entry_level_mpd - carpark_basement_below_entry_m) | 'default_multistorey'.
        building_type: 'retail' (default) | 'office' | 'industrial'
            (valuation.building_type_overrides: 126 office; 128, 129 industrial).
        status_flag: 'post_incident_drc_valuation' for valuation.post_incident_drc_valuation_nos
            (no. 94; valuation basis changed after the November 2025 fire at Wang Fuk Court;
            see Link disclosure). Full replacement cost kept. Empty for others.
        income_status: 'uncertain' for flagged rows; else from income_method: 'reported',
            'fallback' (fallback_sheet), 'estimated' (yield_estimate), 'not_applicable'.
        include_in_value_ratio: False for flagged and under-development rows (nos. 94, 130);
            the replacement cost / valuation summary uses True rows only.
        building_cost_hkd_<b>, carpark_cost_hkd_<b>, replacement_cost_hkd_<b> for b in
            low/mid/high (see below); blank while any config input is null.

Replacement cost (HK$, 4th Quarter 2025 prices, valuation.price_basis), per bound b:
    building = IFA / efficiency_ratio x cfa_to_gfa_ratio x building rate   (IFA rows)
               GFA x cfa_to_gfa_ratio x building rate                      (reported GFA rows)
               building rate by building_type (retail / office / industrial); the
               office high case uses office_high_case_rate_hkd_per_m2_cfa (prestige row)
    carpark  = car_park_spaces x carpark_m2_per_space x car park rate (by car_park_type)
    replacement = building + carpark
Each input is taken at the bound that moves cost the same way: cost low uses every input
low except efficiency_ratio, which is taken high (more IFA per m2 GFA = less GFA).
Under-development rows (no. 130) stay blank.
The efficiency ratio (an ASSUMPTION) is uniform across assets: it scales absolute losses
but cannot change asset rankings.

Loss base: replacement cost uses reported GFA or IFA / efficiency_ratio, never the
footprint area from step 1 (asset_footprints.geojson footprint_area_m2_qa is QA only).

Exposed share (loss basis, decision 2026-10-07; revises the footprint QA-only rule for this
use only): exposed_value = replacement cost x exposed_share (applied in step 5).
    n_storeys = max(1, round(floor-area height / loss_basis.storey_height_m)) from the final
        footprint's iB1000 blocks (data/interim/ib1000_extract.gpkg; see n_storeys)
    ground_floor_share = 1 / n_storeys; assets without block heights (approximate circles,
        no. 130) take the portfolio median ('portfolio_median')
    exposed_share = ground_floor_share (+ one more storey's share if car_park_type is
        'basement'), capped at 1
    Where Link reports GFA (B2 table: nos. 126, 128, 129; gfa_method 'reported'), n_storeys =
        max(1, round(GFA / ground area of the final footprint)) instead (decision 2026-10-07)
Columns: n_storeys, n_storeys_method ('floor_area_height' | 'reported_gfa' | blank),
ground_area_m2, ground_floor_share, exposed_share_method ('ib1000_height' | 'portfolio_median'),
exposed_share.

Income split (business interruption, decision 2026-10-07): retail_income_share = "Retail" / "Total"
net passing income in "HK Summary Mar 25" (31 Mar 2025; the other part is "CPS", car park income),
joined by valuation name, else by an alias in data/manual/asset_name_aliases.csv, and only where
the sheet's Val Ranking equals the valuation no.; income_split_method 'name' | 'alias' | 'none'.
The sheet books all car service centre and The Quayside office income under "Retail".

Loader rule:
    The HK section of "Summary Report 260331" is several sub-tables, each with its own
    header row (nos. 1–125; 126; 127; 128–129; 130), and columns differ between them.
    Detect each sub-table and read columns by header text, never by position.
    Stop at the "Mainland China Properties" heading (HK only).
    Record area_type per row. GFA rows get gfa_method='reported' and are NOT divided
    by efficiency_ratio. "Proposed Gross Floor Area" (no. 130) is reference only.

Income rule (annual net passing income), first that applies:
    0) status 'under_development'                             -> 'not_applicable' (blank)
    a) "Summary Report 260331" net passing income            -> 'reported'
    b) "HKSummary Mar 26" net passing income, joined by No.  -> 'fallback_sheet'
       Allowed because its income matches the main sheet exactly for nos. 1–125
       (125/125, checked 2026-09-24; re-checked at run time, the run stops if not).
    c) value x median initial yield of HK nos. 1–125         -> 'yield_estimate'
       (numeric yields only; no. 94 has '-').

Car park spaces: main sheet ('reported'), else "HKSummary Mar 26" ('fallback_sheet'),
allowed only because its spaces match the main sheet for every no. 1–125 that has both
(checked at run time; the run stops if not).

QA 2026-10-06: T Town's (no. 2) valuation row includes 1,177 car parking spaces, which
supports iB1000 block 1105714720 (car park deck on T Town North's east side) belonging to
the property.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import openpyxl
import pandas as pd

if __package__ in (None, ""):  # run as a script: make `pipeline` importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
XLSX = RAW / "link_valuation_2026-03-31.xlsx"
VALUATION_SHEET = "Summary Report 260331"
FALLBACK_SHEET = "HKSummary Mar 26"
SPLIT_SHEET = "HK Summary Mar 25"   # retail / car park (CPS) split of net passing income only
MANUAL = ROOT / "data" / "manual"
STOP_HEADING = "Mainland China Properties"
HK_NOS = range(1, 131)
YIELD_BASE_NOS = range(1, 126)  # nos. whose initial yields give the median for rule (c)

SQM_PER_SQFT = 0.09290304  # exact: 1 ft = 0.3048 m

# (header text prefix after whitespace normalisation, column, area_type). Longest prefix
# first so "Proposed Gross Floor Area" is not read as "Gross Floor Area".
HEADERS = [
    ("Proposed Gross Floor Area", "area", "proposed_GFA"),
    ("Gross Floor Area", "area", "GFA"),
    ("Internal Floor Area", "area", "IFA"),
    ("No.", "no", None),
    ("Property Name", "name", None),
    ("Property", "name", None),
    ("Car Parking Spaces", "car_park_spaces", None),
    ("Car Park Spaces", "car_park_spaces", None),
    ("Annual Net Passing Income", "net_passing_income_hkd", None),
    ("Capitalisation Rate", "cap_rate", None),
    ("Income Capitalisation Cap. Rate", "cap_rate", None),
    ("Value as at", "value_hkd", None),
    ("Analysis Initial Yield", "initial_yield", None),
]
COLUMNS = ["no", "name", "area", "area_type", "car_park_spaces", "net_passing_income_hkd",
           "cap_rate", "value_hkd", "initial_yield"]


def sqft_to_m2(x: float) -> float:
    return x * SQM_PER_SQFT


def _norm(v) -> str | None:
    return " ".join(v.split()) if isinstance(v, str) else None


def _number(v) -> float:
    """Numeric cell -> float; '-', blank or text -> NaN."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan


def _header_map(row) -> tuple[dict[str, int], str | None]:
    """Header row -> ({column: index}, area_type). Raises on header text not in HEADERS."""
    cols, area_type = {}, None
    for i, v in enumerate(row):
        text = _norm(v)
        if not text:
            continue
        hit = next((h for h in HEADERS if text.startswith(h[0])), None)
        if hit is None:
            raise ValueError(f"unknown header {text!r} in header row {row}")
        _, col, at = hit
        if col in cols:
            raise ValueError(f"two {col!r} columns in header row {row}")
        cols[col] = i
        area_type = at or area_type
    return cols, area_type


def read_schedule(path: Path, sheet: str) -> pd.DataFrame:
    """Read every sub-table of a schedule-of-values sheet up to STOP_HEADING.

    A header row is any row with a "No." cell; it sets the columns (by header text) for
    the rows below it until the next header row. Data rows have an integer in "No.".
    Columns a sub-table lacks are NaN.
    """
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    rows, cols, area_type = [], None, None
    for row in ws.iter_rows(values_only=True):
        texts = [_norm(v) for v in row]
        if STOP_HEADING in texts:
            break
        if "No." in texts:
            cols, area_type = _header_map(row)
            continue
        if cols is None or not isinstance(row[cols["no"]], int):
            continue
        rec = {c: _number(row[i]) for c, i in cols.items() if c not in ("no", "name")}
        rec["no"] = row[cols["no"]]
        rec["name"] = row[cols["name"]].strip()
        rec["area_type"] = area_type if "area" in cols else None
        rows.append(rec)
    return pd.DataFrame(rows).reindex(columns=COLUMNS)


def load_valuation(path: Path, sheet: str = VALUATION_SHEET) -> pd.DataFrame:
    """HK rows of the main valuation sheet: no, name, area (sq ft as reported), area_type
    ('IFA' | 'GFA' | 'proposed_GFA'), car_park_spaces, net_passing_income_hkd, cap_rate,
    value_hkd (plain HKD), initial_yield. Raises unless nos. are exactly 1–130, each with
    an area and a value."""
    df = read_schedule(path, sheet)
    if sorted(df.no) != list(HK_NOS):
        raise ValueError(f"expected HK nos. 1–{HK_NOS[-1]} once each, got {sorted(df.no)}")
    bad = df[df.area.isna() | df.area_type.isna() | df.value_hkd.isna()]
    if len(bad):
        raise ValueError(f"rows without area or value: {bad.no.tolist()}")
    return df.sort_values("no").reset_index(drop=True)


def check_fallback_matches(main: pd.Series, fallback: pd.Series, nos) -> int:
    """Raise unless `fallback` equals `main` for every no. in `nos` where both are numbers.
    Both Series are indexed by no. Returns the number of nos. compared."""
    both = [n for n in nos if pd.notna(main.get(n)) and pd.notna(fallback.get(n))]
    if not both:
        raise ValueError(f"no overlap to check {main.name!r} against the fallback sheet")
    diff = [n for n in both if main[n] != fallback[n]]
    if diff:
        raise ValueError(f"fallback sheet {main.name!r} differs from the main sheet for nos. {diff}")
    return len(both)


def median_initial_yield(df: pd.DataFrame, nos=YIELD_BASE_NOS) -> float:
    """Median of the numeric initial yields of `nos` (NaN, i.e. '-', ignored)."""
    y = df.set_index("no").initial_yield.reindex(list(nos)).dropna()
    if y.empty:
        raise ValueError("no numeric initial yields")
    return float(y.median())


def resolve_income(row: pd.Series, fallback_income: float, median_yield: float) -> tuple[float, str]:
    """(annual net passing income HKD, income_method) for one row, first rule that applies:
    under development -> blank; main sheet; fallback sheet; value x median yield."""
    if row.status == "under_development":
        return np.nan, "not_applicable"
    if pd.notna(row.net_passing_income_hkd):
        return row.net_passing_income_hkd, "reported"
    if pd.notna(fallback_income):
        return fallback_income, "fallback_sheet"
    return row.value_hkd * median_yield, "yield_estimate"


def resolve_spaces(main: float, fallback: float) -> tuple[float, str]:
    """(car park spaces, spaces_method): main sheet, else fallback sheet, else blank."""
    if pd.notna(main):
        return main, "reported"
    if pd.notna(fallback):
        return fallback, "fallback_sheet"
    return np.nan, ""


def estimate_gfa_m2(ifa_m2: float, efficiency_ratio: float | None) -> float:
    """GFA = IFA / efficiency ratio; NaN while the ratio is not sourced (None)."""
    if efficiency_ratio is None:
        return np.nan
    if not 0 < efficiency_ratio <= 1:
        raise ValueError(f"efficiency_ratio must be in (0, 1], got {efficiency_ratio}")
    return ifa_m2 / efficiency_ratio


BOUNDS = ("low", "mid", "high")
BUILDING_TYPES = ("retail", "office", "industrial")
# efficiency_ratio divides: the low cost bound takes the high ratio, and vice versa
EFFICIENCY_BOUND = {"low": "high", "mid": "mid", "high": "low"}


def cost_inputs(val_cfg: dict, bound: str) -> dict | None:
    """Config inputs for one cost bound, or None while any of them is null."""
    rates = val_cfg["carpark_rate_hkd_per_m2_cfa"]
    inputs = {
        "efficiency_ratio": val_cfg["efficiency_ratio"][EFFICIENCY_BOUND[bound]],
        "cfa_to_gfa_ratio": val_cfg["cfa_to_gfa_ratio"][bound],
        "building_rate": {t: val_cfg[f"{t}_rate_hkd_per_m2_cfa"][bound] for t in BUILDING_TYPES},
    }
    if bound == "high":  # office high case: prestige row (sensitivity, user decision 2026-10-06)
        inputs["building_rate"]["office"] = val_cfg["office_high_case_rate_hkd_per_m2_cfa"]
    inputs |= {
        "carpark_m2_per_space": val_cfg["carpark_m2_per_space"][bound],
        "carpark_rate": {t: rates[t][bound] for t in ("multistorey", "basement")},
    }
    flat = [v for k, v in inputs.items() if not isinstance(v, dict)] \
        + list(inputs["building_rate"].values()) + list(inputs["carpark_rate"].values())
    return None if any(v is None for v in flat) else inputs


def building_cost_hkd(area_m2: float, area_type: str, efficiency_ratio: float,
                      cfa_to_gfa_ratio: float, rate_hkd_per_m2_cfa: float) -> float:
    """Building cost (excl. car park): CFA x rate, CFA = GFA x CFA:GFA ratio; GFA = IFA / efficiency
    ratio for IFA rows, the reported area for GFA rows (not divided by the ratio)."""
    if area_type == "IFA":
        gfa = estimate_gfa_m2(area_m2, efficiency_ratio)
    elif area_type == "GFA":
        gfa = area_m2
    else:
        raise ValueError(f"no building cost for area_type {area_type!r}")
    return gfa * cfa_to_gfa_ratio * rate_hkd_per_m2_cfa


def carpark_cost_hkd(spaces: float, m2_per_space: float, rate_hkd_per_m2_cfa: float) -> float:
    """Car park cost: spaces x gross m2 per space x car park rate."""
    return spaces * m2_per_space * rate_hkd_per_m2_cfa


def car_park_type(lowest_floor_mpd: float, entry_level_mpd: float,
                  below_entry_m: float) -> tuple[str, str]:
    """('basement', 'derived_from_levels') where the lowest floor is more than below_entry_m
    under the entry level, else ('multistorey', 'default_multistorey') (incl. no levels)."""
    if pd.notna(lowest_floor_mpd) and pd.notna(entry_level_mpd) \
            and lowest_floor_mpd < entry_level_mpd - below_entry_m:
        return "basement", "derived_from_levels"
    return "multistorey", "default_multistorey"


def n_storeys(blocks, storey_m: float, contained_min: float) -> int | None:
    """Storeys of a footprint from iB1000 block heights (loss basis, decision 2026-10-07):
    max(1, round(H / storey_m)), H = floor-area height = sum(block area x block height) / ground
    area, the same footprint x height / storey height logic as the hand-footprint GFA test.
    A block lying >= contained_min of its area inside a lower-roofed block of the same footprint
    (tower on a podium) counts only from that block's roof up, so shared storeys are not counted
    twice. Blocks without BASELEVEL/ROOFLEVEL are left out; None if no block has both."""
    b = blocks[blocks.BASELEVEL.notna() & blocks.ROOFLEVEL.notna()].reset_index(drop=True)
    if b.empty:
        return None
    floor_m2 = 0.0
    for i, r in b.iterrows():
        base = r.BASELEVEL
        for j, o in b.iterrows():
            if j != i and o.ROOFLEVEL < r.ROOFLEVEL and \
                    r.geometry.intersection(o.geometry).area >= contained_min * r.geometry.area:
                base = max(base, o.ROOFLEVEL)
        floor_m2 += r.geometry.area * max(0.0, r.ROOFLEVEL - base)
    ground = b.geometry.union_all().area
    return max(1, round(floor_m2 / ground / storey_m))


def n_storeys_from_gfa(gfa_m2: float, ground_m2: float) -> int | None:
    """Storeys for an asset with Link-reported GFA (decision 2026-10-07): max(1, round(GFA /
    ground area of the final footprint)). None if either is missing or the ground area is 0."""
    if gfa_m2 is None or ground_m2 is None or pd.isna(gfa_m2) or pd.isna(ground_m2) or ground_m2 <= 0:
        return None
    return max(1, round(gfa_m2 / ground_m2))


def retail_income_share(npi_total: float, npi_retail: float) -> float:
    """'Retail' net passing income / total, clipped to [0, 1]; NaN without income. Net income is after
    opex, so a part can be negative (nos. 88, 99, 103: retail NPI < 0 -> share 0; ASSUMPTION)."""
    if pd.isna(npi_total) or pd.isna(npi_retail) or npi_total <= 0:
        return float("nan")
    return min(1.0, max(0.0, float(npi_retail) / float(npi_total)))


def read_income_split(path: Path, sheet: str = SPLIT_SHEET) -> pd.DataFrame:
    """Net passing income 'Total' and 'Retail' per property from "HK Summary Mar 25" (as at
    31 Mar 2025), columns found by header text: the header row holds "Property" and "Val Ranking";
    the row above holds the group label "Net Passing Income (HK$ pa)", whose sub-columns run to the
    next group label. Reads until the first empty row after the data (the sheet has a separate
    value breakdown below). The other group, "CPS", is car park income."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    low = lambda c: " ".join(c.split()).lower() if isinstance(c, str) else ""  # noqa: E731
    h = next(i for i, r in enumerate(rows) if any(low(c) == "property" for c in r))
    head, group = [low(c) for c in rows[h]], [low(c) for c in rows[h - 1]]
    g0 = group.index("net passing income (hk$ pa)")
    g1 = next((j for j in range(g0 + 1, len(group)) if group[j]), len(group))
    sub = {head[j]: j for j in range(g0, g1) if head[j]}
    c_no, c_name = head.index("val ranking"), head.index("property")
    out, started = [], False
    for r in rows[h + 1:]:
        if all(c is None or str(c).strip() == "" for c in r):
            if started:
                break
            continue
        started = True
        # "Val Ranking" is a merged header: its numbers sit in a column between it and "Property"
        nums = [c for c in r[c_no:c_name] if isinstance(c, (int, float))]
        if nums and r[c_name]:
            out.append({"sheet_no": int(nums[0]), "sheet_name": str(r[c_name]),
                        "npi_total": _number(r[sub["total"]]), "npi_retail": _number(r[sub["retail"]])})
    return pd.DataFrame(out)


def _name_key(s) -> str:
    return " ".join(str(s).split()).strip().rstrip("*").strip().lower()


def join_income_split(values: pd.DataFrame, split: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    """retail_income_share per valuation no.: match the sheet by valuation name, else by an alias
    in data/manual/asset_name_aliases.csv ('name' | 'alias' | 'none'). A matched sheet row must
    carry the same number (Val Ranking = valuation no.), else stop: never guessed."""
    by_name = {_name_key(n): r for r, n in zip(split.itertuples(), split.sheet_name)}
    rows = []
    for no, name in zip(values.valuation_no, values.name):
        hit, how = by_name.get(_name_key(name)), "name"
        if hit is None:
            how = "alias"
            for a in aliases.loc[aliases.valuation_no == no, "alias"]:
                hit = by_name.get(_name_key(a))
                if hit is not None:
                    break
        if hit is None:
            rows.append({"valuation_no": no, "retail_income_share": float("nan"), "income_split_method": "none"})
            continue
        if hit.sheet_no != no:
            raise ValueError(f"income split: no. {no} matched sheet row {hit.sheet_no} ({hit.sheet_name!r}) by {how}")
        rows.append({"valuation_no": no, "retail_income_share": retail_income_share(hit.npi_total, hit.npi_retail),
                     "income_split_method": how})
    return pd.DataFrame(rows)


def exposed_shares(df: pd.DataFrame) -> pd.DataFrame:
    """ground_floor_share = 1 / n_storeys; rows without n_storeys (approximate circles, no
    heights) take the median share of the rest ('portfolio_median'). exposed_share = ground
    floor share, plus one more storey's share for a basement car park, capped at 1."""
    out = df[["valuation_no"]].copy()
    gfs = 1.0 / df.n_storeys.astype(float)
    med = float(gfs.median())
    out["ground_floor_share"] = gfs.fillna(med)
    out["exposed_share_method"] = np.where(gfs.isna(), "portfolio_median", "ib1000_height")
    extra = np.where(df.car_park_type.eq("basement"), out.ground_floor_share, 0.0)
    out["exposed_share"] = np.minimum(1.0, out.ground_floor_share + extra)
    return out


def footprint_storeys(footprints: pd.DataFrame, gpkg: Path, storey_m: float, contained_min: float) -> pd.DataFrame:
    """n_storeys per asset from the final footprint's iB1000 blocks (block_ids; sheet pieces
    unioned by BUILDINGID). Approximate-circle assets have no blocks -> NaN."""
    ids = {int(x) for s in footprints.block_ids.dropna() for x in str(s).split(",") if x}
    blocks = gpd.read_file(gpkg, layer="Building", columns=["BUILDINGID", "BASELEVEL", "ROOFLEVEL"])
    blocks = blocks[blocks.BUILDINGID.astype("int64").isin(ids)]
    blocks = blocks.dissolve("BUILDINGID", aggfunc="first").reset_index()
    blocks["BUILDINGID"] = blocks.BUILDINGID.astype("int64")
    rows = []
    for r in footprints.itertuples():
        n, ground = None, None
        if r.footprint_method == "ib1000_footprint" and isinstance(r.block_ids, str):
            mine = blocks[blocks.BUILDINGID.isin([int(x) for x in r.block_ids.split(",") if x])]
            n = n_storeys(mine, storey_m, contained_min)
            ground = float(mine.geometry.union_all().area) if len(mine) else None
        rows.append({"valuation_no": r.valuation_no, "n_storeys": n, "ground_area_m2": ground})
    return pd.DataFrame(rows)


def replacement_costs(r: dict, val_cfg: dict) -> dict:
    """building/carpark/replacement cost columns for one output row (all bounds)."""
    out = {}
    for b in BOUNDS:
        inp = cost_inputs(val_cfg, b)
        building = carpark = np.nan
        if inp is not None and r["status"] != "under_development":
            area = r["ifa_m2"] if r["area_type"] == "IFA" else r["gfa_m2"]
            building = building_cost_hkd(area, r["area_type"], inp["efficiency_ratio"],
                                         inp["cfa_to_gfa_ratio"], inp["building_rate"][r["building_type"]])
            spaces = r["car_park_spaces"]
            carpark = 0.0 if spaces == 0 else carpark_cost_hkd(
                spaces, inp["carpark_m2_per_space"], inp["carpark_rate"].get(r["car_park_type"], np.nan))
        out[f"building_cost_hkd_{b}"] = building
        out[f"carpark_cost_hkd_{b}"] = carpark
        out[f"replacement_cost_hkd_{b}"] = building + carpark
    return out


def build_values(main: pd.DataFrame, fallback: pd.DataFrame, val_cfg: dict,
                 levels: pd.DataFrame | None = None) -> pd.DataFrame:
    """One output row per valuation no. (see module docstring for the columns).
    `levels`: valuation_no, entry_level_mpd, lowest_floor_mpd (step 1); None = no levels."""
    fb = fallback.set_index("no")
    m = main.set_index("no")
    check_fallback_matches(m.net_passing_income_hkd, fb.net_passing_income_hkd, YIELD_BASE_NOS)
    check_fallback_matches(m.car_park_spaces, fb.car_park_spaces, YIELD_BASE_NOS)
    med = median_initial_yield(main, YIELD_BASE_NOS)
    ratio = val_cfg["efficiency_ratio"]["mid"]
    dev = set(val_cfg["under_development_valuation_nos"])
    flagged = set(val_cfg.get("post_incident_drc_valuation_nos") or [])
    types = {int(k): v for k, v in (val_cfg.get("building_type_overrides") or {}).items()}
    if set(types.values()) - set(BUILDING_TYPES):
        raise ValueError(f"unknown building_type in overrides: {types}")
    lv = (levels.set_index("valuation_no") if levels is not None
          else pd.DataFrame(columns=["entry_level_mpd", "lowest_floor_mpd"]))

    out = []
    for r in main.itertuples(index=False):
        r = pd.Series(r._asdict())
        r["status"] = "under_development" if r.no in dev else "operating"
        income, income_method = resolve_income(r, fb.net_passing_income_hkd.get(r.no, np.nan), med)
        spaces, spaces_method = resolve_spaces(r.car_park_spaces, fb.car_park_spaces.get(r.no, np.nan))
        area_m2 = sqft_to_m2(r.area)
        ifa_m2 = area_m2 if r.area_type == "IFA" else np.nan
        proposed = area_m2 if r.area_type == "proposed_GFA" else np.nan
        if r.area_type == "GFA":
            gfa_m2, gfa_method = area_m2, "reported"
        elif r.area_type == "IFA":
            gfa_m2, gfa_method = estimate_gfa_m2(ifa_m2, ratio), "estimated"
        else:
            gfa_m2, gfa_method = np.nan, ""
        if r.status == "under_development":
            gfa_m2, gfa_method = np.nan, ""
        cp_type = cp_method = ""
        if r.status != "under_development" and pd.notna(spaces) and spaces > 0:
            cp_type, cp_method = car_park_type(
                lv.lowest_floor_mpd.get(r.no, np.nan), lv.entry_level_mpd.get(r.no, np.nan),
                val_cfg["carpark_basement_below_entry_m"])
        row = {
            "valuation_no": r.no, "name": r["name"], "status": r.status,
            "area_type": r.area_type, "ifa_m2": ifa_m2, "gfa_m2": gfa_m2,
            "gfa_method": gfa_method, "proposed_gfa_m2": proposed,
            "car_park_spaces": spaces, "spaces_method": spaces_method,
            "car_park_type": cp_type, "car_park_type_method": cp_method,
            "building_type": "" if r.status == "under_development" else types.get(r.no, "retail"),
            "net_passing_income_hkd": income, "income_method": income_method,
            "cap_rate": r.cap_rate, "initial_yield": r.initial_yield,
            "value_hkd": r.value_hkd,
            "status_flag": POST_INCIDENT_FLAG if r.no in flagged else "",
            "income_status": "uncertain" if r.no in flagged else INCOME_STATUS[income_method],
            "include_in_value_ratio": r.no not in flagged and r.status != "under_development",
        }
        row.update(replacement_costs(row, val_cfg))
        out.append(row)
    return pd.DataFrame(out)


INCOME_STATUS = {"reported": "reported", "fallback_sheet": "fallback",
                 "yield_estimate": "estimated", "not_applicable": "not_applicable"}
POST_INCIDENT_FLAG = "post_incident_drc_valuation"


def value_ratio_summary(values: pd.DataFrame, bound: str = "mid",
                        high: float = 2.0, low: float = 0.1) -> dict:
    """Replacement cost / valuation over rows with include_in_value_ratio True and a cost:
    n, min, median, max, and the valuation nos. above `high` or below `low`."""
    v = values[values.include_in_value_ratio.astype(bool)]
    r = (v[f"replacement_cost_hkd_{bound}"] / v.value_hkd).dropna()
    nos = v.loc[r.index, "valuation_no"]
    return {"n": len(r), "min": r.min(), "median": r.median(), "max": r.max(),
            "above_high": nos[r > high].tolist(), "below_low": nos[r < low].tolist()}


def check_against_assets(values: pd.DataFrame, assets: pd.DataFrame) -> None:
    """Raise unless step 1's assets have the same valuation nos. and names."""
    a = assets.drop_duplicates("valuation_no").set_index("valuation_no").name
    v = values.set_index("valuation_no").name
    if set(a.index) != set(v.index):
        raise ValueError(f"valuation nos. differ from assets.geojson: "
                         f"{sorted(set(a.index) ^ set(v.index))}")
    diff = [n for n in v.index if a[n] != v[n]]
    if diff:
        raise ValueError(f"names differ from assets.geojson for nos. {diff}")


def main() -> None:
    cfg = load_config("assumptions")
    main_df = load_valuation(XLSX)
    fallback = read_schedule(XLSX, FALLBACK_SHEET)
    levels = gpd.read_file(INTERIM / "asset_footprints.geojson", ignore_geometry=True)[
        ["valuation_no", "entry_level_mpd", "lowest_floor_mpd"]]
    values = build_values(main_df, fallback, cfg["valuation"], levels)
    lb = cfg["loss_basis"]
    fps = gpd.read_file(INTERIM / "asset_footprints.geojson", ignore_geometry=True)
    st = footprint_storeys(fps, INTERIM / "ib1000_extract.gpkg", lb["storey_height_m"], lb["contained_block_min_share"])
    values = values.merge(st, on="valuation_no", how="left")
    # Link-reported GFA (B2 table): n_storeys = GFA / ground area (decision 2026-10-07)
    rep = values.gfa_method.eq("reported") & values.ground_area_m2.notna()
    values["n_storeys_method"] = np.where(values.n_storeys.isna(), "", "floor_area_height")
    values.loc[rep, "n_storeys"] = [n_storeys_from_gfa(g, a) for g, a in
                                    zip(values.loc[rep, "gfa_m2"], values.loc[rep, "ground_area_m2"])]
    values.loc[rep, "n_storeys_method"] = "reported_gfa"
    split = join_income_split(values, read_income_split(XLSX), pd.read_csv(MANUAL / "asset_name_aliases.csv"))
    values = values.merge(split, on="valuation_no", how="left")
    values = values.merge(exposed_shares(values), on="valuation_no", how="left")
    assets = gpd.read_file(INTERIM / "assets.geojson", ignore_geometry=True)
    check_against_assets(values, assets)
    out = INTERIM / "asset_values.csv"
    values.to_csv(out, index=False)

    print(f"rows loaded: {len(values)} -> {out.relative_to(ROOT)}")
    for col in ("status", "area_type", "gfa_method", "income_method", "spaces_method",
                "car_park_type_method", "building_type"):
        counts = values[col].replace("", "(blank)").value_counts().to_dict()
        print(f"{col}: {counts}")
    print(f"median initial yield (nos. 1–125, numeric): {median_initial_yield(main_df):.6f}")
    t = values.set_index("valuation_no").loc[2]
    print(f"T Town (no. 2) car park spaces: {t.car_park_spaces:.0f} ({t.spaces_method})")
    basement = values.loc[values.car_park_type == "basement", "valuation_no"].tolist()
    print(f"car_park_type basement: nos. {basement}")
    print(f"income_split_method: {values.income_split_method.value_counts().to_dict()}")
    print(values.loc[values.n_storeys_method == "reported_gfa", ["valuation_no", "name", "gfa_m2", "ground_area_m2",
                                                                 "n_storeys", "exposed_share"]].to_string(index=False))
    print(f"exposed_share_method: {values.exposed_share_method.value_counts().to_dict()}; "
          f"median ground_floor_share {values.ground_floor_share.median():.3f}")
    print(f"status_flag: nos. {values.loc[values.status_flag != '', 'valuation_no'].tolist()}; "
          f"include_in_value_ratio False: nos. "
          f"{values.loc[~values.include_in_value_ratio, 'valuation_no'].tolist()}")
    for b in BOUNDS:
        print(f"replacement_cost_hkd_{b} total: {values[f'replacement_cost_hkd_{b}'].sum():,.0f}")
    vr = value_ratio_summary(values)
    print(f"replacement cost (mid) / value, {vr['n']} rows: min {vr['min']:.2f} "
          f"median {vr['median']:.2f} max {vr['max']:.2f}; > 2x: {vr['above_high']}; "
          f"< 10%: {vr['below_low']}")
    missing = [b for b in BOUNDS if cost_inputs(cfg["valuation"], b) is None]
    blank = values.replacement_cost_hkd_mid.isna().sum()
    print(f"replacement_cost_hkd_mid blank: {blank}/{len(values)}"
          + (f" (config inputs null for bounds {missing})" if missing else ""))


if __name__ == "__main__":
    main()
