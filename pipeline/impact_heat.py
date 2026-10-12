"""Heat: illustrative cooling-cost what-if, not a projection (decision 2026-10-07). Run by step 5.

No projected heat cost: no sourced cooling-demand-per-degree sensitivity was found. Instead:
    baseline cooling electricity = Link HK electricity (ESG Data Compendium FY2025/26, landlord-
        controlled only) x EMSD retail-segment air-conditioning share (HK Energy End-use Data
        2025, Table 38, 2023: air conditioning / total)
    baseline cooling cost = cooling electricity x average net tariff, weighted by GFA between CLP
        and HK Electric (utility from the asset's ALS district; ASSUMPTION)
    what-if = cooling cost at +10% / +20% cooling demand (heat_whatif.demand_changes)
All inputs in config `heat_whatif` (values in config/local). Labelled "illustrative what-if, not a
projection" wherever shown.

Output: data/processed/heat_whatif.csv
"""

import pandas as pd


def assign_utility(df: pd.DataFrame, hk_electric_districts, blank_district_clp_nos) -> pd.Series:
    """'hk_electric' for assets in hk_electric_districts, else 'clp'. An asset with a blank district
    must be listed in blank_district_clp_nos (checked by location), else stop."""
    blank = df.district.isna() | df.district.astype(str).str.strip().eq("")
    missing = sorted(set(df.loc[blank, "valuation_no"]) - set(blank_district_clp_nos or []))
    if missing:
        raise ValueError(f"no district and not in heat_whatif.blank_district_clp_nos: {missing}")
    return df.district.isin(hk_electric_districts).map({True: "hk_electric", False: "clp"})


def weighted_tariff(df: pd.DataFrame, tariffs: dict) -> tuple[float, float]:
    """(GFA-weighted average tariff, HK Electric share of GFA)."""
    w = df.groupby("utility").gfa_m2.sum() / df.gfa_m2.sum()
    return float(sum(w.get(u, 0.0) * t for u, t in tariffs.items())), float(w.get("hk_electric", 0.0))


def cooling_whatif(electricity_mwh: float, ac_share: float, tariff_cents_per_kwh: float,
                   demand_changes) -> pd.DataFrame:
    """Cooling electricity and cost at baseline and at each demand change (fraction)."""
    base_mwh = electricity_mwh * ac_share
    rows = []
    for d in [0.0] + list(demand_changes):
        mwh = base_mwh * (1 + d)
        cost = mwh * 1000 * tariff_cents_per_kwh / 100
        rows.append({"demand_change": d, "cooling_mwh": mwh, "cooling_cost_hkd": cost,
                     "extra_cost_hkd": cost - base_mwh * 1000 * tariff_cents_per_kwh / 100})
    return pd.DataFrame(rows)


def heat_whatif(cfg: dict, assets: pd.DataFrame) -> pd.DataFrame:
    """assets: valuation_no, district, gfa_m2, status. Returns the what-if table with its inputs."""
    for k in ("link_hk_electricity_mwh", "emsd_retail_ac_tj", "emsd_retail_total_tj"):
        if cfg[k] is None:
            raise ValueError(f"heat_whatif.{k} missing (config/local/assumptions.yaml)")
    if any(v is None for v in cfg["tariff_cents_per_kwh"].values()):
        raise ValueError("heat_whatif.tariff_cents_per_kwh missing (config/local/assumptions.yaml)")
    a = assets[assets.status != "under_development"].copy()
    a["utility"] = assign_utility(a, cfg["hk_electric_districts"], cfg["blank_district_clp_nos"])
    tariff, hke_share = weighted_tariff(a, cfg["tariff_cents_per_kwh"])
    ac_share = cfg["emsd_retail_ac_tj"] / cfg["emsd_retail_total_tj"]
    out = cooling_whatif(cfg["link_hk_electricity_mwh"], ac_share, tariff, cfg["demand_changes"])
    out["link_hk_electricity_mwh"] = cfg["link_hk_electricity_mwh"]
    out["ac_share"] = round(ac_share, 6)
    out["tariff_cents_per_kwh"] = round(tariff, 3)
    out["hk_electric_gfa_share"] = round(hke_share, 6)
    out["label"] = "illustrative what-if, not a projection"
    return out
