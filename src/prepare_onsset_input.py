"""Map enriched settlement table to OnSSET column schema.
Output: data/raw/onsset_input.csv  (used by both vanilla and extended runs).
"""
import numpy as np
import pandas as pd
from src.config import (
    ENRICHED_FULL_CSV, ONSSET_INPUT_CSV,
    HOUSEHOLD_SIZE, ELEC_RATE_START,
)


def main():
    df = pd.read_csv(ENRICHED_FULL_CSV)
    print(f"Loaded {len(df):,} enriched settlements")

    out = pd.DataFrame()

    # --- Identification ---
    out["Country"]          = "Benin"
    out["X_deg"]            = df["lon"].round(6)
    out["Y_deg"]            = df["lat"].round(6)

    # --- Population ---
    out["Pop"]              = df["population"].astype(int)
    # ElecPop: electrified population (42% national access, nightlit settlements)
    out["ElecPop"] = np.where(
        df["has_nightlight"],
        (df["population"] * ELEC_RATE_START).astype(int),
        0,
    )

    # --- Cell area (km^2): use hull_area / 1e6 or a default ---
    if "hull_area" in df.columns:
        out["GridCellArea"] = (df["hull_area"] / 1e6).fillna(0.01).clip(lower=0.001)
    else:
        out["GridCellArea"] = 0.01

    # --- Nighttime lights (0-255 scale; nightlit → 50, dark → 0) ---
    out["NightLights"]      = np.where(df["has_nightlight"], 50, 0)

    # --- Urban/rural (OnSSET uses 0=rural, 2=urban; avoid 3 to skip interactive prompt) ---
    out["IsUrban"] = np.where(df["population"] > 5000, 2, 0)

    # --- Solar resource ---
    out["GHI"]              = df["GHI"].round(1)

    # --- Wind (no commercial wind potential in Benin) ---
    out["WindVel"]          = 3.0

    # --- Travel time: dist / assumed 40 km/h road speed ---
    out["TravelHours"]      = (df["dist_nearest_hub_km"] / 40.0).round(3)

    # --- Terrain (Benin is mostly flat; no terrain raster, use country defaults) ---
    out["Elevation"]        = 200.0    # meters, Benin average
    out["Slope"]            = 0.5      # degrees
    out["LandCover"]        = 5        # MODIS: open shrubland/grassland

    # --- Grid distances (km) ---
    # Substation distance is the refined grid-extension cost driver (Extension 3)
    out["SubstationDist"]           = df["dist_to_substations"].round(3)
    # Use freshly computed HV line distances from enrich_transmission.py
    out["CurrentHVLineDist"]        = df["dist_to_hvline_km"].round(3)
    out["PlannedHVLineDist"]        = df["distance_to_planned_transmission_lines"].round(3)
    # MV lines: use substation distance as proxy (OSM MV coverage is too sparse)
    out["CurrentMVLineDist"]        = df["dist_to_substations"].round(3)
    out["PlannedMVLineDist"]        = df["distance_to_planned_transmission_lines"].round(3)
    # Grid extension = min(substation, HV line): settlement can tap off either
    _sub  = pd.to_numeric(df["dist_to_substations"],  errors="coerce")
    _hvl  = pd.to_numeric(df["dist_to_hvline_km"],    errors="coerce")
    out["GridDistCurrent"]          = np.minimum(_sub, _hvl).round(3)
    out["GridDistPlan"]             = df["distance_to_planned_transmission_lines"].round(3)
    # Transformer distance (substation)
    out["TransformerDist"]          = df["dist_to_substations"].round(3)

    # --- Road distance ---
    out["RoadDist"]         = df["dist_main_road_km"].fillna(5.0).round(3)

    # --- Hydropower (no significant hydro in Benin) ---
    out["HydropowerDist"]   = 99999.0
    out["Hydropower"]       = 0.0
    out["HydropowerFID"]    = 0

    # --- Household size ---
    out["NumPeoplePerHH"]   = HOUSEHOLD_SIZE

    # --- OnSSET computed-later columns (initialise to 0) ---
    for col in [
        "PerCapitaDemand", "AgriDemand", "HealthDemand",
        "EducationDemand", "CommercialDemand",
        "ElectrificationOrder", "Conflict",
    ]:
        out[col] = 0

    # --- Extension columns (ignored by vanilla run, used by extended run) ---
    out["mean_rwi"]                  = df["mean_rwi"].round(4)
    out["productive_multiplier_osm"] = df["productive_multiplier"].round(4)
    out["n_health_combined"]         = df["n_health_combined"].astype(int)
    out["n_education_combined"]      = df["n_education_combined"].astype(int)
    out["anchor_load_kwh_yr"]        = df["anchor_load_kwh_yr"].round(1)
    out["growth_factor"]             = df["growth_factor"].round(4)
    out["pop_2030_worldpop"]         = df["pop_2030_worldpop"].astype(int)

    # Admin columns (for downstream filtering)
    out["admin1_name"] = df["admin1_name"].fillna("Unknown")
    out["admin2_name"] = df["admin2_name"].fillna("Unknown")

    # --- Validate ---
    critical = ["Pop", "GHI", "GridDistCurrent", "CurrentHVLineDist"]
    for col in critical:
        n_null = out[col].isna().sum()
        if n_null:
            print(f"  WARN: {col} has {n_null} nulls — filling with 0")
            out[col] = out[col].fillna(0)

    ONSSET_INPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(ONSSET_INPUT_CSV, index=False)

    print(f"Saved OnSSET input -> {ONSSET_INPUT_CSV}")
    print(f"Rows: {len(out):,}  Columns: {len(out.columns)}")
    print(f"Columns: {list(out.columns)}")


if __name__ == "__main__":
    main()
