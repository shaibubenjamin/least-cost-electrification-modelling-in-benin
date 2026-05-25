"""Apply wealth-disaggregated demand tiers via Meta Relative Wealth Index.

Extension 1: OnSSET's prepare_wtf_tier_columns() creates columns
ResidentialDemandTier1 through ResidentialDemandTier5 (constant per tier).
set_scenario_variables() then copies the relevant tier value into PerCapitaDemand
for all rural or urban settlements uniformly.

The tier-numbered columns are modified per-settlement BEFORE set_scenario_variables
runs, so that richest-quartile settlements receive a higher demand target and
poorest-quartile receive a lower one.

Key design decisions:
- IsUrban == 2 settlements (large urban centres / cities) are EXCLUDED. RWI at
  2.4km resolution blends many wealth levels within a city, and cities already
  receive the higher Tier 3 urban demand target. Applying a 4x multiplier to a
  1.5M-person city creates implausible multi-billion-dollar CAPEX.
- Multipliers use ACTUAL MTF tier ratios, not a flat factor:
    Q1 rural  (-1 tier, Tier2->Tier1): 38.7/219  = 0.177
    Q4 rural  (+1 tier, Tier2->Tier3): 803/219   = 3.67
  These are rounded to 0.18 and 3.67 for clarity.
- Middle quartiles (Q2, Q3) receive no adjustment (multiplier = 1.0).
"""
import pandas as pd
import numpy as np

from src.config import RWI_TIER_ADJUSTMENT

# Actual MTF tier ratios (kWh/HH/yr)
_MTF = {1: 38.7, 2: 219.0, 3: 803.0, 4: 2117.0, 5: 2993.0}

# Multipliers derived from tier ratios for a baseline-Tier-2 rural settlement
_TIER_RATIO = {
    -1: _MTF[1] / _MTF[2],   # 38.7/219  = 0.177  (Tier2 -> Tier1)
     0: 1.0,
    +1: _MTF[3] / _MTF[2],   # 803/219   = 3.669  (Tier2 -> Tier3)
}


def compute_rwi_quartile_thresholds(rwi_series: pd.Series):
    """Return Benin RWI Q1 and Q3 boundary values from the data."""
    q1 = rwi_series.quantile(0.25)
    q3 = rwi_series.quantile(0.75)
    return q1, q3


def wealth_quartile(rwi, q1_thresh, q3_thresh):
    """Map a single mean_rwi value to a quartile label."""
    if pd.isna(rwi):
        return "q2"
    if rwi <= q1_thresh:
        return "q1"
    if rwi >= q3_thresh:
        return "q4"
    return "q2"


def apply_wealth_tier_shift(sp_df: pd.DataFrame) -> None:
    """Adjust ResidentialDemandTier{1-5} columns in-place based on mean_rwi quartile.

    Must be called AFTER prepare_wtf_tier_columns() which creates the numbered columns.
    Skips IsUrban == 2 settlements (large cities) — see module docstring for rationale.
    """
    if "mean_rwi" not in sp_df.columns:
        print("  [extensions] mean_rwi column not found -- skipping wealth tier shift")
        return

    tier_cols = [c for c in sp_df.columns if c.startswith("ResidentialDemandTier") and c[-1].isdigit()]
    if not tier_cols:
        print("  [extensions] ResidentialDemandTier{N} columns not found -- "
              "call after prepare_wtf_tier_columns()")
        return

    rwi = sp_df["mean_rwi"]
    q1_thresh, q3_thresh = compute_rwi_quartile_thresholds(rwi)

    adj_map = {q: _TIER_RATIO[shift] for q, shift in RWI_TIER_ADJUSTMENT.items()}

    # Exclude large urban centres (IsUrban == 2) — cities are high-density mixed-wealth
    is_city = sp_df.get("IsUrban", pd.Series(0, index=sp_df.index)) == 2

    multipliers = pd.Series(1.0, index=sp_df.index)
    for idx in sp_df.index:
        if is_city.loc[idx]:
            continue   # leave cities at their base tier
        q = wealth_quartile(rwi.loc[idx], q1_thresh, q3_thresh)
        multipliers.loc[idx] = adj_map[q]

    n_shifted_up   = (multipliers > 1).sum()
    n_shifted_down = (multipliers < 1).sum()
    n_city_skipped = is_city.sum()

    for col in tier_cols:
        original_mean = sp_df[col].mean()
        sp_df[col] = sp_df[col] * multipliers
        new_mean = sp_df[col].mean()
        print(f"  [extensions] {col}: mean {original_mean:.1f} -> {new_mean:.1f} kWh/capita/yr")

    print(f"  [extensions] Wealth tier shift: "
          f"{n_shifted_up:,} up (Q4), {n_shifted_down:,} down (Q1), "
          f"{n_city_skipped:,} urban centres skipped")
    print(f"  [extensions] RWI quartile thresholds: Q1={q1_thresh:.3f}, Q3={q3_thresh:.3f}")
    print(f"  [extensions] Multipliers used: Q1={adj_map['q1']:.3f}, Q4={adj_map['q4']:.3f}")
