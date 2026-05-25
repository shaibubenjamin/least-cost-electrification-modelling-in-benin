"""FastAPI web application — Benin Electrification Explorer.

Endpoints:
  GET /                            → serves index.html
  GET /api/stats                   → summary statistics (JSON)
  GET /api/stats/filtered          → stats filtered to admin1/admin2
  GET /api/map                     → settlement points (fast, for delta view)
  GET /api/delta                   → settlements that changed technology
  GET /api/admin                   → aggregated stats by department
  GET /api/geodata/settlements     → settlement polygons + classification (CACHED)
  GET /api/geodata/transmission    → HV transmission lines GeoJSON
  GET /api/geodata/boundary        → department boundaries GeoJSON
"""
import json
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    VANILLA_RESULTS_CSV, EXTENDED_RESULTS_CSV, COMPARISON_CSV,
    FIGURES_DIR, END_YEAR, ADMIN1_SHP,
)

TL_GEOJSON          = PROJECT_ROOT / "transmission_line" / "Benin_existing_transmission_lines_2017 (2).geojson"
SETTLEMENT_POLYGONS = PROJECT_ROOT / "Benin_settlement_properties.geojson"

TECH_COL = f"MinimumOverall{END_YEAR}"
LCOE_COL = f"MinimumOverallLCOE{END_YEAR}"
INV_COL  = f"InvestmentCost{END_YEAR}"
CONN_COL = f"NewConnections{END_YEAR}"

TECH_LABEL_MAP = {
    f"Grid{END_YEAR}":      "Grid",
    f"MG_PV{END_YEAR}":     "MG_PV",
    f"SA_PV{END_YEAR}":     "SA_PV",
    f"MG_Diesel{END_YEAR}": "MG_Diesel",
    f"SA_Diesel{END_YEAR}": "SA_Diesel",
    f"MG_Hydro{END_YEAR}":  "MG_Hydro",
    f"MG_Wind{END_YEAR}":   "MG_Wind",
}

# ── In-memory cache ────────────────────────────────────────────────────────
_cache: dict = {
    "vanilla_df":   None,
    "extended_df":  None,
    "delta_df":     None,
    "settlements_vanilla_geojson":  None,   # pre-built JSON string
    "settlements_extended_geojson": None,
    "boundary_geojson": None,
    "hvlines_geojson":  None,
    "admin_data": None,
}
_cache_lock = threading.Lock()


def _build_settlement_geojson(scenario: str) -> str:
    """Load polygons, simplify, join classification, return JSON string."""
    print(f"  [cache] Building settlement GeoJSON for '{scenario}'...")
    gdf = gpd.read_file(str(SETTLEMENT_POLYGONS))
    gdf["geometry"] = gdf["geometry"].simplify(0.002, preserve_topology=True)

    df = _load_vanilla() if scenario == "vanilla" else _load_extended()
    df["tech"] = _clean_tech(df[TECH_COL])
    df["lcoe"] = pd.to_numeric(df.get(LCOE_COL, np.nan), errors="coerce").round(4)

    # Total investment across both planning steps (USD)
    inv2033 = pd.to_numeric(df.get("InvestmentCost2033", 0), errors="coerce").fillna(0)
    inv2041 = pd.to_numeric(df.get(INV_COL, 0), errors="coerce").fillna(0)
    df["inv_total"] = (inv2033 + inv2041).round(0).astype(int)

    conn = pd.to_numeric(df.get(CONN_COL, np.nan), errors="coerce")
    df["new_conn"] = conn.round(0).fillna(0).astype(int)

    gdf["lon_r"] = gdf["lon"].round(4)
    gdf["lat_r"] = gdf["lat"].round(4)
    df["lon_r"]  = df["X_deg"].round(4)
    df["lat_r"]  = df["Y_deg"].round(4)

    rcols = ["lon_r", "lat_r", "tech", "lcoe", "inv_total", "new_conn"]
    for c in ["admin1_name", "admin2_name", "Pop"]:
        if c in df.columns:
            rcols.append(c)

    merged = gdf.merge(df[rcols], on=["lon_r", "lat_r"], how="left")

    keep = ["tech", "lcoe", "inv_total", "new_conn",
            "admin1_name", "admin2_name",
            "Pop", "population", "village_name", "num_buildings",
            "lon", "lat", "geometry"]
    keep = [c for c in keep if c in merged.columns]
    out = merged[keep].to_crs("EPSG:4326")
    result = out.to_json()
    print(f"  [cache] '{scenario}' settlement GeoJSON ready ({len(result)//1024}KB)")
    return result


def _build_boundary_geojson() -> str:
    print("  [cache] Building boundary GeoJSON...")
    gdf = gpd.read_file(str(ADMIN1_SHP))[["geometry", "NAME_1"]].copy()
    gdf = gdf.to_crs("EPSG:4326")
    gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)
    return gdf.to_json()


def _build_hvlines_geojson() -> str:
    print("  [cache] Building HV lines GeoJSON...")
    gdf = gpd.read_file(str(TL_GEOJSON))
    benin = gdf[
        gdf["Country_1"].isin(["BJ", "BEN"]) |
        gdf["Country_2"].isin(["BJ", "BEN"])
    ][["geometry", "Voltage_KV", "Situation"]].copy()
    return benin.to_crs("EPSG:4326").to_json()


def _build_admin_data() -> dict:
    print("  [cache] Building admin summary...")
    delta = _load_delta()
    van   = _load_vanilla()
    if "admin1_name" not in delta.columns:
        return {"departments": []}

    van_tech = _clean_tech(van[TECH_COL]) if TECH_COL in van.columns else pd.Series(dtype=str)
    van_inv  = (van.get("InvestmentCost2033", pd.Series(0.0)) +
                van.get(INV_COL, pd.Series(0.0)))

    dept_df = pd.DataFrame({
        "admin1":        delta["admin1_name"].values,
        "tech_vanilla":  delta["tech_vanilla"].values,
        "tech_extended": delta["tech_extended"].values,
        "tech_changed":  delta["tech_changed"].values,
        "inv_van":       van_inv.values if len(van_inv) == len(delta) else 0.0,
    })

    out = []
    for dept, grp in dept_df.groupby("admin1"):
        van_mix = grp["tech_vanilla"].value_counts().to_dict()
        ext_mix = grp["tech_extended"].value_counts().to_dict()
        out.append({
            "department":        dept,
            "n_settlements":     int(len(grp)),
            "n_changed":         int(grp["tech_changed"].sum()),
            "pct_changed":       round(100 * grp["tech_changed"].mean(), 1),
            "vanilla_tech_mix":  {k: int(v) for k, v in van_mix.items()},
            "extended_tech_mix": {k: int(v) for k, v in ext_mix.items()},
            "investment_van_m":  round(float(grp["inv_van"].sum()) / 1e6, 2),
        })
    out.sort(key=lambda x: x["n_settlements"], reverse=True)
    return {"departments": out}


def _prime_cache():
    """Pre-build all expensive caches in a background thread."""
    print("[cache] Starting cache warm-up...")
    with _cache_lock:
        _cache["vanilla_df"]  = pd.read_csv(VANILLA_RESULTS_CSV, low_memory=False)
        _cache["extended_df"] = pd.read_csv(EXTENDED_RESULTS_CSV, low_memory=False)
        _cache["delta_df"]    = pd.read_csv(COMPARISON_CSV)
        print("  [cache] DataFrames loaded.")

        _cache["boundary_geojson"] = _build_boundary_geojson()
        _cache["hvlines_geojson"]  = _build_hvlines_geojson()
        _cache["admin_data"]       = _build_admin_data()

        _cache["settlements_vanilla_geojson"]  = _build_settlement_geojson("vanilla")
        _cache["settlements_extended_geojson"] = _build_settlement_geojson("extended")
    print("[cache] Warm-up complete.")


# Start cache warm-up in a background thread so the server starts instantly
_cache_thread = threading.Thread(target=_prime_cache, daemon=True)
_cache_thread.start()


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Benin Electrification Explorer", version="1.0")

app.mount("/figures", StaticFiles(directory=str(FIGURES_DIR)), name="figures")
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Data helpers ───────────────────────────────────────────────────────────
def _load_vanilla() -> pd.DataFrame:
    if _cache["vanilla_df"] is not None:
        return _cache["vanilla_df"]
    return pd.read_csv(VANILLA_RESULTS_CSV, low_memory=False)


def _load_extended() -> pd.DataFrame:
    if _cache["extended_df"] is not None:
        return _cache["extended_df"]
    return pd.read_csv(EXTENDED_RESULTS_CSV, low_memory=False)


def _load_delta() -> pd.DataFrame:
    if _cache["delta_df"] is not None:
        return _cache["delta_df"]
    return pd.read_csv(COMPARISON_CSV)


def _clean_tech(series) -> pd.Series:
    return pd.Series(series).map(lambda v: TECH_LABEL_MAP.get(str(v), str(v)))


def _total_inv(df: pd.DataFrame) -> float:
    inv2033 = df["InvestmentCost2033"].sum() if "InvestmentCost2033" in df.columns else 0
    inv2041 = df[INV_COL].sum() if INV_COL in df.columns else 0
    return float(inv2033 + inv2041) / 1e6


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return JSONResponse({"error": "index.html not found"}, status_code=404)


@app.get("/api/stats")
def stats():
    try:
        van   = _load_vanilla()
        ext   = _load_extended()
        delta = _load_delta()
        van_mix = _clean_tech(van[TECH_COL]).value_counts().to_dict() if TECH_COL in van.columns else {}
        ext_mix = _clean_tech(ext[TECH_COL]).value_counts().to_dict() if TECH_COL in ext.columns else {}
        inv_van = _total_inv(van)
        inv_ext = _total_inv(ext)
        return {
            "n_settlements": int(len(delta)),
            "end_year": END_YEAR,
            "vanilla":  {"tech_mix": {k: int(v) for k, v in van_mix.items()}, "investment_m_usd": round(inv_van, 1)},
            "extended": {"tech_mix": {k: int(v) for k, v in ext_mix.items()}, "investment_m_usd": round(inv_ext, 1)},
            "delta": {
                "n_changed":             int(delta["tech_changed"].sum()),
                "pct_changed":           round(100 * delta["tech_changed"].mean(), 1),
                "investment_delta_m_usd": round(inv_ext - inv_van, 1),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/filtered")
def stats_filtered(admin1: str = "", admin2: str = ""):
    try:
        van = _load_vanilla()
        ext = _load_extended()
        delta = _load_delta()

        def flt(df):
            if admin2 and "admin2_name" in df.columns:
                return df[df["admin2_name"] == admin2]
            if admin1 and "admin1_name" in df.columns:
                return df[df["admin1_name"] == admin1]
            return df

        van_f, ext_f, delta_f = flt(van), flt(ext), flt(delta)
        van_mix = _clean_tech(van_f[TECH_COL]).value_counts().to_dict() if TECH_COL in van_f.columns else {}
        ext_mix = _clean_tech(ext_f[TECH_COL]).value_counts().to_dict() if TECH_COL in ext_f.columns else {}
        inv_van = _total_inv(van_f)
        inv_ext = _total_inv(ext_f)

        return {
            "filter":       {"admin1": admin1, "admin2": admin2},
            "n_settlements": int(len(van_f)),
            "end_year":      END_YEAR,
            "vanilla":  {"tech_mix": {k: int(v) for k, v in van_mix.items()}, "investment_m_usd": round(inv_van, 1)},
            "extended": {"tech_mix": {k: int(v) for k, v in ext_mix.items()}, "investment_m_usd": round(inv_ext, 1)},
            "delta": {
                "n_changed":             int(delta_f["tech_changed"].sum()) if "tech_changed" in delta_f else 0,
                "pct_changed":           round(100 * delta_f["tech_changed"].mean(), 1) if "tech_changed" in delta_f else 0,
                "investment_delta_m_usd": round(inv_ext - inv_van, 1),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/map")
def map_data(scenario: str = "vanilla", max_points: int = 20000):
    try:
        df = _load_vanilla() if scenario == "vanilla" else _load_extended()
        if TECH_COL not in df.columns:
            raise HTTPException(status_code=404, detail=f"{TECH_COL} not in results")
        df = df.copy()
        df["tech"] = _clean_tech(df[TECH_COL])
        cols = ["X_deg", "Y_deg", "tech"]
        for c in [LCOE_COL, "Pop", "admin1_name"]:
            if c in df.columns:
                cols.append(c)
        out = df[cols].dropna(subset=["X_deg", "Y_deg"])
        if len(out) > max_points:
            out = out.sample(n=max_points, random_state=42)
        records = out.to_dict(orient="records")
        return JSONResponse({"scenario": scenario, "count": len(records), "settlements": records})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/delta")
def delta_data():
    try:
        delta = _load_delta()
        changed = delta[delta["tech_changed"]].copy()
        cols = ["X_deg", "Y_deg", "tech_vanilla", "tech_extended"]
        for c in ["lcoe_delta", "admin1_name"]:
            if c in delta.columns:
                cols.append(c)
        records = changed[cols].to_dict(orient="records")
        return JSONResponse({"n_changed": len(records), "settlements": records})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geodata/settlements")
def geodata_settlements(scenario: str = "vanilla"):
    """Serve pre-cached simplified settlement polygons + classification."""
    cache_key = f"settlements_{scenario}_geojson"
    cached = _cache.get(cache_key)
    if cached is None:
        # Cache not ready yet — build synchronously (first request only)
        cached = _build_settlement_geojson(scenario)
        _cache[cache_key] = cached
    return Response(content=cached, media_type="application/json")


@app.get("/api/geodata/transmission")
def geodata_transmission():
    cached = _cache.get("hvlines_geojson")
    if cached is None:
        cached = _build_hvlines_geojson()
        _cache["hvlines_geojson"] = cached
    return Response(content=cached, media_type="application/json")


@app.get("/api/geodata/boundary")
def geodata_boundary():
    cached = _cache.get("boundary_geojson")
    if cached is None:
        cached = _build_boundary_geojson()
        _cache["boundary_geojson"] = cached
    return Response(content=cached, media_type="application/json")


@app.get("/api/admin")
def admin_summary():
    cached = _cache.get("admin_data")
    if cached is None:
        cached = _build_admin_data()
        _cache["admin_data"] = cached
    return JSONResponse(cached)


@app.get("/api/cache_status")
def cache_status():
    """Check which cached items are ready."""
    return {k: (v is not None) for k, v in _cache.items()}
