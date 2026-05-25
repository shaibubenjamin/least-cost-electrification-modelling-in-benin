"""Compute per-settlement distance to existing HV transmission lines.

Input:  data/raw/settlements_enriched_full.csv
        transmission_line/Benin_existing_transmission_lines_2017 (2).geojson
Output: updates settlements_enriched_full.csv with 'dist_to_hvline_km' column

The new column is then used in prepare_onsset_input.py so that:
  GridDistCurrent = min(dist_to_substations, dist_to_hvline_km)
which correctly represents the true grid extension distance
(a settlement can tap off either a nearby substation or a nearby HV line).
"""
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Benjamin.shaibu\Desktop\least-cost-electrification-modelling-in-benin")
TL_GEOJSON   = PROJECT_ROOT / "transmission_line" / "Benin_existing_transmission_lines_2017 (2).geojson"
ENRICHED_CSV = PROJECT_ROOT / "data" / "raw" / "settlements_enriched_full.csv"

# UTM Zone 31N (EPSG:32631) — covers Benin, units in metres
METRIC_CRS = "EPSG:32631"


def main():
    print("Loading transmission lines...")
    tl = gpd.read_file(TL_GEOJSON)
    print(f"  {len(tl)} line features  |  CRS: {tl.crs}")
    print(f"  Voltages: {tl['Voltage_KV'].value_counts().to_dict()}")

    # Keep only lines inside or very close to Benin
    tl_benin = tl[tl["Country_1"].isin(["BJ", "BEN"]) |
                  tl["Country_2"].isin(["BJ", "BEN"])].copy()
    print(f"  Benin-related lines: {len(tl_benin)}")

    # Re-project to metric CRS for distance calculations
    tl_m = tl_benin.to_crs(METRIC_CRS)
    # Dissolve to a single MultiLineString to compute distance to the full network
    tl_union = tl_m.geometry.unary_union

    print("\nLoading settlements...")
    df = pd.read_csv(ENRICHED_CSV)
    print(f"  {len(df):,} settlements")

    # Build GeoDataFrame of settlement centroids
    gdf = gpd.GeoDataFrame(
        df[["lon", "lat"]].copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326"
    ).to_crs(METRIC_CRS)

    print("Computing distances to HV network (this may take ~1 min)...")
    dist_m = gdf.geometry.distance(tl_union)
    dist_km = dist_m / 1000.0

    df["dist_to_hvline_km"] = dist_km.values.round(3)

    print(f"\n=== dist_to_hvline_km (new column) ===")
    print(df["dist_to_hvline_km"].describe())
    print(f"  Settlements within 5 km of HV line: {(df['dist_to_hvline_km'] <= 5).sum():,}")
    print(f"  Settlements within 10 km: {(df['dist_to_hvline_km'] <= 10).sum():,}")

    # Compare with old column
    old = pd.to_numeric(df["distance_to_existing_transmission_lines"], errors="coerce")
    new = df["dist_to_hvline_km"]
    print(f"\n  Old 'distance_to_existing_transmission_lines' mean: {old.mean():.2f} km")
    print(f"  New 'dist_to_hvline_km' mean:                      {new.mean():.2f} km")
    print(f"  Correlation: {old.corr(new):.4f}")

    # Show what GridDistCurrent would become
    sub = pd.to_numeric(df["dist_to_substations"], errors="coerce")
    new_grid_dist = pd.concat([sub, new], axis=1).min(axis=1)
    print(f"\n=== Proposed new GridDistCurrent = min(substation, HV line) ===")
    print(new_grid_dist.describe())
    print(f"  Old GridDistCurrent (substation only) mean: {sub.mean():.2f} km")
    print(f"  New GridDistCurrent mean:                   {new_grid_dist.mean():.2f} km")
    print(f"  Settlements where HV line is closer: {(new < sub).sum():,} "
          f"({100*(new < sub).mean():.1f}%)")

    df.to_csv(ENRICHED_CSV, index=False)
    print(f"\nSaved -> {ENRICHED_CSV}  (added dist_to_hvline_km)")
    return df


if __name__ == "__main__":
    main()
