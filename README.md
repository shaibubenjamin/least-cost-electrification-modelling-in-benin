# Least-Cost Electrification Modelling in Benin

A full end-to-end electrification planning pipeline for Benin, West Africa — from raw settlement data to least-cost technology assignment for 17,175 settlements across a 2026–2041 planning horizon. Built on top of **OnSSET v1.1** with custom extensions for wealth-disaggregated demand, site-specific solar irradiance, and transmission-line proximity.

---

## Results at a glance

| Scenario | Grid | Mini-Grid (PV) | Solar Home System | Total Investment |
|---|---|---|---|---|
| **Baseline** | 85.7% (14,726) | 0.1% (25) | 14.1% (2,424) | **$7.0 B** |
| **Extended** | 51.6% (8,864) | 16.7% (2,873) | 31.7% (5,438) | **$8.9 B** |

- **6,365 settlements (37.1%)** changed technology when wealth-disaggregated demand was applied.
- The extended model shifts ~2,900 poor rural settlements from grid to mini-grid or SHS — reducing over-investment in expensive grid extensions to low-demand areas.

---

## Background

Benin has a national electrification rate of ~42% (World Bank 2023). Reaching SDG7 by 2041 requires connecting ~17,000 currently unelectrified settlements, with technologies chosen to minimise cost while meeting service-level targets. This analysis uses the **Multi-Tier Framework (MTF)** for demand and OnSSET's LCOE-based selection logic to identify the least-cost option per settlement.

---

## Pipeline overview

```
Raw settlement CSV
       │
       ▼
┌─────────────────────────────┐
│  Data Enrichment (Phase 1)  │
│  • WorldPop 2030 population │
│  • Solar GHI (raster)       │
│  • Admin boundaries (GADM)  │
│  • HV transmission distance │
│  • OSM anchor loads (POIs)  │
└────────────┬────────────────┘
             ▼
┌──────────────────────────────┐
│  OnSSET Input Prep (Phase 2) │
│  • 43-column schema          │
│  • GridDistCurrent = min(    │
│      dist_to_substation,     │
│      dist_to_hvline)         │
└────────────┬─────────────────┘
             ▼
    ┌────────┴────────┐
    ▼                 ▼
Baseline Run      Extended Run
(vanilla)         (wealth tiers)
    │                 │
    └────────┬────────┘
             ▼
┌──────────────────────────────┐
│  Comparison & Figures        │
│  delta.csv + 5 cartographic  │
│  figures (PNG)               │
└────────────┬─────────────────┘
             ▼
┌──────────────────────────────┐
│  Web Dashboard               │
│  FastAPI + Leaflet           │
│  • Interactive map           │
│  • Department filter         │
│  • Click-through popups      │
└──────────────────────────────┘
```

---

## Repository structure

```
.
├── src/
│   ├── config.py                  # All paths & parameters in one place
│   ├── enrich_solar.py            # Extract GHI per settlement (rasterio)
│   ├── enrich_worldpop.py         # WorldPop 2030 population projection
│   ├── enrich_admin.py            # Admin boundary join (GADM)
│   ├── enrich_transmission.py     # Distance to HV transmission lines
│   ├── merge_poi_enrichment.py    # OSM anchor loads (schools, clinics, towers)
│   ├── prepare_onsset_input.py    # Build the 43-column OnSSET CSV
│   ├── run_vanilla_onsset.py      # Baseline OnSSET run (uniform MTF Tier 2/3)
│   ├── run_extended_onsset.py     # Extended run with wealth-tier extension
│   ├── onsset_extensions.py       # Extension: wealth-disaggregated demand
│   ├── compare_results.py         # Join scenarios; compute per-settlement deltas
│   └── build_figures.py           # Cartographic figures (Matplotlib + GeoPandas)
│
├── app/
│   ├── main.py                    # FastAPI server (background-cached endpoints)
│   └── index.html                 # Leaflet dashboard (Z-pattern layout)
│
├── data/
│   └── raw/
│       ├── onsset_input.csv           # 43-col OnSSET input (baseline)
│       ├── onsset_input_extended.csv  # 43-col OnSSET input (extended)
│       └── settlements_enriched_full.csv  # All enrichment columns merged
│
├── outputs/
│   ├── vanilla/results.csv        # Baseline OnSSET results (17,175 rows)
│   ├── extended/results.csv       # Extended OnSSET results
│   └── comparison/delta.csv       # Per-settlement deltas + transition matrix
│
├── figures/
│   ├── fig1_vanilla_tech_map.png  # Baseline technology map (cartographic)
│   ├── fig2_extended_tech_map.png # Extended technology map
│   ├── fig3_delta_map.png         # Settlements that changed technology
│   ├── fig4_tech_mix_bar.png      # Grouped bar chart: tech mix comparison
│   └── fig5_lcoe_histograms.png   # LCOE distribution per technology
│
├── benin_admin_boundary/          # GADM 4.1 shapefiles (BEN L1 + L2)
├── transmission_line/             # Benin HV transmission GeoJSON
├── benin_settlements_cleaned.csv  # Base settlement file (17,175 rows)
├── requirements.txt
└── README.md
```

> **Not committed (large files — see Data Sources below):**
> `Benin_settlement_properties.geojson` (36 MB polygon file),
> `benin_2030_population/` (WorldPop 100m raster),
> `benin_solar_atlass/GHI.tif` (PVGIS solar raster)

---

## Methodology

### 1. Demand estimation

Each settlement's annual electricity demand is estimated using the **Multi-Tier Framework (MTF)**:

```
Annual demand [kWh/yr] = Households × kWh_per_HH_per_yr(tier)
Households             = Population ÷ HH_size (5.2, Benin DHS 2017-18)
```

**MTF tier targets used:**

| Tier | kWh/HH/year | Typical service level |
|---|---|---|
| 1 | 4.5 | Basic lighting |
| 2 | 73 | Lighting + phone charging + fan |
| 3 | 365 | Lighting + TV + productive use |
| 4 | 1,250 | Approaching grid parity |
| 5 | 3,000 | Full household demand |

Baseline: all rural settlements target **MTF Tier 2**; urban settlements **Tier 3**.

**Extended model — wealth disaggregation (Extension 1):**  
Settlements are ranked by Meta's **Relative Wealth Index (RWI)**. The poorest quartile (Q1) receives demand downscaled to Tier 1 (multiplier = 38.7/219 = **0.177**); the richest quartile (Q4) is upscaled to Tier 3 (multiplier = 803/219 = **3.67**). Middle quartiles unchanged. Large urban centres (population > threshold) are excluded from adjustment.

**Demand growth:**  
Demand grows linearly from 2026 to 2041 as electrification rate rises from 42% → 95% (SDG7), consistent with OnSSET's two-step planning approach (intermediate year 2033, final year 2041).

**Productive and institutional demand (optional anchor loads):**

| Facility | kWh/year |
|---|---|
| Health clinic | 25,000 |
| School | 4,500 |
| Telecom tower | 26,000 |
| Water pump | 5,500 |

OSM point-of-interest data was used to identify settlements with these facilities and add anchor loads accordingly.

---

### 2. Technology options and cost model

Three technologies are compared using **LCOE (Levelised Cost of Electricity, $/kWh)**:

#### National Grid Extension
- **CAPEX:** $25,000/km for MV line + $375/HH for LV network + connection
- **OPEX:** 3% of CAPEX/year
- **Losses:** 18% transmission and distribution
- **Wholesale cost:** $0.12/kWh (CEB tariff)
- **Lifetime:** 30 years, **Discount rate:** 8%
- **Key driver:** Distance to nearest substation or HV line (`GridDistCurrent = min(dist_substation, dist_HVline)`)

#### Mini-Grid (Solar PV + Battery)
- **CAPEX:** $2,900/kW (all-in: PV panels + 4h battery storage + BOS) — Global Electrification Platform West Africa reference
- **OPEX:** 4% of CAPEX/year
- **Within-village distribution:** $150/HH connection
- **Battery storage:** 4 hours autonomy
- **Oversizing factor:** 4.5× peak load
- **Lifetime:** 20 years

#### Solar Home System (SHS)
- **CAPEX:** $350/system (pay-as-you-go)
- **Annual service fee:** $25/HH/year (PAYG)
- **Service level:** MTF Tier 1–2 (100 kWh/HH/year cap)
- **Lifetime:** 10 years

**LCOE formula:**

```
LCOE = (CAPEX × CRF + OPEX_annual + Fuel_cost) / Annual_kWh_generated

CRF (Capital Recovery Factor) = r(1+r)^n / ((1+r)^n - 1)
  where r = discount rate, n = technology lifetime
```

The least-cost technology for each settlement is whichever of the three yields the lowest LCOE, given its population, distance to grid, and demand tier.

---

### 3. OnSSET configuration

**OnSSET v1.1a6** was installed from PyPI:
```bash
pip install onsset
```

A **Python 3.14 compatibility patch** was applied to the installed package (replacing deprecated `pkg_resources` with `importlib.metadata`).

**Key configuration decisions:**

| Parameter | Value | Rationale |
|---|---|---|
| `start_year` | 2026 | Current baseline |
| `end_year` | 2041 | 15-year planning horizon (SDG7) |
| `intermediate_year` | 2033 | Two-step electrification |
| `num_people_per_hh` | 5.2 | Benin DHS 2017-18 |
| `grid_cell_area` | auto | From settlement polygon extent |
| `urban_cutoff` | 2000 | Population threshold |

**GridDistCurrent correction:** OnSSET's default uses only substation distance. This analysis uses `GridDistCurrent = min(dist_to_substation, dist_to_HVline_km)`, ensuring settlements near HV corridors correctly see lower grid extension costs.

---

### 4. Extensions made to OnSSET

#### Extension 1 — Wealth-disaggregated demand (`src/onsset_extensions.py`)

OnSSET's `prepare_wtf_tier_columns()` creates uniform demand targets. The extension modifies `ResidentialDemandTier{1-5}` columns **per-settlement** before `set_scenario_variables()` runs, using RWI quartile rank:

```python
def apply_wealth_tier_shift(sp_df):
    rwi = sp_df["mean_rwi"]
    q1_thresh, q3_thresh = rwi.quantile(0.25), rwi.quantile(0.75)
    for idx, row in sp_df.iterrows():
        if row["IsUrban"] == 2:
            continue   # skip cities
        quartile = wealth_quartile(row["mean_rwi"], q1_thresh, q3_thresh)
        multiplier = _TIER_RATIO[RWI_TIER_ADJUSTMENT[quartile]]
        for col in tier_cols:
            sp_df.at[idx, col] *= multiplier
```

This produces a per-settlement demand signal that the LCOE engine sees, shifting ~2,900 settlements from grid to mini-grid or SHS.

#### Extension 2 — HV line proximity in grid distance

```python
# prepare_onsset_input.py
_sub  = pd.to_numeric(df["dist_to_substations"], errors="coerce")
_hvl  = pd.to_numeric(df["dist_to_hvline_km"],   errors="coerce")
out["GridDistCurrent"] = np.minimum(_sub, _hvl).round(3)
```

8,981 settlements are closer to an HV line than to a substation; without this fix their grid LCOE would be overestimated.

#### Extension 3 — Site-specific solar GHI

Rather than a national average GHI, each settlement receives its local GHI value extracted from PVGIS rasters, feeding the mini-grid capacity sizing calculation.

#### Extension 4 — Anchor load uplift

Settlements with schools, clinics, telecom towers, or water pumps receive additional kWh/year demand before LCOE calculation, improving mini-grid business-case viability for those sites.

---

## Installation

```bash
git clone https://github.com/shaibubenjamin/least-cost-electrification-modelling-in-benin.git
cd least-cost-electrification-modelling-in-benin
pip install -r requirements.txt
```

### Data files (not in repo — large)

| File | Source | Notes |
|---|---|---|
| `Benin_settlement_properties.geojson` | Provided dataset | 36 MB polygon file |
| `benin_2030_population/` | WorldPop Project | 100m raster, ~2030 projection |
| `benin_solar_atlass/GHI.tif` | PVGIS / Global Solar Atlas | Annual GHI raster |

Place these in the project root before running enrichment scripts.

---

## Running the pipeline

```bash
# Step 1 — Enrich settlement data
python -m src.enrich_solar
python -m src.enrich_worldpop
python -m src.enrich_admin
python -m src.enrich_transmission
python -m src.merge_poi_enrichment

# Step 2 — Prepare OnSSET input
python -m src.prepare_onsset_input

# Step 3 — Run both OnSSET scenarios
python -m src.run_vanilla_onsset
python -m src.run_extended_onsset

# Step 4 — Compare and generate figures
python -m src.compare_results
python -m src.build_figures

# Step 5 — Launch the interactive dashboard
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

---

## Interactive dashboard

The FastAPI + Leaflet dashboard provides:
- **Settlement map** with technology colour-coding and distinct border patterns per technology
- **Click-through popups**: LCOE, investment, new connections, department/commune, buildings, population
- **Department filter**: Zoom to department, visual highlight of matched settlements, filtered KPI cards
- **Scenario tabs**: Baseline / Extended / Changes (37.1% reclassified)
- **Analysis figures** panel with lightbox view

---

## Key findings

1. **Grid dominance under baseline assumptions** reflects Benin's relatively dense HV network (mean distance to grid = 19.9 km after HV correction). At $25,000/km, grid extension is cheapest for most settlements.

2. **Wealth disaggregation shifts the picture significantly.** Applying MTF tier downscaling to poor rural settlements (which constitute the majority of unconnected population) raises mini-grid and SHS LCOE competitiveness because demand is too low to justify the grid extension capital cost.

3. **Mini-grid viability is highly site-specific.** Of the 17,175 settlements, only those with sufficient population density and moderate grid distance become mini-grid candidates. The GHI enrichment shows northern Benin has 10–15% higher solar resource than the south.

4. **Investment gap is real but manageable.** Extended model costs $1.95 B more than baseline but delivers a more equitable, demand-matched solution. The extra cost buys ~2,900 mini-grids sized for actual community needs.

---

## Limitations

| Limitation | Impact | Mitigation with more time |
|---|---|---|
| Population data is WorldPop 2030 (modelled) | ±20% error in rural settlement populations | Use latest census micro-data |
| Grid extension cost is uniform $25,000/km | Terrain/road penalties ignored | Spatially varying cost surface |
| No grid capacity constraints modelled | May overstate grid extension feasibility | Load flow analysis |
| RWI resolution is ~2.4 km | Intra-settlement wealth variance lost | Higher-resolution consumption data |
| SHS modelled as one tier only | MTF Tier 1-2 cap ignores higher-tier SHS | Multi-tier SHS product stack |
| Diesel price fixed at $1.20/L | Volatile; affects MG_Diesel/SA_Diesel competitiveness | Sensitivity analysis |
| No grid reinforcement cost | Understates grid costs near capacity limits | Network planning data from SBEE |

---

## Data sources

| Dataset | Source |
|---|---|
| Settlement boundaries & attributes | Provided dataset |
| WorldPop 2030 population (100m) | worldpop.org |
| Solar GHI raster | Global Solar Atlas / PVGIS |
| Admin boundaries (GADM 4.1) | gadm.org |
| HV transmission lines | Provided dataset |
| Relative Wealth Index (RWI) | data.humdata.org / Meta AI |
| OSM Points of Interest | OpenStreetMap via Overpass API |
| OnSSET electrification model | github.com/OnSSET/onsset |
| MTF tier definitions | World Bank ESMAP MTF 2020 |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
