"""Generate publication-quality cartographic figures for the Benin electrification model.

Figures produced:
  fig1_vanilla_tech_map.png   — Baseline technology map (cartographic)
  fig2_extended_tech_map.png  — Extended technology map (cartographic)
  fig3_delta_map.png          — Technology change map (cartographic)
  fig4_tech_mix_bar.png       — Grouped horizontal bar chart
  fig5_lcoe_histograms.png    — LCOE distribution per technology
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
import matplotlib.ticker as mticker
from pathlib import Path

from src.config import (
    VANILLA_RESULTS_CSV, EXTENDED_RESULTS_CSV, COMPARISON_CSV,
    ADMIN1_SHP, FIGURES_DIR, END_YEAR,
)

# ── Colours ──────────────────────────────────────────────────────────────────
TECH_COLOURS = {
    "Grid":  "#1d6bb8",
    "MG_PV": "#1e8a44",
    "SA_PV": "#e06c1a",
}
CHANGE_COL = "#cc2200"
UNCH_COL   = "#9eaab8"
TECH_COL   = f"MinimumOverall{END_YEAR}"
LCOE_COL   = f"MinimumOverallLCOE{END_YEAR}"
TECH_LABEL = {
    f"Grid{END_YEAR}":  "Grid",
    f"MG_PV{END_YEAR}": "MG_PV",
    f"SA_PV{END_YEAR}": "SA_PV",
}

BENIN_BBOX = (0.8, 6.2, 3.9, 12.4)   # lon_min, lat_min, lon_max, lat_max


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_data():
    v = pd.read_csv(VANILLA_RESULTS_CSV, low_memory=False)
    e = pd.read_csv(EXTENDED_RESULTS_CSV, low_memory=False)
    c = pd.read_csv(COMPARISON_CSV)
    for df in (v, e):
        df["tech"] = df[TECH_COL].map(TECH_LABEL).fillna("Other")
    return v, e, c


def load_admin():
    return gpd.read_file(str(ADMIN1_SHP)).to_crs("EPSG:4326")


def pop_size(pop_series, min_s=1.2, max_s=9.0, clip=5000):
    p = np.clip(pop_series.fillna(0).values, 0, clip)
    if p.max() == 0:
        return np.full(len(p), min_s)
    return min_s + (max_s - min_s) * (p / p.max()) ** 0.5


# ── Cartographic map ──────────────────────────────────────────────────────────
def make_map_fig(df, title, subtitle, legend_handles, admin_gdf, save_path,
                 changed_mask=None):
    fig, ax = plt.subplots(1, 1, figsize=(9, 11), facecolor="white")
    ax.set_facecolor("#ddeeff")   # ocean/background

    # Department fills + outlines
    admin_gdf.plot(ax=ax, color="#f4ede0", edgecolor="#999", linewidth=0.5, zorder=2)
    admin_gdf.boundary.plot(ax=ax, edgecolor="#555", linewidth=0.9, zorder=3)

    # Dept labels
    for _, row in admin_gdf.iterrows():
        pt = row.geometry.centroid
        ax.text(pt.x, pt.y, row["NAME_1"], fontsize=6, ha="center", va="center",
                color="#444", fontstyle="italic", zorder=4,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="#f4ede0")])

    # Graticule at 1° intervals
    for lon in np.arange(1, 4, 1):
        ax.axvline(lon, color="#a8bfd0", linewidth=0.35, linestyle="--", zorder=1, alpha=0.7)
    for lat in np.arange(7, 13, 1):
        ax.axhline(lat, color="#a8bfd0", linewidth=0.35, linestyle="--", zorder=1, alpha=0.7)

    # Settlement points
    sizes = pop_size(df.get("Pop", pd.Series(100, index=df.index)))
    alpha = 0.72

    if changed_mask is not None:
        ax.scatter(df.loc[~changed_mask, "X_deg"], df.loc[~changed_mask, "Y_deg"],
                   c=UNCH_COL, s=sizes[~changed_mask], alpha=0.3, linewidths=0,
                   zorder=5, rasterized=True)
        ax.scatter(df.loc[changed_mask, "X_deg"], df.loc[changed_mask, "Y_deg"],
                   c=CHANGE_COL, s=sizes[changed_mask] * 1.4, alpha=0.85, linewidths=0,
                   zorder=6, rasterized=True)
    else:
        for tech, col in TECH_COLOURS.items():
            mask = df["tech"] == tech
            if mask.sum() == 0:
                continue
            ax.scatter(df.loc[mask, "X_deg"], df.loc[mask, "Y_deg"],
                       c=col, s=sizes[mask], alpha=alpha, linewidths=0,
                       zorder=5, rasterized=True)

    # Extent and aspect
    ax.set_xlim(BENIN_BBOX[0], BENIN_BBOX[2])
    ax.set_ylim(BENIN_BBOX[1], BENIN_BBOX[3])
    ax.set_aspect("equal")

    # Axes — decimal degrees
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}°E"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}°N"))
    ax.tick_params(labelsize=7.5, length=3, color="#888")
    ax.set_xlabel("Longitude", fontsize=8, labelpad=6, color="#555")
    ax.set_ylabel("Latitude",  fontsize=8, labelpad=6, color="#555")
    for spine in ax.spines.values():
        spine.set_edgecolor("#888")
        spine.set_linewidth(0.8)

    # Title block
    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=5, loc="left")
    fig.text(0.13, 0.915, subtitle, fontsize=7.5, color="#555", ha="left")

    # North arrow (top-right corner of axes)
    ax.annotate("", xy=(0.965, 0.975), xytext=(0.965, 0.935),
                xycoords="axes fraction", textcoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color="#1a3a5c", lw=1.6,
                                mutation_scale=10))
    ax.text(0.965, 0.98, "N", transform=ax.transAxes,
            fontsize=9, fontweight="bold", ha="center", va="bottom", color="#1a3a5c")

    # Scale bar — 100 km
    km_per_deg_lon = 111.32 * np.cos(np.radians(9.3))
    scale_km  = 100
    scale_deg = scale_km / km_per_deg_lon
    sb_x = BENIN_BBOX[0] + 0.15
    sb_y = BENIN_BBOX[1] + 0.25
    ax.plot([sb_x, sb_x + scale_deg], [sb_y, sb_y],
            color="#1a3a5c", lw=2.2, solid_capstyle="butt", zorder=8)
    for xx in [sb_x, sb_x + scale_deg]:
        ax.plot([xx, xx], [sb_y - 0.05, sb_y + 0.05], color="#1a3a5c", lw=1.5, zorder=8)
    ax.text(sb_x + scale_deg / 2, sb_y - 0.15, f"{scale_km} km",
            ha="center", fontsize=7, color="#1a3a5c", fontweight="600", zorder=8)
    ax.text(sb_x, sb_y - 0.15, "0", ha="center", fontsize=7, color="#1a3a5c", zorder=8)

    # Legend
    ax.legend(handles=legend_handles, title="Least-Cost Technology",
              title_fontsize=7.5, fontsize=7.5, loc="lower right",
              framealpha=0.93, edgecolor="#bbb", borderpad=0.9,
              handlelength=1.2, handletextpad=0.6, labelspacing=0.45)

    # Metadata text
    ax.text(0.01, 0.005, "CRS: EPSG:4326  |  Decimal degrees",
            transform=ax.transAxes, fontsize=5.5, color="#aaa", va="bottom")
    fig.text(0.13, 0.03,
             "Data: OnSSET v1.1a6 · WorldPop 2030 · Meta RWI · SBTN · GADM · OSM",
             fontsize=5.5, color="#bbb")

    fig.tight_layout(pad=0.6, rect=[0, 0.035, 1, 0.955])
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved {Path(save_path).name}")


# ── Fig 4: horizontal grouped bar ─────────────────────────────────────────────
def make_tech_mix_bar(van, ext, save_path):
    fig, ax = plt.subplots(figsize=(8, 4), facecolor="white")
    ax.set_facecolor("white")

    techs   = list(TECH_COLOURS.keys())
    n_van   = van["tech"].value_counts()
    n_ext   = ext["tech"].value_counts()
    pct_v   = [n_van.get(t, 0) / len(van) * 100 for t in techs]
    pct_e   = [n_ext.get(t, 0) / len(ext) * 100 for t in techs]

    y, h = np.arange(len(techs)), 0.34
    cols  = [TECH_COLOURS[t] for t in techs]

    bars_v = ax.barh(y + h/2, pct_v, height=h, color=cols, alpha=0.52,
                     edgecolor="white", linewidth=0)
    bars_e = ax.barh(y - h/2, pct_e, height=h, color=cols, alpha=0.95,
                     edgecolor="white", linewidth=0)

    for bar, pct in zip(bars_v, pct_v):
        if pct > 0.5:
            ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height()/2,
                    f"{pct:.1f}%", va="center", fontsize=8, color="#666")
    for bar, pct in zip(bars_e, pct_e):
        if pct > 0.5:
            ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height()/2,
                    f"{pct:.1f}%", va="center", fontsize=8.5, color="#111", fontweight="600")

    ax.set_yticks(y)
    ax.set_yticklabels([t.replace("_", "-") for t in techs], fontsize=11)
    ax.set_xlabel("Share of settlements (%)", fontsize=9)
    max_pct = max(max(pct_v), max(pct_e), 1)
    ax.set_xlim(0, max_pct * 1.18)
    ax.set_title("Technology Mix: Baseline vs. Extended Scenario", fontsize=11,
                 fontweight="bold", pad=8, loc="left")

    ax.grid(axis="x", color="#e8ecf0", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#ddd")
    ax.tick_params(labelsize=8.5, color="#ccc")

    legend_handles = [
        mpatches.Patch(facecolor="#888", alpha=0.52, label="Baseline (light)"),
        mpatches.Patch(facecolor="#444", alpha=0.95, label="Extended (solid)"),
    ]
    ax.legend(handles=legend_handles, fontsize=8.5, loc="lower right",
              framealpha=0.9, edgecolor="#ddd", borderpad=0.8)

    fig.tight_layout(pad=1.0)
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved {Path(save_path).name}")


# ── Fig 5: LCOE distributions ──────────────────────────────────────────────────
def make_lcoe_hist(van, ext, save_path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), facecolor="white")
    fig.suptitle("LCOE Distribution by Technology ($/kWh)", fontsize=12,
                 fontweight="bold", y=1.01)

    for ax, df, label in [(axes[0], van, "Baseline"), (axes[1], ext, "Extended")]:
        ax.set_facecolor("white")
        ax.set_title(label, fontsize=10, fontweight="600", pad=4)

        lcoe = pd.to_numeric(df[LCOE_COL], errors="coerce")
        for tech, col in TECH_COLOURS.items():
            mask = df["tech"] == tech
            vals = lcoe[mask].dropna().clip(0, 1.6)
            if len(vals) < 3:
                continue
            n_bins = min(50, max(10, len(vals) // 40))
            ax.hist(vals, bins=n_bins, color=col, alpha=0.55,
                    label=tech.replace("_", "-"), edgecolor="none", density=True)
            med = vals.median()
            ymax = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 5
            ax.axvline(med, color=col, linewidth=2, linestyle="--", alpha=0.9, zorder=4)
            ax.text(med + 0.015, ymax * 0.05,
                    f"${med:.2f}", fontsize=7, color=col,
                    rotation=90, va="bottom", fontweight="600")

        ax.set_xlabel("LCOE ($/kWh)", fontsize=9, labelpad=4)
        ax.set_ylabel("Density", fontsize=9, labelpad=4)
        ax.legend(fontsize=8.5, framealpha=0.9, edgecolor="#ddd", borderpad=0.6)
        ax.grid(axis="y", color="#ececec", linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#ddd")
        ax.tick_params(labelsize=8.5, color="#ccc")

    fig.tight_layout(pad=1.2)
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved {Path(save_path).name}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading results...")
    van, ext, comp = load_data()
    admin = load_admin()
    print(f"  Vanilla: {len(van):,} | Extended: {len(ext):,}")

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving figures to {FIGURES_DIR}\n")

    tech_legend = [
        mpatches.Patch(color=c, label=t.replace("_", "-"))
        for t, c in TECH_COLOURS.items()
    ]
    pop_legend  = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#666",
               markersize=s, label=lbl)
        for s, lbl in [(2, "Pop ~100"), (4, "Pop ~1,000"), (7, "Pop ~5,000+")]
    ]

    print("Fig 1 — baseline map")
    make_map_fig(van,
                 "Baseline Least-Cost Technology Map",
                 "OnSSET baseline · MTF Tier 2/3 demand · 2026–2041 planning horizon",
                 tech_legend + pop_legend, admin,
                 FIGURES_DIR / "fig1_vanilla_tech_map.png")

    print("Fig 2 — extended map")
    make_map_fig(ext,
                 "Extended Least-Cost Technology Map",
                 "Wealth-disaggregated (RWI) · site-specific GHI · HV distances · POI loads · 2026–2041",
                 tech_legend + pop_legend, admin,
                 FIGURES_DIR / "fig2_extended_tech_map.png")

    print("Fig 3 — change map")
    changed_mask = comp["tech_changed"].values.astype(bool)
    change_legend = [
        mpatches.Patch(color=CHANGE_COL, label=f"Changed ({changed_mask.sum():,})"),
        mpatches.Patch(color=UNCH_COL, alpha=0.5, label=f"Unchanged ({(~changed_mask).sum():,})"),
    ]
    make_map_fig(van,
                 "Technology Change Map: Baseline → Extended",
                 "Red = settlement reclassified by extended model · 6,365 of 17,175 settlements",
                 change_legend, admin,
                 FIGURES_DIR / "fig3_delta_map.png",
                 changed_mask=changed_mask)

    print("Fig 4 — tech mix bar")
    make_tech_mix_bar(van, ext, FIGURES_DIR / "fig4_tech_mix_bar.png")

    print("Fig 5 — LCOE histograms")
    make_lcoe_hist(van, ext, FIGURES_DIR / "fig5_lcoe_histograms.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
