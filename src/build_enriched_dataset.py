"""Validate and finalize the fully-enriched settlement dataset.
Checks all required columns are populated, logs coverage stats,
and confirms the file is ready for OnSSET input preparation.
"""
import pandas as pd
import numpy as np
from src.config import ENRICHED_FULL_CSV

REQUIRED_COLS = [
    "identifier", "lat", "lon", "population", "mean_rwi",
    "dist_to_substations", "distance_to_planned_transmission_lines",
    "has_nightlight", "dist_nearest_hub_km",
    "GHI", "pop_2030_worldpop", "growth_factor",
    "admin1_name", "admin2_name",
    "productive_multiplier", "n_health_combined", "n_education_combined",
    "anchor_load_kwh_yr", "has_poi_signal",
]


def main():
    print("=" * 60)
    print("Build enriched dataset — final validation")
    print("=" * 60)

    df = pd.read_csv(ENRICHED_FULL_CSV)
    print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    print("\nColumn coverage:")
    for col in REQUIRED_COLS:
        n_null = df[col].isna().sum()
        pct = 100 * n_null / len(df)
        flag = " WARN" if pct > 1 else ""
        print(f"  {col:<42} {n_null:5} nulls ({pct:.1f}%){flag}")

    # Final sanity checks
    assert len(df) == 17175, f"Expected 17,175 rows, got {len(df)}"
    assert df["GHI"].between(1000, 2500).all(), "GHI out of range"
    assert df["growth_factor"].between(0.5, 3.1).all(), "growth_factor out of range"
    assert (df["pop_2030_worldpop"] >= 0).all(), "Negative pop_2030_worldpop"

    print(f"\nKey stats:")
    print(f"  Population total (dataset):       {df['population'].sum():>12,}")
    print(f"  Population total (WorldPop 2030): {df['pop_2030_worldpop'].sum():>12,}")
    print(f"  GHI median (kWh/m2/yr):           {df['GHI'].median():>12.0f}")
    print(f"  Growth factor median:             {df['growth_factor'].median():>12.3f}")
    print(f"  Settlements with POI signal:      {df['has_poi_signal'].sum():>12,} ({100*df['has_poi_signal'].mean():.1f}%)")
    print(f"  Admin1 coverage:                  {df['admin1_name'].notna().sum():>12,} ({100*df['admin1_name'].notna().mean():.1f}%)")

    print(f"\nEnriched dataset validated -> {ENRICHED_FULL_CSV}")


if __name__ == "__main__":
    main()
