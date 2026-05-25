"""Join vanilla and extended OnSSET results and compute per-settlement deltas.

Output: outputs/comparison/delta.csv
Columns added:
  tech_vanilla, tech_extended  — technology labels (Grid/MG_PV/SA_PV/…)
  tech_changed                 — boolean, True if tech differs
  lcoe_vanilla, lcoe_extended  — LCOE in $/kWh
  lcoe_delta                   — lcoe_extended - lcoe_vanilla
  investment_vanilla, investment_extended, investment_delta  — USD
  new_connections_vanilla, new_connections_extended          — HH count
"""
import pandas as pd
import numpy as np
from src.config import (
    VANILLA_RESULTS_CSV, EXTENDED_RESULTS_CSV, COMPARISON_CSV, END_YEAR,
)

TECH_COL      = f"MinimumOverall{END_YEAR}"
LCOE_COL      = f"MinimumOverallLCOE{END_YEAR}"
INV_COL_2033  = "InvestmentCost2033"
INV_COL_2041  = f"InvestmentCost{END_YEAR}"
CONN_COL      = f"NewConnections{END_YEAR}"
INTERMEDIATE_YEAR = 2033

TECH_LABEL = {
    f"Grid{END_YEAR}":       "Grid",
    f"MG_PV{END_YEAR}":      "MG_PV",
    f"SA_PV{END_YEAR}":      "SA_PV",
    f"MG_Diesel{END_YEAR}":  "MG_Diesel",
    f"SA_Diesel{END_YEAR}":  "SA_Diesel",
    f"MG_Hydro{END_YEAR}":   "MG_Hydro",
    f"MG_Wind{END_YEAR}":    "MG_Wind",
}


def _clean_tech(arr) -> pd.Series:
    return pd.Series(arr).map(lambda v: TECH_LABEL.get(str(v), str(v)))


def load_and_merge():
    van = pd.read_csv(VANILLA_RESULTS_CSV, low_memory=False)
    ext = pd.read_csv(EXTENDED_RESULTS_CSV, low_memory=False)
    print(f"Vanilla : {len(van):,} rows  |  Extended: {len(ext):,} rows")

    key_cols = ["X_deg", "Y_deg"]
    van = van.set_index(key_cols)
    ext = ext.set_index(key_cols)

    delta = pd.DataFrame(index=van.index)

    # Coordinates
    delta = delta.reset_index()

    # Technology
    delta["tech_vanilla"]  = _clean_tech(van[TECH_COL].values) if TECH_COL in van.columns else "unknown"
    delta["tech_extended"] = _clean_tech(ext[TECH_COL].values) if TECH_COL in ext.columns else "unknown"
    delta["tech_changed"]  = delta["tech_vanilla"] != delta["tech_extended"]

    # LCOE
    if LCOE_COL in van.columns and LCOE_COL in ext.columns:
        delta["lcoe_vanilla"]  = van[LCOE_COL].values.astype(float)
        delta["lcoe_extended"] = ext[LCOE_COL].values.astype(float)
        delta["lcoe_delta"]    = delta["lcoe_extended"] - delta["lcoe_vanilla"]
    else:
        print(f"  WARN: {LCOE_COL} not found; skipping LCOE columns")

    # Investment — sum both time steps (2033 + END_YEAR) for the correct planning-period total
    if INV_COL_2033 in van.columns and INV_COL_2041 in van.columns:
        van_total = van[INV_COL_2033].values.astype(float) + van[INV_COL_2041].values.astype(float)
        ext_total = ext[INV_COL_2033].values.astype(float) + ext[INV_COL_2041].values.astype(float)
        delta["investment_vanilla"]  = van_total
        delta["investment_extended"] = ext_total
        delta["investment_delta"]    = ext_total - van_total
    else:
        print(f"  WARN: investment columns not found; skipping")

    # New connections
    if CONN_COL in van.columns and CONN_COL in ext.columns:
        delta["new_connections_vanilla"]  = van[CONN_COL].values.astype(float)
        delta["new_connections_extended"] = ext[CONN_COL].values.astype(float)

    # Pass-through admin columns for maps
    for col in ["admin1_name", "admin2_name"]:
        if col in van.columns:
            delta[col] = van[col].values

    return delta


def print_summary(delta: pd.DataFrame):
    n_changed = delta["tech_changed"].sum()
    pct = 100 * n_changed / len(delta)
    print(f"\n{'='*60}")
    print(f"Comparison summary  ({len(delta):,} settlements)")
    print(f"{'='*60}")
    print(f"Technology changed: {n_changed:,} settlements ({pct:.1f}%)")

    print("\nVanilla tech mix:")
    print(delta["tech_vanilla"].value_counts().to_string())
    print("\nExtended tech mix:")
    print(delta["tech_extended"].value_counts().to_string())

    if "lcoe_delta" in delta.columns:
        print(f"\nLCOE delta (ext - van):  mean={delta['lcoe_delta'].mean():.4f}  "
              f"median={delta['lcoe_delta'].median():.4f}  "
              f"std={delta['lcoe_delta'].std():.4f}  $/kWh")

    if "investment_delta" in delta.columns:
        total_van = delta["investment_vanilla"].sum() / 1e6
        total_ext = delta["investment_extended"].sum() / 1e6
        print(f"\nTotal investment (2033+2041 steps):")
        print(f"  Vanilla:  ${total_van:,.1f}M")
        print(f"  Extended: ${total_ext:,.1f}M")
        print(f"  Delta:    ${total_ext - total_van:+,.1f}M")

    # Transition matrix
    print("\nTransition matrix (vanilla -> extended):")
    matrix = pd.crosstab(delta["tech_vanilla"], delta["tech_extended"], margins=True)
    print(matrix.to_string())


def main():
    delta = load_and_merge()
    print_summary(delta)

    COMPARISON_CSV.parent.mkdir(parents=True, exist_ok=True)
    delta.to_csv(COMPARISON_CSV, index=False)
    print(f"\nSaved -> {COMPARISON_CSV}")
    return delta


if __name__ == "__main__":
    main()
