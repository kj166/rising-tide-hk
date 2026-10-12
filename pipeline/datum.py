"""Vertical datum conversion: Chart Datum (mCD) <-> Hong Kong Principal Datum (mPD).

The CD is 0.146 m below the PD (PWDM Part 1 §2.2.1, PDF p. 13; config/assumptions.yaml
`datum.chart_datum_below_pd_m`), so mPD = mCD - 0.146 (e.g. 3.88 mCD = 3.734 mPD).
Heights in mCD (HKO tide records) are converted on load; the project works in mPD.
"""

from pipeline.config import load_config


def _offset(cd_below_pd_m: float | None) -> float:
    if cd_below_pd_m is None:
        cd_below_pd_m = load_config("assumptions")["datum"]["chart_datum_below_pd_m"]
    return float(cd_below_pd_m)


def mcd_to_mpd(height_mcd, cd_below_pd_m: float | None = None):
    """Height above Chart Datum -> height above Principal Datum (scalar or array)."""
    return height_mcd - _offset(cd_below_pd_m)


def mpd_to_mcd(height_mpd, cd_below_pd_m: float | None = None):
    """Height above Principal Datum -> height above Chart Datum (scalar or array)."""
    return height_mpd + _offset(cd_below_pd_m)
