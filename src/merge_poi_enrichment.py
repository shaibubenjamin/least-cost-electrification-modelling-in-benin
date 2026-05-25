"""
merge_poi_enrichment.py
Merges poi_weights_per_settlement.csv into benin_settlements_cleaned.csv,
adding five derived columns needed by the OnSSET pipeline:
  - productive_multiplier  : scales residential demand for productive use
  - n_health_combined      : max(dataset count, OSM count)
  - n_education_combined   : max(dataset count, OSM count)
  - anchor_load_kwh_yr     : 24/7 telecom + water-pump base load (kWh/year)
  - has_poi_signal         : bool, True if any OSM POI was matched
Output: data/raw/settlements_enriched_poi.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

BASE          = Path(r"C:\Users\Benjamin.shaibu\Desktop\least-cost-electrification-modelling-in-benin")
SETTLEMENTS   = BASE / "benin_settlements_cleaned.csv"
POI_WEIGHTS   = BASE / "data/raw/poi_weights_per_settlement.csv"
OUTPUT        = BASE / "data/raw/settlements_enriched_poi.csv"

# productive_multiplier scaling bounds
MULTIPLIER_BASELINE  = 0.20   # settlements with no POI signal
MULTIPLIER_LOW       = 0.10   # settlements with minimal productive POIs
MULTIPLIER_HIGH      = 0.60   # settlements with dense productive POIs

# kWh/day weights from LOAD_CATEGORY; multiplied × 365 to get annual
ANCHOR_CATEGORIES = ["weight_infrastructure_telecom", "weight_infrastructure_water"]


def compute_productive_multiplier(df: pd.DataFrame) -> pd.Series:
    """
    Log-scale productive POI total weight to [MULTIPLIER_LOW, MULTIPLIER_HIGH].
    Settlements without any productive signal get MULTIPLIER_BASELINE.
    """
    prod_cols = ["weight_productive_heavy", "weight_productive_light", "weight_productive_medium"]
    total = df[prod_cols].sum(axis=1)

    has_prod = total > 0
    nonzero = total[has_prod]

    # Use 95th-percentile as ceiling to avoid outlier domination
    p95 = nonzero.quantile(0.95) if len(nonzero) > 0 else 1.0

    log_score = np.log1p(total) / np.log1p(p95)
    log_score = log_score.clip(0, 1)

    multiplier = pd.Series(MULTIPLIER_BASELINE, index=df.index, dtype=float)
    multiplier[has_prod] = MULTIPLIER_LOW + log_score[has_prod] * (MULTIPLIER_HIGH - MULTIPLIER_LOW)
    return multiplier.round(4)


def main():
    print("=" * 60)
    print("Merge POI enrichment into settlements")
    print("=" * 60)

    settlements = pd.read_csv(SETTLEMENTS)
    poi = pd.read_csv(POI_WEIGHTS)
    print(f"Settlements: {len(settlements):,} rows")
    print(f"POI weights:  {len(poi):,} rows")

    merged = settlements.merge(poi, on="identifier", how="left")

    # Fill POI columns with 0 for unmatched settlements
    poi_cols = [c for c in poi.columns if c != "identifier"]
    merged[poi_cols] = merged[poi_cols].fillna(0)

    # --- Derived columns ---
    merged["has_poi_signal"] = (
        merged[[c for c in poi_cols if c.startswith("count_")]].sum(axis=1) > 0
    )

    merged["productive_multiplier"] = compute_productive_multiplier(merged)

    merged["n_health_combined"] = np.maximum(
        merged["num_health_facilities"].fillna(0),
        merged["count_institutional_health"].fillna(0),
    ).astype(int)

    merged["n_education_combined"] = np.maximum(
        merged["num_education_facilities"].fillna(0),
        merged["count_institutional_edu"].fillna(0),
    ).astype(int)

    # Weights represent daily kWh; ×365 → annual
    merged["anchor_load_kwh_yr"] = (
        merged[ANCHOR_CATEGORIES].sum(axis=1) * 365
    ).round(1)

    # --- Diagnostics ---
    print(f"\nSettlements with POI signal: {merged['has_poi_signal'].sum():,} "
          f"({100*merged['has_poi_signal'].mean():.1f}%)")

    pm = merged["productive_multiplier"]
    print(f"productive_multiplier — min: {pm.min():.2f}  median: {pm.median():.2f}  "
          f"max: {pm.max():.2f}  mean: {pm.mean():.3f}")

    print(f"n_health_combined lifted vs dataset:    "
          f"{(merged['n_health_combined'] > merged['num_health_facilities']).sum():,} settlements")
    print(f"n_education_combined lifted vs dataset: "
          f"{(merged['n_education_combined'] > merged['num_education_facilities']).sum():,} settlements")

    anchor_nonzero = (merged["anchor_load_kwh_yr"] > 0).sum()
    print(f"Settlements with anchor loads: {anchor_nonzero:,} "
          f"(median {merged.loc[merged['anchor_load_kwh_yr']>0,'anchor_load_kwh_yr'].median():.0f} kWh/yr)")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT, index=False)
    print(f"\nSaved -> {OUTPUT}")
    print(f"Final shape: {merged.shape[0]:,} rows × {merged.shape[1]} columns")


if __name__ == "__main__":
    main()
