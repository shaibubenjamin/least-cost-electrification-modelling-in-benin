"""Run OnSSET 1.1a6 with West Africa defaults to produce the vanilla baseline.
Call sequence matches the actual runner.scenario() flow.
Output: outputs/vanilla/results.csv
"""
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING)   # suppress verbose OnSSET logging

from onsset import SettlementProcessor, Technology
from src.config import (
    ONSSET_INPUT_CSV, VANILLA_RESULTS_CSV,
    DISCOUNT_RATE_REAL, START_YEAR, END_YEAR,
    GRID_MV_PER_KM, GRID_TD_LOSS, GRID_WHOLESALE_PER_KWH, GRID_OM_PCT, GRID_LIFETIME,
    MG_PV_PER_KW, MG_OM_PCT, MG_LIFETIME,
    SHS_CAPEX, SHS_PAYGO_PER_YR, SHS_LIFETIME,
    HOUSEHOLD_SIZE, ELEC_RATE_START,
)

# ---- Scenario parameters ----
RURAL_TIER          = 2          # MTF Tier 2 — ESMAP West Africa baseline
URBAN_TIER          = 3
PRODUCTIVE_DEMAND   = 1          # 20% residential uplift (OnSSET default flag)
INTERMEDIATE_YEAR   = 2033
TIME_STEP_1         = INTERMEDIATE_YEAR - START_YEAR   # 7 years
TIME_STEP_2         = END_YEAR - INTERMEDIATE_YEAR     # 8 years
MAX_GRID_DIST       = 50.0       # km — max grid extension distance

# ---- National calibration totals (Benin WB 2023) ----
POP_ACTUAL          = 13_712_000
POP_FUTURE_HIGH     = 17_500_000
POP_FUTURE_LOW      = 15_800_000
URBAN_CURRENT       = 0.49
URBAN_FUTURE        = 0.58
ELEC_RATE_URBAN     = 0.67
ELEC_RATE_RURAL     = 0.18


def build_technologies():
    Technology.set_default_values(
        base_year=START_YEAR,
        start_year=START_YEAR,
        end_year=END_YEAR,
        discount_rate=DISCOUNT_RATE_REAL,
    )
    grid_calc = Technology(
        om_of_td_lines=GRID_OM_PCT,
        distribution_losses=GRID_TD_LOSS,
        connection_cost_per_hh=375,
        base_to_peak_load_ratio=0.8,
        capacity_factor=1.0,
        tech_life=GRID_LIFETIME,
        grid_capacity_investment=GRID_MV_PER_KM,
        grid_penalty_ratio=1.0,
        grid_price=GRID_WHOLESALE_PER_KWH,
    )
    mg_pv_calc = Technology(
        om_of_td_lines=0.02, distribution_losses=0.05,
        connection_cost_per_hh=150, base_to_peak_load_ratio=0.85,
        tech_life=MG_LIFETIME, om_costs=MG_OM_PCT,
        capital_cost={float("inf"): MG_PV_PER_KW}, mini_grid=True,
    )
    sa_pv_calc = Technology(
        base_to_peak_load_ratio=0.9, tech_life=SHS_LIFETIME,
        om_costs=SHS_PAYGO_PER_YR / SHS_CAPEX,
        capital_cost={
            float("inf"): SHS_CAPEX * 20,
            1:    SHS_CAPEX * 13,
            0.1:  SHS_CAPEX * 18,
            0.05: SHS_CAPEX * 25,
            0.02: SHS_CAPEX * 27,
        },
        standalone=True,
    )
    mg_diesel_calc = Technology(
        om_of_td_lines=0.02, distribution_losses=0.05,
        connection_cost_per_hh=100, base_to_peak_load_ratio=0.85,
        capacity_factor=0.7, tech_life=15, om_costs=0.1,
        capital_cost={float("inf"): 721}, mini_grid=True,
    )
    sa_diesel_calc = Technology(
        base_to_peak_load_ratio=0.9, capacity_factor=0.5,
        tech_life=10, om_costs=0.1,
        capital_cost={float("inf"): 938}, standalone=True,
    )
    mg_hydro_calc = Technology(
        om_of_td_lines=0.02, distribution_losses=0.05,
        connection_cost_per_hh=100, base_to_peak_load_ratio=0.85,
        capacity_factor=0.5, tech_life=30, om_costs=0.03,
        capital_cost={float("inf"): 3000}, mini_grid=True,
    )
    mg_wind_calc = Technology(
        om_of_td_lines=0.02, distribution_losses=0.05,
        connection_cost_per_hh=100, base_to_peak_load_ratio=0.85,
        capital_cost={float("inf"): 3750}, om_costs=0.02,
        tech_life=20, mini_grid=True,
    )
    return grid_calc, mg_pv_calc, sa_pv_calc, mg_diesel_calc, sa_diesel_calc, mg_hydro_calc, mg_wind_calc


def run_onsset(input_csv, output_csv, label="vanilla", post_prepare_fn=None):
    """Run OnSSET following the exact runner.scenario() call order.
    post_prepare_fn(sp): optional hook called AFTER prepare_wtf_tier_columns + condition_df,
                         used by extended run to apply wealth tier shift before calibration.
    """
    print(f"\n{'='*60}")
    print(f"OnSSET run: {label}")
    print(f"{'='*60}")

    sp = SettlementProcessor(str(input_csv))
    print(f"Loaded {len(sp.df):,} settlements")

    sp.prepare_wtf_tier_columns(
        num_people_per_hh_rural=HOUSEHOLD_SIZE,
        num_people_per_hh_urban=4.5,
        tier_1=38.7, tier_2=219, tier_3=803, tier_4=2117, tier_5=2993,
    )
    sp.condition_df()
    sp.df.reset_index(drop=True, inplace=True)   # condition_df sorts; elec_extension needs sequential idx

    # Extension hook runs AFTER tier columns and condition_df, BEFORE calibration
    if post_prepare_fn:
        post_prepare_fn(sp)
    sp.df["GridPenalty"] = sp.grid_penalties(sp.df)
    sp.df["WindCF"] = sp.calc_wind_cfs()

    pop_modelled, urban_modelled = sp.calibrate_current_pop_and_urban(POP_ACTUAL, URBAN_CURRENT)
    sp.project_pop_and_urban(
        pop_modelled=pop_modelled,
        pop_future_high=POP_FUTURE_HIGH,
        pop_future_low=POP_FUTURE_LOW,
        urban_modelled=urban_modelled,
        urban_future=URBAN_FUTURE,
        start_year=START_YEAR,
        end_year=END_YEAR,
        intermediate_year=INTERMEDIATE_YEAR,
    )
    _em, _re, _ue = sp.elec_current_and_future(
        elec_actual=ELEC_RATE_START,
        elec_actual_urban=ELEC_RATE_URBAN,
        elec_actual_rural=ELEC_RATE_RURAL,
        start_year=START_YEAR,
    )
    print(f"Electrification modelled: {_em:.3f}  rural: {_re:.3f}  urban: {_ue:.3f}")

    sp.current_mv_line_dist()

    grid_calc, mg_pv_calc, sa_pv_calc, mg_diesel_calc, sa_diesel_calc, mg_hydro_calc, mg_wind_calc = (
        build_technologies()
    )
    diesel_costs_sa = {"diesel_price": 1.20, "efficiency": 0.28,
                       "diesel_truck_consumption": 14, "diesel_truck_volume": 300}
    diesel_costs_mg = {"diesel_price": 1.20, "efficiency": 0.33,
                       "diesel_truck_consumption": 33.7, "diesel_truck_volume": 15000}

    years_of_analysis = [INTERMEDIATE_YEAR, END_YEAR]
    elec_limits       = {INTERMEDIATE_YEAR: 0.70, END_YEAR: 1.0}
    time_steps_map    = {INTERMEDIATE_YEAR: TIME_STEP_1, END_YEAR: TIME_STEP_2}
    end_year_pop_flag = 1    # High scenario

    grid_investment = 0
    for year in years_of_analysis:
        time_step  = time_steps_map[year]
        elec_limit = elec_limits[year]
        print(f"\n  Year {year}  (step={time_step}, target={elec_limit:.0%})")

        sp.set_scenario_variables(
            year=year,
            num_people_per_hh_rural=HOUSEHOLD_SIZE,
            num_people_per_hh_urban=4.5,
            time_step=time_step,
            start_year=START_YEAR,
            urban_tier=URBAN_TIER,
            rural_tier=RURAL_TIER,
            end_year_pop=end_year_pop_flag,
            productive_demand=PRODUCTIVE_DEMAND,
        )

        sp.diesel_cost_columns(diesel_costs_sa, diesel_costs_mg, year)

        (sa_diesel_inv, sa_pv_inv, mg_diesel_inv, mg_pv_inv,
         mg_wind_inv, mg_hydro_inv) = sp.calculate_off_grid_lcoes(
            mg_hydro_calc, mg_wind_calc, mg_pv_calc, sa_pv_calc,
            mg_diesel_calc, sa_diesel_calc, year, END_YEAR, time_step,
        )

        grid_investment, grid_cap_limit, grid_conn_limit = sp.pre_electrification(
            grid_price=GRID_WHOLESALE_PER_KWH,
            year=year, time_step=time_step, end_year=END_YEAR,
            grid_calc=grid_calc,
            grid_capacity_limit=9_999_999_999,
            grid_connect_limit=9_999_999_999,
        )

        (sp.df[f"Grid{year}"], sp.df[f"MinGridDist{year}"],
         sp.df[f"ElectrificationOrder{year}"], sp.df["MVConnectDist"],
         grid_investment) = sp.elec_extension(
            grid_calc=grid_calc,
            max_dist=MAX_GRID_DIST,
            year=year,
            start_year=START_YEAR,
            end_year=END_YEAR,
            time_step=time_step,
            grid_capacity_limit=grid_cap_limit,
            grid_connect_limit=grid_conn_limit,
            auto_intensification=0,
            prioritization=2,
            new_investment=grid_investment,
        )

        sp.results_columns(year=year, time_step=time_step, prio=2, auto_intensification=0)

        sp.calculate_investments(
            sa_diesel_investment=sa_diesel_inv,
            sa_pv_investment=sa_pv_inv,
            mg_diesel_investment=mg_diesel_inv,
            mg_pv_investment=mg_pv_inv,
            mg_wind_investment=mg_wind_inv,
            mg_hydro_investment=mg_hydro_inv,
            grid_investment=grid_investment,
            year=year,
        )

        sp.apply_limitations(elec_limit, year, time_step, prioritization=2)

        sp.calculate_new_capacity(
            mg_hydro_calc, mg_wind_calc, mg_pv_calc, sa_pv_calc,
            mg_diesel_calc, sa_diesel_calc, grid_calc, year,
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    sp.df.to_csv(output_csv, index=False)
    print(f"\nSaved -> {output_csv}")

    tech_col = f"MinimumOverall{END_YEAR}"
    if tech_col in sp.df.columns:
        print(f"\nTechnology distribution ({label}, year {END_YEAR}):")
        print(sp.df[tech_col].value_counts().to_string())
    else:
        avail = [c for c in sp.df.columns if "Minimum" in c]
        print(f"Expected '{tech_col}'. Available: {avail}")

    return sp


def main():
    run_onsset(ONSSET_INPUT_CSV, VANILLA_RESULTS_CSV, label="vanilla")


if __name__ == "__main__":
    main()
