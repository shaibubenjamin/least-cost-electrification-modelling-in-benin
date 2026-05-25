"""Spatially join settlements to GADM admin boundaries (departments + communes)."""
import pandas as pd
import geopandas as gpd
from src.config import ENRICHED_FULL_CSV, ADMIN1_SHP, ADMIN2_SHP


def main():
    df = pd.read_csv(ENRICHED_FULL_CSV)

    # Drop prior admin columns to avoid conflicts on re-run
    for col in ["admin1_name", "admin2_name", "index_right"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )

    admin1 = gpd.read_file(ADMIN1_SHP).to_crs("EPSG:4326")[["NAME_1", "geometry"]].rename(
        columns={"NAME_1": "admin1_name"}
    )
    admin2 = gpd.read_file(ADMIN2_SHP).to_crs("EPSG:4326")[["NAME_2", "geometry"]].rename(
        columns={"NAME_2": "admin2_name"}
    )

    gdf = gpd.sjoin(gdf, admin1, how="left", predicate="within")
    if "index_right" in gdf.columns:
        gdf = gdf.drop(columns=["index_right"])

    gdf = gpd.sjoin(gdf, admin2, how="left", predicate="within")
    if "index_right" in gdf.columns:
        gdf = gdf.drop(columns=["index_right"])

    print(f"Settlements with admin1: {gdf['admin1_name'].notna().sum():,}")
    print(f"Settlements with admin2: {gdf['admin2_name'].notna().sum():,}")
    print(f"Admin1 distribution:")
    print(gdf["admin1_name"].value_counts().to_string())

    out = gdf.drop(columns=["geometry"])
    out.to_csv(ENRICHED_FULL_CSV, index=False)
    print(f"\nUpdated -> {ENRICHED_FULL_CSV}")
    print(f"Shape: {out.shape[0]:,} rows x {out.shape[1]} columns")


if __name__ == "__main__":
    main()
