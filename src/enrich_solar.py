"""Sample Global Solar Atlas GHI at each settlement's coordinates."""
import pandas as pd
import rasterio
from src.config import POI_ENRICHED_CSV, SOLAR_GHI_TIF, ENRICHED_FULL_CSV


def main():
    df = pd.read_csv(POI_ENRICHED_CSV)
    print(f"Loaded {len(df):,} settlements from {POI_ENRICHED_CSV.name}")

    with rasterio.open(SOLAR_GHI_TIF) as src:
        print(f"GHI raster: CRS={src.crs}, bounds={src.bounds}")
        coords = list(zip(df["lon"], df["lat"]))
        ghi_values = [val[0] for val in src.sample(coords)]
        df["GHI"] = ghi_values

    # The "LTAym_YearlyMonthlyTotals" file is yearly — no conversion needed.
    # If median < 100, file is in daily kWh — multiply by 365.
    if df["GHI"].median() < 100:
        print("GHI median < 100 — file appears to be daily; converting to annual")
        df["GHI"] = df["GHI"] * 365

    # Fill any out-of-bounds with country median
    n_missing = df["GHI"].isna().sum() + (df["GHI"] <= 0).sum()
    if n_missing:
        country_median = df.loc[df["GHI"] > 0, "GHI"].median()
        df.loc[df["GHI"] <= 0, "GHI"] = country_median
        print(f"  Imputed {n_missing} bad-value settlements with median {country_median:.1f}")

    print(f"GHI range: {df['GHI'].min():.0f} to {df['GHI'].max():.0f} kWh/m2/yr")
    print(f"GHI mean:  {df['GHI'].mean():.0f}")

    assert 1000 <= df["GHI"].median() <= 2500, f"GHI median {df['GHI'].median():.0f} outside expected range"

    ENRICHED_FULL_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ENRICHED_FULL_CSV, index=False)
    print(f"Saved -> {ENRICHED_FULL_CSV}")


if __name__ == "__main__":
    main()
