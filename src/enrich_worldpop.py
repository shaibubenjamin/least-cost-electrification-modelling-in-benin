"""Compute projected 2030 population per settlement from WorldPop raster.

Uses rasterio + geopandas for zonal statistics (avoids fiona/rasterstats GDAL
build requirement). Polygons from the settlement GeoJSON are rasterized and
the sum of WorldPop pixels within each polygon is computed.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping
from src.config import (
    SETTLEMENT_POLYGONS, WORLDPOP_2030_TIF,
    ENRICHED_FULL_CSV,
)


def zonal_sum(tif_path, gdf: gpd.GeoDataFrame, id_col: str) -> pd.Series:
    """Sum raster pixels within each polygon (all_touched=True to handle small polys).
    Also buffers polygons by 1 pixel width if the raw polygon is too small.
    Returns a Series indexed by id_col.
    """
    results = {}
    with rasterio.open(tif_path) as src:
        nodata = src.nodata
        # Pixel size in degrees (~100m at Benin's latitude)
        pixel_deg = abs(src.transform.a)
        for _, row in gdf.iterrows():
            geom = row.geometry
            # Buffer by one pixel if polygon is smaller than 4 pixels
            if geom.area < (4 * pixel_deg ** 2):
                geom = geom.buffer(pixel_deg)
            try:
                data, _ = rio_mask(src, [mapping(geom)], crop=True, all_touched=True)
                arr = data[0].astype(float)
                if nodata is not None:
                    arr[arr == nodata] = np.nan
                arr[arr < 0] = np.nan
                total = np.nansum(arr)
            except Exception:
                total = 0.0
            results[row[id_col]] = total
    return pd.Series(results, name="pop_2030_worldpop")


def main():
    df = pd.read_csv(ENRICHED_FULL_CSV)
    print(f"Loaded {len(df):,} settlements")

    # Load polygons; inner-join to cleaned settlements to exclude dropped rows
    polys = gpd.read_file(SETTLEMENT_POLYGONS)
    polys = polys[polys["identifier"].isin(df["identifier"])][["identifier", "geometry"]]
    polys = polys.to_crs("EPSG:4326")
    print(f"Loaded {len(polys):,} polygons")

    print("Computing zonal sums (this takes 2-5 min for 17k polygons)...")
    pop_series = zonal_sum(WORLDPOP_2030_TIF, polys, "identifier")

    polys["pop_2030_worldpop"] = polys["identifier"].map(pop_series).fillna(0).astype(int)
    national_total = polys["pop_2030_worldpop"].sum()
    print(f"WorldPop 2030 national total: {national_total:,.0f}")

    # Drop existing columns if re-running
    for col in ["pop_2030_worldpop", "growth_factor"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    df = df.merge(
        polys[["identifier", "pop_2030_worldpop"]],
        on="identifier", how="left"
    )
    df["pop_2030_worldpop"] = df["pop_2030_worldpop"].fillna(0).astype(int)

    # Raw growth factor
    raw_gf = (df["pop_2030_worldpop"] / df["population"].clip(lower=1)).clip(0.5, 3.0)

    # Departmental fallback: WorldPop-based settlements where raw_gf < 0.85 are
    # likely raster-coverage artefacts for small polygons. Apply departmental average.
    df["_raw_gf"] = raw_gf
    dept_col = "admin_cgaz_1" if "admin_cgaz_1" in df.columns else None

    if dept_col:
        reliable = raw_gf >= 0.85
        dept_gf = df[reliable].groupby(dept_col).apply(
            lambda g: g["pop_2030_worldpop"].sum() / g["population"].sum()
        ).clip(0.9, 2.0).rename("dept_gf")
        df = df.join(dept_gf, on=dept_col, how="left")
        df["dept_gf"] = df["dept_gf"].fillna(dept_gf.mean() if len(dept_gf) else 1.3)
        df["growth_factor"] = raw_gf.where(reliable, df["dept_gf"]).clip(0.9, 3.0).round(4)
        df = df.drop(columns=["dept_gf"])
        print(f"Settlements using departmental fallback GF: {(~reliable).sum():,}")
    else:
        df["growth_factor"] = raw_gf.round(4)

    df = df.drop(columns=["_raw_gf"])

    print(f"Growth factor distribution:")
    print(df["growth_factor"].describe().round(3).to_string())

    df.to_csv(ENRICHED_FULL_CSV, index=False)
    print(f"\nUpdated -> {ENRICHED_FULL_CSV}")
    print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")


if __name__ == "__main__":
    main()
