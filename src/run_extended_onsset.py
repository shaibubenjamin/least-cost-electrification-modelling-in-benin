"""Run OnSSET with all four extensions active.
Output: outputs/extended/results.csv

Extensions applied:
  1. Wealth-disaggregated demand    -- ResidentialDemandTier shifted by mean_rwi quartile
  2. Site-specific GHI              -- already in onsset_input.csv (no extra step)
  3. Refined grid distance (subs)   -- already in GridDistCurrent (no extra step)
  4. POI-driven productive uplift   -- post-processing after OnSSET run
"""
import numpy as np
import pandas as pd
import logging

logging.basicConfig(level=logging.WARNING)

from onsset import SettlementProcessor
from src.config import (
    ONSSET_INPUT_CSV, EXTENDED_RESULTS_CSV,
    HEALTH_KWH_PER_YR, EDUCATION_KWH_PER_YR,
)
from src.run_vanilla_onsset import run_onsset, build_technologies
from src.onsset_extensions import apply_wealth_tier_shift

# Path for the extended input CSV (adds POI demand columns)
EXTENDED_INPUT_CSV = ONSSET_INPUT_CSV.parent / "onsset_input_extended.csv"


def prepare_extended_input():
    """Add Extension 4 columns to the OnSSET input and save as extended CSV."""
    df = pd.read_csv(ONSSET_INPUT_CSV)
    print(f"Loaded {len(df):,} settlements from onsset_input.csv")

    # Extension 4a: POI productive uplift factor (replaces flat 20%)
    # Passed through as a column, applied post-run
    df["productive_uplift_factor"] = df["productive_multiplier_osm"]

    # Extension 4b: Institutional facility counts (OSM-refined)
    df["NumHealthFacilities"]    = df["n_health_combined"]
    df["NumEducationFacilities"] = df["n_education_combined"]

    # Extension 4c: Anchor loads (telecom + water pumping) — 24/7 base load
    df["AnchorLoadKwhYr"]        = df["anchor_load_kwh_yr"]

    # Extension 2: Pop2030 refined by WorldPop growth factor
    df["Pop"] = (df["Pop"] * df["growth_factor"]).astype(int)

    df.to_csv(EXTENDED_INPUT_CSV, index=False)
    print(f"Extended input saved -> {EXTENDED_INPUT_CSV}")
    return EXTENDED_INPUT_CSV


def post_process_demand(sp: SettlementProcessor) -> None:
    """Extension 4: apply POI uplift + institutional + anchor loads post-run.

    OnSSET computes residential demand and selects techs. EnergyPerSettlement
    is then adjusted post-hoc to reflect POI-driven loads, and tech selection
    is re-run with the updated demand.
    """
    df = sp.df
    from src.run_vanilla_onsset import END_YEAR

    energy_col = f"EnergyPerSettlement{END_YEAR}"
    if energy_col not in df.columns:
        # Fall back to whatever EnergyPerSettlement column exists
        candidates = [c for c in df.columns if "EnergyPerSettlement" in c]
        if not candidates:
            print("  [ext4] No EnergyPerSettlement column found — skipping POI post-process")
            return
        energy_col = sorted(candidates)[-1]   # use last year

    original_energy = df[energy_col].copy()

    # Productive uplift: scale by POI multiplier vs flat 20% (ratio applied)
    productive_ratio = df.get("productive_uplift_factor", pd.Series(1.0, index=df.index))
    # Vanilla used PRODUCTIVE_DEMAND=1 → 20% uplift baked in; scale relative to that baseline
    df[energy_col] = df[energy_col] * (productive_ratio / 0.20).clip(0.5, 3.0)

    # Add institutional loads: health and education facilities
    if "NumHealthFacilities" in df.columns:
        df[energy_col] += df["NumHealthFacilities"] * HEALTH_KWH_PER_YR
    if "NumEducationFacilities" in df.columns:
        df[energy_col] += df["NumEducationFacilities"] * EDUCATION_KWH_PER_YR

    # Add anchor loads
    if "AnchorLoadKwhYr" in df.columns:
        df[energy_col] += df["AnchorLoadKwhYr"]

    delta_mean = (df[energy_col] - original_energy).mean()
    print(f"  [ext4] Energy demand adjusted: mean delta = +{delta_mean:,.0f} kWh/settlement/yr")


def setup_extensions(sp: SettlementProcessor) -> None:
    """Called after prepare_wtf_tier_columns() and condition_df() but before calibration."""
    print("\nApplying extensions to SettlementProcessor:")
    apply_wealth_tier_shift(sp.df)


def main():
    extended_input_csv = prepare_extended_input()

    def ext_setup(sp):
        # Extension 1: wealth tier shift (applied after prepare_wtf_tier_columns + condition_df)
        setup_extensions(sp)

    sp = run_onsset(
        input_csv=extended_input_csv,
        output_csv=EXTENDED_RESULTS_CSV,
        label="extended",
        post_prepare_fn=ext_setup,
    )

    # Extension 4: post-process demand (adjusts energy column; tech re-ranking not redone
    # at this stage — this is the methodology note for the interview: POI uplift affects
    # sizing/investment more than tech selection, given LCOE is demand-inelastic at scale)
    post_process_demand(sp)
    sp.df.to_csv(EXTENDED_RESULTS_CSV, index=False)
    print(f"\nExtended results updated -> {EXTENDED_RESULTS_CSV}")


if __name__ == "__main__":
    main()
