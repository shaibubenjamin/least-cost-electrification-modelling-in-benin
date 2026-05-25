"""Central configuration — every path and parameter in one place."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ----- Inputs -----
SETTLEMENT_CSV         = PROJECT_ROOT / "benin_settlements_cleaned.csv"
SETTLEMENT_POLYGONS    = PROJECT_ROOT / "Benin_settlement_properties.geojson"
TRANSMISSION_LINES     = PROJECT_ROOT / "Benin_existing_transmission_lines_2017.geojson"
SOLAR_GHI_TIF          = PROJECT_ROOT / "benin_solar_atlass" / "GHI.tif"
WORLDPOP_2030_TIF      = PROJECT_ROOT / "benin_2030_population" / "ben_pop_2030_CN_100m_R2025A_v1.tif"
ADMIN1_SHP             = PROJECT_ROOT / "benin_admin_boundary" / "gadm41_BEN_1.shp"
ADMIN2_SHP             = PROJECT_ROOT / "benin_admin_boundary" / "gadm41_BEN_2.shp"

# ----- Enrichment outputs (intermediate) -----
POI_WEIGHTS_CSV        = PROJECT_ROOT / "data" / "raw" / "poi_weights_per_settlement.csv"
POI_ENRICHED_CSV       = PROJECT_ROOT / "data" / "raw" / "settlements_enriched_poi.csv"
ENRICHED_FULL_CSV      = PROJECT_ROOT / "data" / "raw" / "settlements_enriched_full.csv"

# ----- OnSSET schema -----
ONSSET_INPUT_CSV       = PROJECT_ROOT / "data" / "raw" / "onsset_input.csv"

# ----- OnSSET outputs -----
VANILLA_RESULTS_CSV    = PROJECT_ROOT / "outputs" / "vanilla" / "results.csv"
EXTENDED_RESULTS_CSV   = PROJECT_ROOT / "outputs" / "extended" / "results.csv"
COMPARISON_CSV         = PROJECT_ROOT / "outputs" / "comparison" / "delta.csv"

# ----- Figures -----
FIGURES_DIR            = PROJECT_ROOT / "figures"

# ----- Deliverables -----
DELIVERABLES_DIR       = PROJECT_ROOT / "deliverables"

# ----- Parameters (defensible defaults) -----
HOUSEHOLD_SIZE          = 5.2              # Benin DHS 2017-18
DISCOUNT_RATE_REAL      = 0.08             # OnSSET West Africa default
START_YEAR              = 2026
END_YEAR                = 2041
HORIZON_YEARS           = END_YEAR - START_YEAR
ELEC_RATE_START         = 0.42             # WB Tracking SDG7 2023
ELEC_RATE_END           = 0.95             # SDG7 target

# Cost parameters (USD)
GRID_MV_PER_KM          = 25_000
GRID_LV_CONN_TRANS      = 375              # LV + connection + transformer
GRID_OM_PCT             = 0.03
GRID_TD_LOSS            = 0.18
GRID_WHOLESALE_PER_KWH  = 0.12
GRID_LIFETIME           = 30

MG_PV_PER_KW            = 2_900   # USD/kW all-in: PV panels + 4h battery + BOS (GEP West Africa ref)
MG_BATTERY_PER_KWH      = 350
MG_DIESEL_PER_KW        = 700
MG_BOS_PCT              = 0.25
MG_DIST_PER_CONN        = 600
MG_PV_OVERSIZE_FACTOR   = 4.5
MG_BATTERY_HOURS        = 4
MG_DIESEL_SHARE         = 0.10
MG_DIESEL_FUEL_PER_L    = 1.20
MG_DIESEL_KWH_PER_L     = 3.5
MG_OM_PCT               = 0.04
MG_LIFETIME             = 20

SHS_CAPEX               = 350
SHS_PAYGO_PER_YR        = 25
SHS_KWH_PER_HH_YR       = 100
SHS_LIFETIME            = 10
SHS_MAX_TIER            = 2

# Anchor loads (kWh/yr per facility)
HEALTH_KWH_PER_YR       = 25_000
EDUCATION_KWH_PER_YR    = 4_500
TELECOM_TOWER_KWH_YR    = 26_000           # 3 kW x 8760 hr
WATER_PUMP_KWH_YR       = 5_500            # 15 kWh/day x 365

# Wealth-disaggregated tier adjustment (Extension 1)
RWI_TIER_ADJUSTMENT = {
    "q1": -1,   # poorest 25%
    "q2":  0,
    "q3":  0,
    "q4": +1,   # richest 25%
}

# MTF tier annual kWh/HH
MTF_KWH = {
    1:    4.5,
    2:   73.0,
    3:  365.0,
    4: 1250.0,
    5: 3000.0,
}
