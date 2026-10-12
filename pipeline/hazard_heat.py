"""Heat per scenario (step 3; plan 2026-10-06, decision 2026-10-07).

HKO projections are territory-wide (Hong Kong Observatory station series), so heat is one set
of values per scenario, the same for every asset: very hot days and hot nights per year (mean +
HKO "likely range") and the change in annual mean temperature, all relative to 1995-2014.
Values from config/local/scenarios.yaml (HKO projection pages; check sheet
docs/internal/heat_rain_transcription_check.md).
"""

import pandas as pd


def heat_table(scen: dict, scenarios: list[str]) -> pd.DataFrame:
    """One row per scenario; *_change = scenario mean minus the 1995-2014 average."""
    base = scen["baseline"]
    b_vhd, b_hn = base["very_hot_days"]["mean"], base["hot_nights"]["mean"]
    if b_vhd is None or b_hn is None or base.get("mean_temp_c") is None:
        raise ValueError("baseline heat values missing (config/local/scenarios.yaml)")
    rows = []
    for s in scenarios:
        v, n = scen[s]["very_hot_days"], scen[s]["hot_nights"]
        t = scen[s]["mean_temp_change_c"]
        if v["mean"] is None or n["mean"] is None or t is None:
            raise ValueError(f"heat values missing for {s} (config/local/scenarios.yaml)")
        rows.append({"scenario": s,
                     "very_hot_days": v["mean"], "very_hot_days_low": v.get("low"), "very_hot_days_high": v.get("high"),
                     "very_hot_days_change": v["mean"] - b_vhd,
                     "hot_nights": n["mean"], "hot_nights_low": n.get("low"), "hot_nights_high": n.get("high"),
                     "hot_nights_change": n["mean"] - b_hn,
                     "mean_temp_change_c": t, "mean_temp_c": round(base["mean_temp_c"] + t, 1),
                     # likely range from HKO's "more details" page (CMIP6); None if not given
                     "mean_temp_change_c_low": (scen[s].get("mean_temp_change_c_likely") or {}).get("low"),
                     "mean_temp_change_c_high": (scen[s].get("mean_temp_change_c_likely") or {}).get("high")})
    return pd.DataFrame(rows)
