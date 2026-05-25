"""Build two PowerPoint decks from the analysis outputs.

Deliverables:
  deliverables/technical_deck.pptx   — 12 slides for a technical audience
  deliverables/policy_deck.pptx      — 8 slides for a policy/non-technical audience
"""
import io
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from src.config import (
    FIGURES_DIR, COMPARISON_CSV, VANILLA_RESULTS_CSV, EXTENDED_RESULTS_CSV,
    DELIVERABLES_DIR, END_YEAR, START_YEAR,
)

# ---- colour palette ----
BLUE   = RGBColor(0x21, 0x66, 0xac)
ORANGE = RGBColor(0xf4, 0xa5, 0x82)
GREEN  = RGBColor(0x1b, 0x7a, 0x3e)
WHITE  = RGBColor(0xff, 0xff, 0xff)
DARK   = RGBColor(0x1a, 0x1a, 0x2e)
GREY   = RGBColor(0x55, 0x55, 0x55)

W = Inches(13.33)   # widescreen 16:9
H = Inches(7.5)


def _prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H
    return prs


def _blank(prs: Presentation):
    blank_layout = prs.slide_layouts[6]   # completely blank
    return prs.slides.add_slide(blank_layout)


def _bg(slide, colour: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = colour


def _textbox(slide, text, left, top, width, height,
             fontsize=18, bold=False, colour=WHITE, align=PP_ALIGN.LEFT,
             wrap=True):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(fontsize)
    run.font.bold = bold
    run.font.color.rgb = colour
    return txBox


def _img(slide, path, left, top, width=None, height=None):
    if not Path(path).exists():
        return
    if width and height:
        slide.shapes.add_picture(str(path), left, top, width, height)
    elif width:
        slide.shapes.add_picture(str(path), left, top, width=width)
    elif height:
        slide.shapes.add_picture(str(path), left, top, height=height)
    else:
        slide.shapes.add_picture(str(path), left, top)


# ---------- helper: summary stats ----------
def _load_stats():
    delta  = pd.read_csv(COMPARISON_CSV)
    van    = pd.read_csv(VANILLA_RESULTS_CSV,  low_memory=False)
    ext    = pd.read_csv(EXTENDED_RESULTS_CSV, low_memory=False)

    tech_col = f"MinimumOverall{END_YEAR}"
    inv_col  = f"InvestmentCost{END_YEAR}"

    van_mix = delta["tech_vanilla"].value_counts().to_dict()
    ext_mix = delta["tech_extended"].value_counts().to_dict()
    n_changed = int(delta["tech_changed"].sum())
    pct_changed = 100 * n_changed / len(delta)

    inv_van = van[inv_col].sum() / 1e6 if inv_col in van.columns else 0
    inv_ext = ext[inv_col].sum() / 1e6 if inv_col in ext.columns else 0

    return {
        "n_settlements": len(delta),
        "van_mix":       van_mix,
        "ext_mix":       ext_mix,
        "n_changed":     n_changed,
        "pct_changed":   pct_changed,
        "inv_van_m":     inv_van,
        "inv_ext_m":     inv_ext,
        "inv_delta_m":   inv_ext - inv_van,
    }


# ============================================================
#  TECHNICAL DECK
# ============================================================

def _tech_title_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, DARK)
    _textbox(sl, "Least-Cost Electrification Modelling in Benin",
             Inches(1), Inches(1.8), Inches(11.3), Inches(1.5),
             fontsize=36, bold=True, colour=WHITE, align=PP_ALIGN.CENTER)
    _textbox(sl, f"OnSSET Vanilla vs Extended Model Comparison  |  {START_YEAR}-{END_YEAR}",
             Inches(1), Inches(3.5), Inches(11.3), Inches(0.8),
             fontsize=18, colour=ORANGE, align=PP_ALIGN.CENTER)
    _textbox(sl, "Technical Analysis Deck",
             Inches(1), Inches(4.4), Inches(11.3), Inches(0.6),
             fontsize=14, colour=GREY, align=PP_ALIGN.CENTER)


def _tech_methodology_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Methodology Overview", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
             fontsize=26, bold=True, colour=DARK)
    bullets = [
        "OnSSET 1.1a6 — Open Source Spatial Electrification Tool (KTH)",
        "17,175 settlements across Benin from HRSL + GHS-SMOD datasets",
        "Planning horizon: 2026-2041  |  Two time steps: 2033 and 2041",
        "Vanilla baseline: country-level MTF Tier 2 rural / Tier 3 urban demand",
        "Extended model adds 4 extensions to improve demand accuracy and cost estimation:",
        "  1. Wealth-disaggregated demand — Meta Relative Wealth Index (RWI) quartile tier shifts",
        "  2. Site-specific GHI — Global Solar Atlas 1km raster sampled per settlement",
        "  3. Refined grid distance — MV substation proximity instead of transmission lines",
        "  4. POI-driven productive uplift — OSM-derived anchor loads + institutional demand",
    ]
    top = Inches(1.2)
    for b in bullets:
        indent = b.startswith("  ")
        _textbox(sl, b.strip(), Inches(0.8 if not indent else 1.3), top,
                 Inches(11.5), Inches(0.35),
                 fontsize=13 if not indent else 11, colour=DARK if not indent else GREY)
        top += Inches(0.38 if not indent else 0.33)


def _tech_data_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Input Data Sources", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
             fontsize=26, bold=True, colour=DARK)
    rows = [
        ("Dataset",              "Source",                "Resolution"),
        ("Settlement locations", "HRSL / GHS-SMOD",       "~100 m"),
        ("Population",           "WorldPop 2030 (CN)",    "100 m"),
        ("Solar resource (GHI)", "Global Solar Atlas",    "1 km"),
        ("Grid distances",       "MV substation OSM/SHP", "Vector"),
        ("Wealth index",         "Meta RWI (2016-2023)",  "2.4 km"),
        ("POIs / facilities",    "OpenStreetMap Overpass","Vector"),
        ("Admin boundaries",     "GADM 4.1",              "Level 1+2"),
        ("National calibration", "WB Tracking SDG7 2023", "National"),
    ]
    top = Inches(1.2)
    col_w = [Inches(4), Inches(5.5), Inches(2.5)]
    for i, row in enumerate(rows):
        for j, (cell, w) in enumerate(zip(row, col_w)):
            left = Inches(0.5) + sum(col_w[:j])
            _textbox(sl, cell, left, top, w, Inches(0.4),
                     fontsize=12 if i > 0 else 13,
                     bold=(i == 0),
                     colour=DARK if i > 0 else BLUE)
        top += Inches(0.42)


def _tech_vanilla_map_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, f"Vanilla OnSSET — Technology Assignment ({END_YEAR})",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig1_vanilla_tech_map.png",
         Inches(1.5), Inches(0.9), height=Inches(6.3))
    _textbox(sl, f"Grid: {681:,}  |  MG-PV: {16001:,}  |  SA-PV: {493:,}",
             Inches(0.4), Inches(7.05), Inches(12), Inches(0.35), fontsize=11, colour=GREY)


def _tech_extended_map_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, f"Extended OnSSET — Technology Assignment ({END_YEAR})",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig2_extended_tech_map.png",
         Inches(1.5), Inches(0.9), height=Inches(6.3))
    ext = st["ext_mix"]
    summary = "  |  ".join(f"{k}: {v:,}" for k, v in sorted(ext.items()))
    _textbox(sl, summary, Inches(0.4), Inches(7.05), Inches(12), Inches(0.35), fontsize=11, colour=GREY)


def _tech_delta_map_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Technology Changes — Vanilla vs Extended",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig3_delta_map.png",
         Inches(1.5), Inches(0.9), height=Inches(6.3))
    _textbox(sl, f"{st['n_changed']:,} settlements changed technology ({st['pct_changed']:.1f}%)",
             Inches(0.4), Inches(7.05), Inches(12), Inches(0.35), fontsize=11, colour=GREY)


def _tech_mix_bar_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Technology Mix: Vanilla vs Extended",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig4_tech_mix_bar.png",
         Inches(0.8), Inches(0.9), width=Inches(11.5))


def _tech_lcoe_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "LCOE Distribution by Technology",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig5_lcoe_histograms.png",
         Inches(0.4), Inches(0.9), width=Inches(12.5))


def _tech_investment_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Investment Requirements",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)

    rows = [
        ("Metric",                      "Vanilla",                             "Extended"),
        ("Total investment (USD)",      f"${st['inv_van_m']:,.0f}M",          f"${st['inv_ext_m']:,.0f}M"),
        ("Investment delta",            "—",                                   f"${st['inv_delta_m']:+,.0f}M"),
        ("Settlements served",          f"{st['n_settlements']:,}",            f"{st['n_settlements']:,}"),
        ("Technology changed",          "—",                                   f"{st['n_changed']:,} ({st['pct_changed']:.1f}%)"),
    ]
    top = Inches(1.2)
    col_w = [Inches(4.5), Inches(3.5), Inches(3.5)]
    for i, row in enumerate(rows):
        for j, (cell, w) in enumerate(zip(row, col_w)):
            left = Inches(0.5) + sum(col_w[:j])
            _textbox(sl, cell, left, top, w, Inches(0.5),
                     fontsize=13 if i > 0 else 14,
                     bold=(i == 0),
                     colour=DARK if i > 0 else BLUE)
        top += Inches(0.55)

    _textbox(sl, "Note: Extended investment is higher due to wealth-adjusted demand uplift for "
                 "richest-quartile settlements (Extension 1) and POI-driven anchor/institutional loads (Extension 4).",
             Inches(0.5), Inches(5.8), Inches(12), Inches(1.0), fontsize=11, colour=GREY)


def _tech_extensions_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Extension Impact Summary",
             Inches(0.4), Inches(0.2), Inches(12), Inches(0.6), fontsize=22, bold=True, colour=DARK)
    exts = [
        ("Ext 1 — Wealth-disaggregated demand",
         "RWI Q1 (poorest 25%) demand shifted -1 MTF tier; Q4 (richest 25%) +1 tier. "
         "Result: 2,510 MG-PV -> SA-PV transitions as poorest settlements no longer "
         "justify mini-grid infrastructure cost."),
        ("Ext 2 — Site-specific GHI",
         "Global Solar Atlas 1km raster sampled per settlement. GHI range: 1,678-2,116 "
         "kWh/m2/yr across Benin. Affects MG-PV and SA-PV LCOE calculations."),
        ("Ext 3 — Refined grid distance (substations)",
         "MV substation proximity used as grid extension cost driver instead of 161kV "
         "transmission lines. More accurate for MV-level grid rollout planning."),
        ("Ext 4 — POI-driven productive uplift",
         "OSM-derived productive multiplier replaces flat 20% uplift. Health facilities "
         "+25,000 kWh/yr; education +4,500 kWh/yr; anchor loads (telecom+water) added. "
         "Mean energy demand +291,011 kWh/settlement/yr."),
    ]
    top = Inches(1.2)
    for title, body in exts:
        _textbox(sl, title, Inches(0.5), top, Inches(12), Inches(0.4),
                 fontsize=13, bold=True, colour=BLUE)
        top += Inches(0.38)
        _textbox(sl, body, Inches(0.8), top, Inches(12), Inches(0.55),
                 fontsize=11, colour=DARK)
        top += Inches(0.65)


def _tech_conclusions_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, DARK)
    _textbox(sl, "Key Findings", Inches(0.5), Inches(0.4), Inches(12), Inches(0.7),
             fontsize=28, bold=True, colour=WHITE)
    findings = [
        f"Off-grid solar (MG-PV + SA-PV) dominates: >96% of {st['n_settlements']:,} settlements in both scenarios",
        f"Grid extension reaches {st['van_mix'].get('Grid', 0):,} settlements (vanilla) vs "
        f"{st['ext_mix'].get('Grid', 0):,} (extended) — grid viable only near substations",
        f"Wealth disaggregation shifts {2510:,} settlements MG-PV -> SA-PV (demand too low for mini-grid CAPEX)",
        f"Extended investment {st['inv_ext_m']:,.0f}M USD vs vanilla {st['inv_van_m']:,.0f}M USD "
        f"({st['inv_delta_m']:+,.0f}M delta driven by demand uplift)",
        "POI-driven anchor loads add meaningful baseload in settlements near telecom towers and water pumps",
        "GHI variation (1,678-2,116 kWh/m2/yr) is modest — MG-PV viability driven more by demand and grid distance",
    ]
    top = Inches(1.4)
    for f in findings:
        _textbox(sl, f"• {f}", Inches(0.7), top, Inches(12), Inches(0.5),
                 fontsize=13, colour=WHITE)
        top += Inches(0.6)


def build_technical_deck(st):
    prs = _prs()
    _tech_title_slide(prs, st)
    _tech_methodology_slide(prs)
    _tech_data_slide(prs)
    _tech_vanilla_map_slide(prs)
    _tech_extended_map_slide(prs, st)
    _tech_delta_map_slide(prs, st)
    _tech_mix_bar_slide(prs)
    _tech_lcoe_slide(prs)
    _tech_investment_slide(prs, st)
    _tech_extensions_slide(prs)
    _tech_conclusions_slide(prs, st)

    DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = DELIVERABLES_DIR / "technical_deck.pptx"
    prs.save(str(path))
    print(f"  Saved {path}")


# ============================================================
#  POLICY DECK (non-technical audience)
# ============================================================

def _policy_title_slide(prs):
    sl = _blank(prs)
    _bg(sl, GREEN)
    _textbox(sl, "Powering Benin:", Inches(1), Inches(1.5), Inches(11), Inches(1.0),
             fontsize=40, bold=True, colour=WHITE, align=PP_ALIGN.CENTER)
    _textbox(sl, "Least-Cost Pathways to Universal Electricity Access",
             Inches(1), Inches(2.7), Inches(11), Inches(0.9),
             fontsize=24, colour=WHITE, align=PP_ALIGN.CENTER)
    _textbox(sl, f"{START_YEAR} – {END_YEAR}  |  Benin Energy Planning Study",
             Inches(1), Inches(3.8), Inches(11), Inches(0.6),
             fontsize=14, colour=RGBColor(0xb2, 0xdf, 0xb2), align=PP_ALIGN.CENTER)


def _policy_challenge_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "The Challenge", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
             fontsize=28, bold=True, colour=GREEN)
    points = [
        ("13.7 million people",      "Benin's current population — growing to 17.5M by 2041"),
        ("42% electrification rate", "Leaving 8 million people without reliable electricity"),
        ("17,175 settlements",       "Mapped across 12 departments, many in remote rural areas"),
        ("2 key questions:",         "Which technology serves each settlement at lowest cost?"),
        ("",                         "How much investment is needed, and where?"),
    ]
    top = Inches(1.3)
    for label, desc in points:
        if label:
            _textbox(sl, label, Inches(0.5), top, Inches(4.2), Inches(0.5),
                     fontsize=16, bold=True, colour=GREEN)
        _textbox(sl, desc, Inches(4.7 if label else 1.0), top, Inches(8.0), Inches(0.5),
                 fontsize=14, colour=DARK)
        top += Inches(0.65)


def _policy_approach_slide(prs):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "My Approach", Inches(0.5), Inches(0.3), Inches(12), Inches(0.7),
             fontsize=28, bold=True, colour=GREEN)
    _textbox(sl, "I used OnSSET — a globally-recognised electrification planning model — "
                 "enhanced with Benin-specific data to compare three technology options for each settlement:",
             Inches(0.5), Inches(1.2), Inches(12.3), Inches(0.8), fontsize=13, colour=DARK)

    techs = [
        ("National Grid Extension", "Extending MV lines from the nearest substation",
         "#2166ac", Inches(0.5)),
        ("Mini-Grid Solar (MG-PV)", "Community-scale solar + battery systems",
         "#f4a582", Inches(4.6)),
        ("Solar Home Systems (SHS)", "Household solar kits for dispersed settlements",
         "#fdae61", Inches(8.7)),
    ]
    for title, desc, col_hex, left in techs:
        box = sl.shapes.add_shape(1, left, Inches(2.3), Inches(3.8), Inches(3.5))
        box.fill.solid()
        r, g, b = int(col_hex[1:3], 16), int(col_hex[3:5], 16), int(col_hex[5:7], 16)
        box.fill.fore_color.rgb = RGBColor(r, g, b)
        box.line.fill.background()
        _textbox(sl, title, left + Inches(0.1), Inches(2.4), Inches(3.6), Inches(0.6),
                 fontsize=13, bold=True, colour=WHITE)
        _textbox(sl, desc,  left + Inches(0.1), Inches(3.1), Inches(3.6), Inches(2.5),
                 fontsize=12, colour=WHITE)

    _textbox(sl, "The model selects the lowest-cost option for each settlement based on population, "
                 "distance to the grid, solar resource, and local wealth levels.",
             Inches(0.5), Inches(6.1), Inches(12.3), Inches(1.0), fontsize=13, colour=GREY)


def _policy_vanilla_results_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, f"Baseline Results ({END_YEAR})", Inches(0.5), Inches(0.2), Inches(7), Inches(0.7),
             fontsize=26, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig1_vanilla_tech_map.png",
         Inches(7.2), Inches(0.2), height=Inches(7.0))

    stats = [
        ("Solar Mini-Grids",    f"{st['van_mix'].get('MG_PV', 0):,} settlements",  "#f4a582"),
        ("Grid Extension",      f"{st['van_mix'].get('Grid',  0):,} settlements",   "#2166ac"),
        ("Solar Home Systems",  f"{st['van_mix'].get('SA_PV', 0):,} settlements",   "#fdae61"),
    ]
    top = Inches(1.8)
    for label, count, col_hex in stats:
        r, g, b = int(col_hex[1:3], 16), int(col_hex[3:5], 16), int(col_hex[5:7], 16)
        _textbox(sl, label, Inches(0.5), top, Inches(6.5), Inches(0.4),
                 fontsize=14, bold=True, colour=RGBColor(r, g, b))
        _textbox(sl, count, Inches(0.5), top + Inches(0.38), Inches(6.5), Inches(0.4),
                 fontsize=22, bold=True, colour=DARK)
        top += Inches(1.0)

    _textbox(sl, f"Total investment required:  ${st['inv_van_m']:,.0f} million USD",
             Inches(0.5), Inches(5.2), Inches(6.5), Inches(0.6), fontsize=13, colour=GREY)


def _policy_extended_results_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, f"With Wealth & POI Data ({END_YEAR})", Inches(0.5), Inches(0.2), Inches(7), Inches(0.7),
             fontsize=26, bold=True, colour=DARK)
    _img(sl, FIGURES_DIR / "fig2_extended_tech_map.png",
         Inches(7.2), Inches(0.2), height=Inches(7.0))

    stats = [
        ("Solar Mini-Grids",   f"{st['ext_mix'].get('MG_PV', 0):,} settlements", "#f4a582"),
        ("Solar Home Systems", f"{st['ext_mix'].get('SA_PV', 0):,} settlements",  "#fdae61"),
        ("Grid Extension",     f"{st['ext_mix'].get('Grid',  0):,} settlements",  "#2166ac"),
    ]
    top = Inches(1.8)
    for label, count, col_hex in stats:
        r, g, b = int(col_hex[1:3], 16), int(col_hex[3:5], 16), int(col_hex[5:7], 16)
        _textbox(sl, label, Inches(0.5), top, Inches(6.5), Inches(0.4),
                 fontsize=14, bold=True, colour=RGBColor(r, g, b))
        _textbox(sl, count, Inches(0.5), top + Inches(0.38), Inches(6.5), Inches(0.4),
                 fontsize=22, bold=True, colour=DARK)
        top += Inches(1.0)

    _textbox(sl, f"Total investment required:  ${st['inv_ext_m']:,.0f} million USD",
             Inches(0.5), Inches(5.2), Inches(6.5), Inches(0.6), fontsize=13, colour=GREY)


def _policy_key_differences_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "What Changes With Wealth-Adjusted Data?",
             Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.7), fontsize=24, bold=True, colour=DARK)

    rows = [
        ("Finding",                          "Implication for Planning"),
        (f"{st['n_changed']:,} settlements ({st['pct_changed']:.0f}%) change technology",
         "Local wealth levels significantly affect the most cost-effective solution"),
        (f"{2510:,} settlements move from mini-grids to solar home systems",
         "Poorest communities are better served by affordable household kits than community grids"),
        (f"Wealthier settlements justify larger solar systems",
         "Richer areas have higher electricity demand — mini-grids remain the right solution"),
        ("Institutional facilities add significant demand",
         "Health clinics and schools need reliable power — this changes system sizing"),
    ]
    top = Inches(1.3)
    col_w = [Inches(6.5), Inches(6.0)]
    for i, row in enumerate(rows):
        for j, (cell, w) in enumerate(zip(row, col_w)):
            left = Inches(0.5) + sum(col_w[:j])
            _textbox(sl, cell, left, top, w, Inches(0.6),
                     fontsize=13 if i > 0 else 14,
                     bold=(i == 0),
                     colour=DARK if i > 0 else GREEN)
        top += Inches(0.75)


def _policy_investment_slide(prs, st):
    sl = _blank(prs)
    _bg(sl, WHITE)
    _textbox(sl, "Investment Needed for Universal Access",
             Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.7), fontsize=24, bold=True, colour=DARK)

    _textbox(sl, f"${st['inv_van_m']:,.0f}M",
             Inches(1), Inches(1.5), Inches(5), Inches(1.2), fontsize=48, bold=True, colour=BLUE)
    _textbox(sl, "Vanilla baseline estimate", Inches(1), Inches(2.8), Inches(5), Inches(0.5),
             fontsize=14, colour=GREY)

    _textbox(sl, f"${st['inv_ext_m']:,.0f}M",
             Inches(7), Inches(1.5), Inches(5), Inches(1.2), fontsize=48, bold=True, colour=GREEN)
    _textbox(sl, "With wealth & POI data", Inches(7), Inches(2.8), Inches(5), Inches(0.5),
             fontsize=14, colour=GREY)

    _textbox(sl, "The higher estimate reflects more accurate demand modelling: wealthier communities "
                 "require larger systems, and health/education facilities need reliable anchor power. "
                 "The vanilla estimate undercounts true infrastructure needs.",
             Inches(0.5), Inches(4.2), Inches(12.3), Inches(1.5), fontsize=13, colour=DARK)

    _textbox(sl, "Both scenarios show off-grid solar is the least-cost solution for over 95% of Benin's settlements.",
             Inches(0.5), Inches(5.9), Inches(12.3), Inches(0.8), fontsize=14, bold=True, colour=GREEN)


def _policy_recommendations_slide(prs):
    sl = _blank(prs)
    _bg(sl, GREEN)
    _textbox(sl, "Recommendations", Inches(0.5), Inches(0.4), Inches(12), Inches(0.7),
             fontsize=28, bold=True, colour=WHITE)
    recs = [
        ("1. Prioritise off-grid solar",
         "Mini-grids and solar home systems are the lowest-cost path for most of Benin. "
         "Concentrate grid investment near existing substations."),
        ("2. Target wealth-stratified programmes",
         "Poorest-quartile settlements need affordable SHS/PAYG models. "
         "Wealthiest quartile settlements can support productive-use mini-grids."),
        ("3. Anchor institutions in mini-grid planning",
         "Health centres and schools provide baseload demand that improves mini-grid economics. "
         "Co-locate facilities with mini-grid service areas."),
        ("4. Invest in substation proximity data",
         "MV grid extension cost is highly sensitive to substation distance. "
         "Keeping substation GIS data updated will improve future planning decisions."),
    ]
    top = Inches(1.4)
    for title, body in recs:
        _textbox(sl, title, Inches(0.6), top, Inches(12), Inches(0.45),
                 fontsize=15, bold=True, colour=WHITE)
        _textbox(sl, body, Inches(0.6), top + Inches(0.42), Inches(12), Inches(0.55),
                 fontsize=12, colour=RGBColor(0xd4, 0xed, 0xda))
        top += Inches(1.2)


def build_policy_deck(st):
    prs = _prs()
    _policy_title_slide(prs)
    _policy_challenge_slide(prs)
    _policy_approach_slide(prs)
    _policy_vanilla_results_slide(prs, st)
    _policy_extended_results_slide(prs, st)
    _policy_key_differences_slide(prs, st)
    _policy_investment_slide(prs, st)
    _policy_recommendations_slide(prs)

    DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = DELIVERABLES_DIR / "policy_deck.pptx"
    prs.save(str(path))
    print(f"  Saved {path}")


def main():
    print("Loading stats...")
    st = _load_stats()
    print(f"  {st['n_settlements']:,} settlements  |  {st['n_changed']:,} changed")

    print("\nBuilding technical deck...")
    build_technical_deck(st)

    print("\nBuilding policy deck...")
    build_policy_deck(st)

    print("\nDone.")


if __name__ == "__main__":
    main()
