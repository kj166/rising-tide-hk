"""Step 6: Composite risk ranking and adaptation break-even (decisions 2026-10-07).

Inputs:
    data/processed/impact.csv                      coastal EAL per asset x scenario (step 5)
    data/processed/hazards/rain_assets.csv         rain_index_cont_<scenario> (step 3)
    data/processed/hazards/landslide_assets.csv    landslide_score 0-4 (step 3)
    data/interim/asset_values.csv                  net passing income, replacement cost (step 2)
    data/processed/hazards/coastal_levels.csv, coastal_onset.csv, data/interim/asset_footprints.geojson
        (adaptation: exposure recomputed with a raised onset level)
    config/assumptions.yaml: ranking_weights, ranking, adaptation

Ranking (per scenario; operating assets only, ranking.exclude_valuation_nos):
    Hazards ranked: coastal, rain, landslide (weights ranking_weights, ASSUMPTION). Heat is identical for
    every asset (HKO territory-wide series) and is reported at portfolio level only.
    Two lenses; the rain and landslide terms are the same, only the coastal term differs:
        absolute = coastal EAL HK$ (direct + BI, mid cost, median SLR, central onset, truncated at 200 yr)
        relative = coastal EAL / annual net passing income (assets without income: term 0, flagged)
    Coastal term: log10(1 + x / median of the positive x), then min-max to 0-1 (coastal_term).
    Rain term: min-max of rain_index_cont_<scenario>. Landslide term: min-max of landslide_score.
    Composite = sum of weight x term; rank 1 = highest; ties broken by coastal EAL, then replacement cost.
    Tiers (site): Tier 1 = base top n and top n in >= ranking.tier1_min_survival variants; Tier 2 = rest of
    the base top n. Relative lens excludes ranking.relative_exclude_valuation_nos (no. 94, income
    uncertain), listed separately with the flag. Hotspots: top ranking.hotspot_top_n per hazard.
    Weight test: every combination of ranking.weight_test_factors (x0.5 / x1 / x1.5) on the three weights,
    renormalised to sum 1 (27 variants, the base among them); survival = number of variants in which an
    asset is in the top n.

Adaptation (pipeline/adaptation.py): top n assets by coastal EAL (headline scenario); a demountable
barrier raising the onset level by each adaptation.barrier_heights_m; avoided EAL and break-even budget
(present value over adaptation.horizon_years at each discount rate): central = avoided EAL ramping
linearly from the baseline climate (year 1) to the scenario (year 25); upper = scenario value held flat. Top rain-driven assets are listed as
"measures recommended, not quantified".

Outputs:
    data/processed/ranking.csv            scenario x lens x asset: terms, composite, rank, survival count
    data/processed/ranking_top10.csv      headline scenario, both lenses: top n with survival counts
    data/processed/adaptation.csv         top n by coastal EAL x barrier height: EAL now, avoided EAL,
                                          break-even budgets; plus rain-driven rows (not quantified)
    data/processed/hotspots.csv           per scenario: top n per single hazard; #1 = asset to watch
    data/processed/adaptation_reference_costs.csv  UK residential 2016 costs, order-of-magnitude
                                          reference only (never Hong Kong costs)
"""

import itertools
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
HAZ = PROC / "hazards"
TERMS = ("coastal", "rain", "landslide")
WEIGHT_KEYS = {"coastal": "coastal_flood", "rain": "rain_flood", "landslide": "landslide"}


def minmax(x: pd.Series) -> pd.Series:
    """Scale to 0-1; a series without spread maps to 0."""
    x = x.astype(float)
    lo, hi = x.min(), x.max()
    if not np.isfinite(hi - lo) or hi - lo == 0:
        return pd.Series(0.0, index=x.index)
    return (x - lo) / (hi - lo)


def coastal_term(x: pd.Series) -> pd.Series:
    """log10(1 + x / median of positive x), then min-max. All zero -> all 0."""
    x = x.astype(float).fillna(0.0)
    pos = x[x > 0]
    if pos.empty:
        return pd.Series(0.0, index=x.index)
    return minmax(np.log10(1 + x / pos.median()))


def rank_assets(terms: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Composite = sum of weight x term; rank 1 = highest, ties by coastal EAL then replacement cost."""
    out = terms.copy()
    out["composite"] = sum(weights[t] * out[t] for t in TERMS)
    out = out.sort_values(["composite", "coastal_eal_hkd", "replacement_cost_hkd_mid"],
                          ascending=[False, False, False], kind="mergesort").reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def weight_variants(base: dict, factors) -> list[dict]:
    """Every combination of factors on the base weights, renormalised to sum 1."""
    out = []
    for f in itertools.product(factors, repeat=len(TERMS)):
        w = {t: base[t] * k for t, k in zip(TERMS, f)}
        s = sum(w.values())
        out.append({t: v / s for t, v in w.items()})
    return out


def survival(terms: pd.DataFrame, base: dict, factors, top_n: int) -> pd.Series:
    """Number of weight variants in which each asset is in the top n."""
    count = pd.Series(0, index=terms.valuation_no.values)
    for w in weight_variants(base, factors):
        top = rank_assets(terms, w).head(top_n).valuation_no
        count.loc[top.values] += 1
    return count


def assign_tiers(ranked: pd.DataFrame, top_n: int, tier1_min: int) -> pd.DataFrame:
    """Tier 1 = in the base top n and in the top n in >= tier1_min weight variants; Tier 2 = the rest of
    the base top n; blank otherwise (decision 2026-10-08: the site shows tiers, not ranks)."""
    out = ranked.copy()
    top = out["rank"] <= top_n
    out["tier"] = np.where(top & (out.survival_top_n >= tier1_min), "Tier 1", np.where(top, "Tier 2", ""))
    return out


def hotspots(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Top n assets per single hazard (decision 2026-10-08): coastal by EAL (positive only), rain by the
    continuous index, landslide by score (ties: steeper p90 slope, then more HLC points). The #1 of each
    hazard is an 'asset to watch' whatever its composite rank; assets tied with #1 on the hazard's own
    value (e.g. several landslide scores of 3) are flagged too, since the tie-break is not a risk measure."""
    rows = []
    specs = [("coastal", df[df.coastal_eal_hkd > 0], ["coastal_eal_hkd"], "coastal_eal_hkd"),
             ("rain", df, ["rain_index"], "rain_index"),
             ("landslide", df, ["landslide_score", "slope_p90_deg", "hlc_count"], "landslide_score")]
    for hazard, d, keys, value in specs:
        srt = d.sort_values(keys, ascending=False, kind="mergesort")
        if srt.empty:
            continue
        best = srt[value].iloc[0]
        tied = srt[srt[value] == best]
        top = pd.concat([srt.head(n), tied]).drop_duplicates("valuation_no")
        for k, r in enumerate(top.itertuples(), start=1):
            rows.append({"hazard": hazard, "hazard_rank": k, "valuation_no": r.valuation_no, "name": r.name,
                         "value": getattr(r, value), "asset_to_watch": getattr(r, value) == best,
                         "tied_with_first": getattr(r, value) == best and k > 1})
    return pd.DataFrame(rows)


def build_terms(scenario: str, lens: str, impact: pd.DataFrame, rain: pd.DataFrame, ls: pd.DataFrame,
                values: pd.DataFrame, exclude) -> pd.DataFrame:
    i = impact[(impact.scenario == scenario) & (impact.slr_quantile == "median") & (impact.case == "central")]
    v = values[~values.valuation_no.isin(exclude)].set_index("valuation_no")
    df = pd.DataFrame({"valuation_no": v.index, "name": v.name.values})
    eal = i.set_index("valuation_no")
    df["coastal_eal_hkd"] = df.valuation_no.map(eal.eal_direct_hkd_mid + eal.eal_bi_hkd.fillna(0)).fillna(0.0)
    df["net_passing_income_hkd"] = df.valuation_no.map(v.net_passing_income_hkd)
    df["replacement_cost_hkd_mid"] = df.valuation_no.map(v.replacement_cost_hkd_mid).fillna(0.0)
    df["coastal_eal_pct_income"] = 100 * df.coastal_eal_hkd / df.net_passing_income_hkd
    if lens == "absolute":
        df["coastal"] = coastal_term(df.coastal_eal_hkd)
    else:
        df["coastal"] = coastal_term(df.coastal_eal_pct_income.where(df.net_passing_income_hkd > 0, 0.0))
    df["rain_index"] = df.valuation_no.map(rain.set_index("valuation_no")[f"rain_index_cont_{scenario}"])
    lsi = ls.set_index("valuation_no")
    df["landslide_score"] = df.valuation_no.map(lsi.landslide_score)
    df["slope_p90_deg"], df["hlc_count"] = df.valuation_no.map(lsi.slope_p90_deg), df.valuation_no.map(lsi.hlc_count)
    df["rain"], df["landslide"] = minmax(df.rain_index), minmax(df.landslide_score)
    status = df.valuation_no.map(v.income_status)
    df["flags"] = np.where(df.net_passing_income_hkd.isna() & (lens == "relative"), "no income: coastal term 0",
                           np.where(status.eq("uncertain") & (lens == "relative"),
                                    "income uncertain (post-incident valuation): relative rank not reliable", ""))
    return df


def main() -> None:
    cfg = load_config("assumptions")
    rc, w0 = cfg["ranking"], {t: cfg["ranking_weights"][k] for t, k in WEIGHT_KEYS.items()}
    if not math.isclose(sum(w0.values()), 1.0):
        raise ValueError("ranking_weights must sum to 1")
    impact = pd.read_csv(PROC / "impact.csv")
    rain = pd.read_csv(HAZ / "rain_assets.csv").drop_duplicates("valuation_no")
    ls = pd.read_csv(HAZ / "landslide_assets.csv").drop_duplicates("valuation_no")
    values = pd.read_csv(ROOT / "data" / "interim" / "asset_values.csv")
    fps = gpd.read_file(ROOT / "data" / "interim" / "asset_footprints.geojson", ignore_geometry=True)
    rows, hot = [], []
    for s in rc["scenarios"]:
        for lens in ("absolute", "relative"):
            excl = rc["exclude_valuation_nos"] + (rc["relative_exclude_valuation_nos"] if lens == "relative" else [])
            t = build_terms(s, lens, impact, rain, ls, values, excl)
            r = rank_assets(t, w0)
            surv = survival(t, w0, rc["weight_test_factors"], rc["top_n"])
            r["survival_top_n"] = r.valuation_no.map(surv)
            r["n_weight_variants"] = len(rc["weight_test_factors"]) ** len(TERMS)
            r = assign_tiers(r, rc["top_n"], rc["tier1_min_survival"])
            if lens == "relative":   # listed separately with the flag, not ranked
                x = build_terms(s, lens, impact, rain, ls, values, rc["exclude_valuation_nos"])
                x = x[x.valuation_no.isin(rc["relative_exclude_valuation_nos"])].copy()
                x["flags"] = "excluded from the relative lens: income uncertain (post-incident valuation)"
                r = pd.concat([r, x], ignore_index=True)
            if lens == "absolute":
                hs = hotspots(t, rc["hotspot_top_n"]).assign(scenario=s)
                comp_top = set(r.loc[r["rank"] <= rc["top_n"], "valuation_no"])
                hs["in_composite_top_n"] = hs.valuation_no.isin(comp_top)
                hot.append(hs)
            r.insert(0, "lens", lens)
            r.insert(0, "scenario", s)
            rows.append(r)
    ranking = pd.concat(rows, ignore_index=True)
    ranking["rank"] = ranking["rank"].astype("Int64")
    ranking["survival_top_n"] = ranking["survival_top_n"].astype("Int64")
    ranking["footprint_method"] = ranking.valuation_no.map(fps.set_index("valuation_no").footprint_method)
    ranking.to_csv(PROC / "ranking.csv", index=False)
    top = ranking[(ranking.scenario == rc["headline_scenario"]) & (ranking["rank"] <= rc["top_n"])]
    top.to_csv(PROC / "ranking_top10.csv", index=False)
    hot = pd.concat(hot, ignore_index=True)
    hot.to_csv(PROC / "hotspots.csv", index=False)
    for lens, g in top.groupby("lens", sort=False):
        print(f"\ntop {rc['top_n']} ({rc['headline_scenario']}, {lens}):")
        print(g[["rank", "tier", "valuation_no", "name", "coastal_eal_hkd", "coastal", "rain", "landslide", "composite",
                 "survival_top_n"]].round(3).to_string(index=False))
    print(hot[hot.scenario == rc["headline_scenario"]].to_string(index=False))

    # adaptation break-even
    from pipeline.adaptation import avoided_eal, break_even_table
    ac = cfg["adaptation"]
    head = ranking[(ranking.scenario == ac["scenario"]) & (ranking.lens == "absolute")]
    coastal_top = head[head.coastal_eal_hkd > 0].sort_values("coastal_eal_hkd", ascending=False).head(ac["top_n_coastal"])
    levels = pd.read_csv(HAZ / "coastal_levels.csv")
    onset = pd.read_csv(HAZ / "coastal_onset.csv")
    fpx = pd.DataFrame(fps)
    out = []
    acc = cfg["coastal"]["lidar_vertical_accuracy_m"]
    nos = list(coastal_top.valuation_no)
    for h in ac["barrier_heights_m"]:
        args = (levels, onset, fpx, values, cfg["depth_damage_curve"], cfg["business_interruption"], nos, h)
        av_end = avoided_eal(*args, ac["scenario"], acc)
        av_start = avoided_eal(*args, ac["ramp_start_scenario"], acc)
        out.append(break_even_table(av_end, av_start, ac["discount_rates"], ac["horizon_years"]))
    adapt = pd.concat(out, ignore_index=True)
    adapt.insert(1, "name", adapt.valuation_no.map(values.set_index("valuation_no").name))
    adapt.insert(2, "measure", "demountable flood barrier (raises coastal onset level)")
    adapt["status"] = "quantified (coastal)"
    rain_top = head.sort_values("rain_index", ascending=False)
    rain_top = rain_top[~rain_top.valuation_no.isin(coastal_top.valuation_no)].head(ac["top_n_rain"])
    rain_rows = pd.DataFrame({
        "valuation_no": rain_top.valuation_no, "name": rain_top.name,
        "measure": "pumps, flood warning, flood barriers for car parks / basements (DSD advice: HKSAR Government "
                   "reply LCQ15, 18 Oct 2023)",
        "status": "measures recommended, not quantified (rain is a score; no rain EAL)",
        "rain_index": rain_top.rain_index.round(3)})
    adapt = pd.concat([adapt, rain_rows], ignore_index=True)
    adapt["horizon_years"] = ac["horizon_years"]
    adapt["scenario"] = ac["scenario"]
    adapt.to_csv(PROC / "adaptation.csv", index=False)
    ref = cfg["adaptation"]["reference_costs_gbp_uk_residential_2016"]
    pd.DataFrame([{"measure": k, "gbp_low": v[0] if v else None, "gbp_high": v[1] if v else None,
                   "label": "order-of-magnitude reference (UK residential, 2016); not a Hong Kong cost",
                   "source": "Herefordshire Council, Resilience Measures and Indicative Costs (31 Jul 2024; Defra FD2682)"}
                  for k, v in ref.items()]).to_csv(PROC / "adaptation_reference_costs.csv", index=False)
    print(f"\nwrote data/processed/ranking.csv, ranking_top10.csv, adaptation.csv, adaptation_reference_costs.csv")


if __name__ == "__main__":
    main()
