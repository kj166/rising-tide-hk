"""Adaptation break-even (step 6; decision 2026-10-07): what a demountable flood barrier is worth.

A barrier of height h raises an asset's coastal onset level by h: water below onset + h no longer
enters, water above it overtops and floods as before (same depth inside, from the unchanged lowest
floor). Avoided EAL = EAL(current onset) - EAL(raised onset), from the same step 4 / step 5 functions
(direct + BI, mid cost; BI at Hazus maximum days and at 50%; truncated and with tail). Break-even budget
= present value of the avoided EAL over the horizon (constant annual amount at the scenario's level;
ASSUMPTION). No measure costs are used: Hong Kong unit costs are not available; UK figures are shown as
an order-of-magnitude reference only.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


exposure = _load("exposure_04", "04_exposure.py")
impact = _load("impact_05", "05_impact.py")


def present_value(annual: float, rate: float, years: int) -> float:
    """Present value of a constant amount at the end of each year for `years` years."""
    if rate == 0:
        return annual * years
    return annual * (1 - (1 + rate) ** -years) / rate


def present_value_ramp(start: float, end: float, rate: float, years: int) -> float:
    """Present value of an amount ramping linearly from `start` (year 1) to `end` (year `years`),
    each paid at the end of its year (decision 2026-10-08: central case, baseline -> 2050)."""
    if years == 1:
        return start / (1 + rate)
    return sum((start + (end - start) * (t - 1) / (years - 1)) / (1 + rate) ** t for t in range(1, years + 1))


def raise_onset(onset: pd.DataFrame, nos, h: float) -> pd.DataFrame:
    """Copy of the onset table with onset_level_mpd + h for the listed assets (NaN stays NaN)."""
    out = onset.copy()
    m = out.valuation_no.isin(list(nos))
    out.loc[m, "onset_level_mpd"] = out.loc[m, "onset_level_mpd"] + h
    return out


def _eal(levels, onset, fps, values, curve, bi, acc) -> pd.DataFrame:
    exp = exposure.exposure_table(levels, onset, fps, acc)
    ev = impact.event_losses(exp, values, curve, bi)
    return impact.eal_table(ev[ev.case == "central"]).set_index("valuation_no")


def avoided_eal(levels, onset, fps, values, curve, bi, nos, h, scenario, acc) -> pd.DataFrame:
    """Per listed asset: EAL now and with a barrier of height h (median SLR, central onset, mid cost),
    and the avoided EAL: direct + BI (Hazus maximum days) and direct + BI at the 50% days, truncated
    and with tail."""
    lv = levels[(levels.scenario == scenario) & (levels.slr_quantile == "median") & levels.valuation_no.isin(nos)]
    now = _eal(lv, onset, fps, values, curve, bi, acc)
    new = _eal(lv, raise_onset(onset, nos, h), fps, values, curve, bi, acc)
    rows = []
    for no in nos:
        a, b = now.loc[no], new.loc[no]
        tot = lambda r, bi_col, tail: (r[f"eal_direct{'_tail' if tail else ''}_hkd_mid"]  # noqa: E731
                                       + np.nan_to_num(r[f"{bi_col}{'_tail' if tail else ''}_hkd"]))
        rows.append({"valuation_no": no, "barrier_height_m": h,
                     "eal_now_hkd": tot(a, "eal_bi", False), "eal_now_tail_hkd": tot(a, "eal_bi", True),
                     "eal_with_barrier_hkd": tot(b, "eal_bi", False),
                     "avoided_eal_hkd": tot(a, "eal_bi", False) - tot(b, "eal_bi", False),
                     "avoided_eal_tail_hkd": tot(a, "eal_bi", True) - tot(b, "eal_bi", True),
                     "avoided_eal_bi50_hkd": tot(a, "eal_bi_half", False) - tot(b, "eal_bi_half", False),
                     "avoided_eal_bi50_tail_hkd": tot(a, "eal_bi_half", True) - tot(b, "eal_bi_half", True)})
    return pd.DataFrame(rows)


def break_even_table(av_end: pd.DataFrame, av_start: pd.DataFrame, rates, years: int) -> pd.DataFrame:
    """Break-even budgets per avoided-EAL column and discount rate (decision 2026-10-08):
    central = PV of avoided EAL ramping linearly from av_start (year 1, baseline climate) to av_end
    (year `years`, scenario); upper = PV of av_end held flat for every year."""
    names = {"avoided_eal_hkd": "base", "avoided_eal_tail_hkd": "tail", "avoided_eal_bi50_hkd": "bi50",
             "avoided_eal_bi50_tail_hkd": "bi50_tail"}
    start = av_start.set_index(["valuation_no", "barrier_height_m"])
    out = av_end.copy()
    for col, name in names.items():
        out[f"{col.replace('_hkd', '')}_baseline_hkd"] = [start.loc[(n, h), col] for n, h in
                                                         zip(out.valuation_no, out.barrier_height_m)]
        for r in rates:
            tag = f"r{round(r * 100)}"
            out[f"breakeven_central_{name}_{tag}_hkd"] = [
                present_value_ramp(a0, a1, r, years) for a0, a1 in zip(out[f"{col.replace('_hkd', '')}_baseline_hkd"], out[col])]
            out[f"breakeven_upper_{name}_{tag}_hkd"] = [present_value(x, r, years) for x in out[col]]
    return out
