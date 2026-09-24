# -*- coding: utf-8 -*-
"""
main.py — India Air Quality Intelligence
=========================================
Reproducible analysis pipeline for the CPCB CAAQMS AQI dataset.

Source:  Government of India Open Government Data Platform (data.gov.in)
Dataset: CPCB Real-time Air Quality Index
UUID:    3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69

Pipeline stages
---------------
1.  Load raw data
2.  Data cleaning & feature engineering  → aqi_cleaned_long.csv, aqi_cleaned_wide.csv
3.  CPCB 2014 AQI sub-index computation  → aqi_subindex_results.csv + updates wide CSV
4.  EDA calculations                     → printed summary statistics
5.  Dashboard data generation            → dashboard_data.json

Dashboard (dashboard.html)
--------------------------
The interactive dashboard is a standalone HTML/JavaScript file.
It reads dashboard_data.json at runtime via fetch().
No Python is required to run the dashboard — serve it with a local HTTP server:

    python -m http.server 8000
    # then open: http://localhost:8000/dashboard.html

Methodology assumptions (documented, not independently verified)
-----------------------------------------------------------------
- Snapshot date: 23 September 2026, 12:00:00 IST (single point-in-time, not time-series)
- pollutant_avg averaging period: ASSUMED 24h for PM2.5/PM10/SO2/NO2/NH3;
  8h for CO/OZONE — consistent with CPCB 2014 AQI methodology.
  The CSV does not document the averaging period.
- CO is stored in µg/m³ in the CSV.  Divided by 1000 → mg/m³ before applying
  CPCB breakpoints (which use mg/m³).
- All computed AQI values are labelled "Calculated AQI" — NOT official CPCB-reported AQI.
- No rows are deleted.  Suspicious zeros (13) and sensor anomalies (3) are flagged.
- No missing-value imputation is performed.
- This is a cross-sectional snapshot.  No temporal trends or seasonal analysis
  are possible or attempted.

Usage
-----
    python main.py

Outputs (created/overwritten in the same directory as this script):
    aqi_cleaned_long.csv
    aqi_cleaned_wide.csv
    aqi_subindex_results.csv
    dashboard_data.json
"""

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from statistics import median, mean, stdev

# Ensure UTF-8 output on all platforms (including Windows with cp1252 terminal)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── File paths (relative) ──────────────────────────────────────────────────────
RAW_FILE        = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69.csv"
LONG_OUT        = "aqi_cleaned_long.csv"
WIDE_OUT        = "aqi_cleaned_wide.csv"
SUBINDEX_OUT    = "aqi_subindex_results.csv"
DASHBOARD_OUT   = "dashboard_data.json"

POLLUTANTS = ["PM2.5", "PM10", "SO2", "NO2", "CO", "NH3", "OZONE"]

# ── CPCB 2014 AQI Breakpoints ──────────────────────────────────────────────────
# Format: list of (C_lo, C_hi, I_lo, I_hi) per pollutant
# CO breakpoints are in mg/m³ (dataset CO values must be divided by 1000 first)
# Source: CPCB National Air Quality Index, 2014
BREAKPOINTS = {
    "PM2.5": [
        (0,   30,  0,   50),
        (30,  60,  51,  100),
        (60,  90,  101, 200),
        (90,  120, 201, 300),
        (120, 250, 301, 400),
        (250, 380, 401, 500),
    ],
    "PM10": [
        (0,   50,  0,   50),
        (50,  100, 51,  100),
        (100, 250, 101, 200),
        (250, 350, 201, 300),
        (350, 430, 301, 400),
        (430, 600, 401, 500),
    ],
    "SO2": [
        (0,   40,  0,   50),
        (40,  80,  51,  100),
        (80,  380, 101, 200),
        (380, 800, 201, 300),
        (800, 1600,301, 400),
        (1600,2100,401, 500),
    ],
    "NO2": [
        (0,   40,  0,   50),
        (40,  80,  51,  100),
        (80,  180, 101, 200),
        (180, 280, 201, 300),
        (280, 400, 301, 400),
        (400, 800, 401, 500),
    ],
    "CO": [   # units: mg/m³  (dataset values ÷ 1000)
        (0,   1,   0,   50),
        (1,   2,   51,  100),
        (2,   10,  101, 200),
        (10,  17,  201, 300),
        (17,  34,  301, 400),
        (34,  46,  401, 500),
    ],
    "NH3": [
        (0,   200, 0,   50),
        (200, 400, 51,  100),
        (400, 800, 101, 200),
        (800, 1200,201, 300),
        (1200,1800,301, 400),
        (1800,2400,401, 500),
    ],
    "OZONE": [
        (0,   50,  0,   50),
        (50,  100, 51,  100),
        (100, 168, 101, 200),
        (168, 208, 201, 300),
        (208, 748, 301, 400),
        (748, 1000,401, 500),
    ],
}

AQI_LABELS = [
    (0,   50,  "Good"),
    (51,  100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def safe_float(v):
    """Return float or None for blank / 'NA' / non-numeric strings."""
    if v in ("", "None", "NA", "nan", None):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sub_index(pollutant, concentration):
    """
    Compute CPCB 2014 piecewise-linear AQI sub-index for a single pollutant.
    concentration must be in the correct unit:
      - CO: mg/m³  (caller must divide µg/m³ by 1000)
      - all others: µg/m³
    Returns float sub-index or None if concentration is None or out of range.
    """
    if concentration is None or concentration < 0:
        return None
    bps = BREAKPOINTS.get(pollutant)
    if not bps:
        return None
    for c_lo, c_hi, i_lo, i_hi in bps:
        if c_lo <= concentration <= c_hi:
            if c_hi == c_lo:
                return float(i_lo)
            si = i_lo + (concentration - c_lo) * (i_hi - i_lo) / (c_hi - c_lo)
            return round(si, 2)
    # Above highest breakpoint — cap at 500
    if concentration > bps[-1][1]:
        return 500.0
    return None


def aqi_label(aqi):
    """Return CPCB AQI category label for a Calculated AQI value."""
    if aqi is None:
        return ""
    for lo, hi, lbl in AQI_LABELS:
        if lo <= aqi <= hi:
            return lbl
    return "Severe" if aqi > 400 else ""


def shannon_entropy(si_values):
    """Shannon entropy of a pollutant sub-index profile (diversity measure)."""
    vals = [v for v in si_values if v and v > 0]
    if len(vals) < 2:
        return None
    s = sum(vals)
    if s == 0:
        return None
    ps = [v / s for v in vals]
    return round(-sum(p * math.log(p) for p in ps if p > 0), 4)


def percentile(sorted_vals, pct):
    """Return the p-th percentile of a sorted list."""
    if not sorted_vals:
        return None
    idx = int(pct * len(sorted_vals))
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — LOAD RAW DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_raw(path):
    print(f"\n{'='*70}")
    print("STAGE 1 — LOAD RAW DATA")
    print(f"{'='*70}")
    if not os.path.exists(path):
        sys.exit(f"ERROR: Raw file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"  Loaded {len(rows)} rows × {len(rows[0])} columns")
    print(f"  Columns: {list(rows[0].keys())}")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — CLEANING & FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def clean_and_engineer(raw_rows):
    """
    Applies the documented cleaning steps and returns (long_rows, wide_rows).
    No rows are deleted.  All transformations are additive (new columns).
    """
    print(f"\n{'='*70}")
    print("STAGE 2 — DATA CLEANING & FEATURE ENGINEERING")
    print(f"{'='*70}")

    # ── 2a: Parse numeric columns ────────────────────────────────────────────
    rows = [dict(r) for r in raw_rows]   # working copy — raw_rows untouched
    for r in rows:
        r["pollutant_min_num"]  = safe_float(r.get("pollutant_min"))
        r["pollutant_max_num"]  = safe_float(r.get("pollutant_max"))
        r["pollutant_avg_num"]  = safe_float(r.get("pollutant_avg"))
        r["latitude_num"]       = safe_float(r.get("latitude"))
        r["longitude_num"]      = safe_float(r.get("longitude"))

    na_count = sum(1 for r in rows if r["pollutant_avg_num"] is None)
    print(f"  NA pollutant_avg readings: {na_count} of {len(rows)} ({100*na_count/len(rows):.1f}%)")

    # ── 2b: Snapshot metadata ────────────────────────────────────────────────
    # Dataset is a single point-in-time snapshot — NOT a time series.
    for r in rows:
        lu = r.get("last_update", "")
        if lu:
            parts = lu.split(" ")
            r["snapshot_date"]  = parts[0] if parts else ""
            r["snapshot_time"]  = parts[1] if len(parts) > 1 else ""
            r["snapshot_label"] = "SINGLE_SNAPSHOT_NOT_TIME_SERIES"
        else:
            r["snapshot_date"] = r["snapshot_time"] = r["snapshot_label"] = ""

    # ── 2c: CO unit conversion ───────────────────────────────────────────────
    # CO in CSV is µg/m³.  CPCB AQI breakpoints use mg/m³ → divide by 1000.
    # This interpretation is confirmed by physical plausibility:
    # mg/m³ interpretation would place all stations in Severe (physically impossible).
    for r in rows:
        if r.get("pollutant_id", "").strip() == "CO":
            r["CO_ug_m3"] = r["pollutant_avg_num"]
            r["CO_mg_m3"] = r["pollutant_avg_num"] / 1000 if r["pollutant_avg_num"] is not None else None
        else:
            r["CO_ug_m3"] = None
            r["CO_mg_m3"] = None

    # ── 2d: Suspicious zero flags ────────────────────────────────────────────
    # Zero readings for NH3 or SO2 where the same station is actively reporting
    # other non-null pollutants.  A zero at a station that reports nothing else
    # is NOT flagged (may be genuine non-detection or inactive sensor).
    # Retained, not deleted; flagged for validation.
    # First pass: per-station valid-pollutant count from long data
    station_valid_pols = defaultdict(set)
    for r in rows:
        if r["pollutant_avg_num"] is not None and r["pollutant_avg_num"] != 0.0:
            station_valid_pols[r["station"].strip()].add(r.get("pollutant_id","").strip())

    for r in rows:
        pid = r.get("pollutant_id", "").strip()
        val = r["pollutant_avg_num"]
        stn = r["station"].strip()
        # Suspicious: zero NH3 or SO2 at station that has all 6 other pollutants reporting
        # (threshold = 6 matches the original cleaning logic — station fully operational
        # but NH3 or SO2 reads exactly 0)
        r["is_zero_sentinel"] = (
            val == 0.0
            and pid in ("NH3", "SO2")
            and len(station_valid_pols[stn]) >= 6
        )

    n_zero = sum(1 for r in rows if r["is_zero_sentinel"])
    zero_stns = set(r["station"].strip() for r in rows if r["is_zero_sentinel"])
    print(f"  Suspicious zero sentinel rows: {n_zero} across {len(zero_stns)} stations")
    print(f"  (NH3/SO2 = 0 at fully-reporting stations (>=6 other pollutants valid) — retained, flagged)")

    # ── 2e: NA flags ─────────────────────────────────────────────────────────
    for r in rows:
        r["is_na_reading"] = r["pollutant_avg_num"] is None

    # ── 2f: Whitespace standardisation ──────────────────────────────────────
    for r in rows:
        r["station"] = r.get("station", "").strip()

    # ── 2g: Board acronym extraction ─────────────────────────────────────────
    for r in rows:
        stn = r.get("station", "")
        if " - " in stn:
            r["board_acronym"] = stn.rsplit(" - ", 1)[-1].strip()
        else:
            r["board_acronym"] = None

    # ── 2h: Station-level NA counts ──────────────────────────────────────────
    station_na = defaultdict(int)
    station_valid = defaultdict(int)
    for r in rows:
        stn = r["station"]
        if r["is_na_reading"]:
            station_na[stn] += 1
        else:
            station_valid[stn] += 1

    for r in rows:
        stn = r["station"]
        total = station_na[stn] + station_valid[stn]
        r["station_na_count"]            = station_na[stn]
        r["station_valid_pollutant_count"] = station_valid[stn]
        r["station_completeness_pct"]    = round(100 * station_valid[stn] / total, 1) if total else 0

    print(f"  Station-level NA counts computed for {len(set(r['station'] for r in rows))} stations")

    # ── 2i: Build wide (station-level) dataframe ─────────────────────────────
    stations_seen = {}  # station -> first row metadata
    station_pols  = defaultdict(dict)  # station -> {pollutant -> avg_value}
    for r in rows:
        stn = r["station"]
        pid = r.get("pollutant_id", "").strip()
        if stn not in stations_seen:
            stations_seen[stn] = r
        # Use CO_mg_m3 for AQI (but store original µg/m³ value in wide file)
        val = r["pollutant_avg_num"]
        station_pols[stn][pid] = val

    wide_rows = []
    for stn, meta in stations_seen.items():
        vals = station_pols[stn]
        valid_count = sum(1 for p in POLLUTANTS if vals.get(p) is not None)
        missing_count = len(POLLUTANTS) - valid_count
        completeness = round(100 * valid_count / len(POLLUTANTS), 1)

        non_null_vals = [vals[p] for p in POLLUTANTS if vals.get(p) is not None]
        total_conc    = round(sum(non_null_vals), 2)          if non_null_vals else None
        mean_conc     = round(sum(non_null_vals)/len(non_null_vals), 2) if non_null_vals else None
        sorted_vals   = sorted(non_null_vals)
        median_conc   = sorted_vals[len(sorted_vals)//2]      if non_null_vals else None
        range_conc    = round(max(non_null_vals) - min(non_null_vals), 2) if non_null_vals else None
        highest_pol   = max(POLLUTANTS, key=lambda p: vals.get(p) or -1) if non_null_vals else None
        highest_val   = vals.get(highest_pol) if highest_pol else None

        # Z-scores (computed later per-pollutant across all stations)
        wr = {
            "station":           stn,
            "city":              meta.get("city", ""),
            "state":             meta.get("state", ""),
            "latitude":          meta.get("latitude", ""),
            "longitude":         meta.get("longitude", ""),
            "board_acronym":     meta.get("board_acronym", ""),
            "snapshot_date":     meta.get("snapshot_date", ""),
            "snapshot_label":    meta.get("snapshot_label", ""),
        }
        for p in POLLUTANTS:
            wr[p] = vals.get(p)

        wr.update({
            "valid_pollutant_count":             valid_count,
            "missing_pollutant_count":           missing_count,
            "completeness_pct":                  completeness,
            "total_pollutant_conc":              total_conc,
            "mean_pollutant_conc":               mean_conc,
            "median_pollutant_conc":             median_conc,
            "pollutant_conc_range":              range_conc,
            "highest_raw_concentration_pollutant": highest_pol,
            "highest_raw_concentration_value":   highest_val,
            "dominant_pollutant_by_AQI":         "PENDING",
            "high_missingness_flag":             missing_count >= 3,
            "suspicious_zero_flag":              stn in zero_stns,
            "incomplete_station_flag":           missing_count > 0,
            "coordinate_issue_flag":             False,
            "duplicate_coordinate_flag":         False,
        })
        wide_rows.append(wr)

    # Per-pollutant z-scores
    for p in POLLUTANTS:
        pvals = [wr[p] for wr in wide_rows if wr[p] is not None]
        if len(pvals) > 1:
            m  = sum(pvals) / len(pvals)
            sd = math.sqrt(sum((v - m) ** 2 for v in pvals) / len(pvals))
        else:
            m, sd = 0, 1
        for wr in wide_rows:
            v = wr[p]
            wr[f"{p}_zscore"] = round((v - m) / sd, 4) if v is not None and sd > 0 else None

    print(f"  Wide dataframe built: {len(wide_rows)} stations")
    print(f"  High-missingness stations (>=3 NA): {sum(1 for w in wide_rows if w['high_missingness_flag'])}")
    print(f"  Suspicious-zero stations:           {sum(1 for w in wide_rows if w['suspicious_zero_flag'])}")
    print(f"  Imputation: NOT performed (documented design decision)")

    return rows, wide_rows


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — AQI SUB-INDEX COMPUTATION (CPCB 2014)
# ══════════════════════════════════════════════════════════════════════════════

def compute_aqi(wide_rows):
    """
    Computes per-pollutant AQI sub-indexes and composite Calculated AQI.
    Annotates each wide_row in-place.
    Returns updated wide_rows.
    """
    print(f"\n{'='*70}")
    print("STAGE 3 — CPCB 2014 AQI COMPUTATION")
    print(f"{'='*70}")
    print("  Method: piecewise-linear sub-index; composite = max sub-index")
    print("  CO unit: µg/m³ ÷ 1000 = mg/m³ before applying breakpoints")
    print("  Averaging period: ASSUMED (24h: PM2.5/PM10/SO2/NO2/NH3; 8h: CO/OZONE)")

    si_col_map = {
        "PM2.5": "SI_PM2.5", "PM10": "SI_PM10", "SO2": "SI_SO2",
        "NO2":   "SI_NO2",   "CO":   "SI_CO",   "NH3": "SI_NH3",
        "OZONE": "SI_OZONE",
    }

    sensor_anomaly_stations = set()

    for wr in wide_rows:
        si_vals = {}
        for p in POLLUTANTS:
            raw = wr.get(p)
            # For CO, convert µg/m³ → mg/m³ before sub-index
            conc = (raw / 1000) if (p == "CO" and raw is not None) else raw
            si   = sub_index(p, conc)
            wr[si_col_map[p]] = si
            if si is not None:
                si_vals[p] = si

        # Composite AQI = max sub-index
        if si_vals:
            dom_pol = max(si_vals, key=si_vals.get)
            comp_aqi = round(si_vals[dom_pol], 2)
            wr["calculated_AQI"]           = comp_aqi
            wr["aqi_label"]                = aqi_label(comp_aqi)
            wr["dominant_pollutant_by_AQI"] = dom_pol
            wr["dominant_AQI_subindex"]    = round(si_vals[dom_pol], 2)
        else:
            wr["calculated_AQI"] = wr["aqi_label"] = None
            wr["dominant_pollutant_by_AQI"] = wr["dominant_AQI_subindex"] = None

        # AQI confidence category
        valid_si = len(si_vals)
        if valid_si == len(POLLUTANTS):
            wr["aqi_category"] = "FULL"
        elif valid_si >= 4:
            wr["aqi_category"] = "PARTIAL_HIGH_CONFIDENCE"
        elif valid_si >= 2:
            wr["aqi_category"] = "PARTIAL_LOW_CONFIDENCE"
        elif valid_si == 1:
            wr["aqi_category"] = "SINGLE_POLLUTANT_ONLY"
        else:
            wr["aqi_category"] = "NOT_COMPUTABLE"

        # Sensor anomaly flag: CO flat reading > 100 µg/m³
        co_raw = wr.get("CO")
        if co_raw is not None and co_raw > 100:
            wr["possible_sensor_anomaly"] = True
            sensor_anomaly_stations.add(wr["station"])
        else:
            wr["possible_sensor_anomaly"] = False

    # Summary
    label_counts = Counter(w["aqi_label"] for w in wide_rows if w["aqi_label"])
    cat_counts   = Counter(w["aqi_category"] for w in wide_rows)
    dom_counts   = Counter(w["dominant_pollutant_by_AQI"] for w in wide_rows
                           if w.get("dominant_pollutant_by_AQI"))
    aqi_vals     = sorted(w["calculated_AQI"] for w in wide_rows if w["calculated_AQI"] is not None)
    nat_median   = aqi_vals[len(aqi_vals)//2] if aqi_vals else None

    print(f"\n  National Calculated AQI summary ({len(aqi_vals)} stations with valid AQI):")
    print(f"    Median: {nat_median}")
    print(f"    Min:    {aqi_vals[0] if aqi_vals else 'N/A'}")
    print(f"    Max:    {aqi_vals[-1] if aqi_vals else 'N/A'}")
    print(f"\n  AQI Category distribution:")
    for lbl in ["Good","Satisfactory","Moderate","Poor","Very Poor","Severe"]:
        print(f"    {lbl:14s}: {label_counts.get(lbl, 0):>4d} stations")
    print(f"\n  AQI Confidence:")
    for cat, cnt in cat_counts.most_common():
        print(f"    {cat:35s}: {cnt}")
    print(f"\n  Dominant AQI pollutant:")
    for pol, cnt in dom_counts.most_common():
        print(f"    {pol:8s}: {cnt:>4d} stations ({100*cnt/len(wide_rows):.1f}%)")
    print(f"\n  Possible sensor anomalies (CO flat >100 µg/m³): {len(sensor_anomaly_stations)}")
    for s in sorted(sensor_anomaly_stations):
        print(f"    {s}")

    return wide_rows


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — EDA CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def run_eda(wide_rows, long_rows):
    """Print the key EDA findings used in the dashboard and report."""
    print(f"\n{'='*70}")
    print("STAGE 4 — EDA CALCULATIONS")
    print(f"{'='*70}")

    aqi_vals = [w["calculated_AQI"] for w in wide_rows if w["calculated_AQI"] is not None]
    aqi_vals_s = sorted(aqi_vals)
    n = len(aqi_vals_s)
    p75_aqi = aqi_vals_s[int(0.75 * n)]

    # 4a: PM2.5 dominance
    pm25_dom = sum(1 for w in wide_rows if w.get("dominant_pollutant_by_AQI") == "PM2.5")
    above150_total = sum(1 for w in wide_rows if w["calculated_AQI"] and w["calculated_AQI"] > 150)
    above150_pm25  = sum(1 for w in wide_rows
                         if w["calculated_AQI"] and w["calculated_AQI"] > 150
                         and w.get("dominant_pollutant_by_AQI") == "PM2.5")
    print(f"\n  [F1] PM2.5 AQI driver: {pm25_dom}/{len(wide_rows)} stations "
          f"({100*pm25_dom/len(wide_rows):.1f}%)")
    print(f"       Above AQI 150 — PM2.5 drives: {above150_pm25}/{above150_total} "
          f"({100*above150_pm25/above150_total:.1f}% — should be 100%)")

    # 4b: Composition divergence — pairs with similar AQI, different dominant pollutant
    pair_count = 0
    stns = [w for w in wide_rows if w["calculated_AQI"] and w.get("dominant_pollutant_by_AQI")]
    for i in range(len(stns)):
        for j in range(i + 1, len(stns)):
            if (abs(stns[i]["calculated_AQI"] - stns[j]["calculated_AQI"]) <= 20
                    and stns[i]["dominant_pollutant_by_AQI"] != stns[j]["dominant_pollutant_by_AQI"]
                    and stns[i]["calculated_AQI"] < 150):
                pair_count += 1
    print(f"\n  [F2] Station-pairs: same AQI (±20), different dominant pollutant, AQI<150: {pair_count}")

    # 4c: Entropy vs AQI (Spearman correlation approximation)
    SI_COLS = ["SI_PM2.5","SI_PM10","SI_SO2","SI_NO2","SI_CO","SI_NH3","SI_OZONE"]
    ent_data = []
    for w in wide_rows:
        si_list = [w.get(k) for k in SI_COLS]
        ent = shannon_entropy(si_list)
        if ent is not None and w["calculated_AQI"] is not None:
            ent_data.append((w["calculated_AQI"], ent))

    # Spearman: rank correlation
    n_e = len(ent_data)
    aqi_ranks = {v: r for r, v in enumerate(sorted(x[0] for x in ent_data), 1)}
    ent_ranks = {v: r for r, v in enumerate(sorted(x[1] for x in ent_data), 1)}
    d2_sum = sum((aqi_ranks[a] - ent_ranks[e]) ** 2 for a, e in ent_data)
    spearman_rho = 1 - (6 * d2_sum) / (n_e * (n_e ** 2 - 1)) if n_e > 2 else None
    print(f"\n  [F4] Spearman rho(Calculated AQI, Entropy): {spearman_rho:.3f} (n={n_e})")

    # 4d: Within-city variability — Delhi
    delhi_stns = [w for w in wide_rows if w.get("city") == "Delhi" and w["calculated_AQI"]]
    if delhi_stns:
        d_aqis = [w["calculated_AQI"] for w in delhi_stns]
        print(f"\n  [F5] Delhi within-city AQI: n={len(d_aqis)}, "
              f"min={min(d_aqis):.0f}, max={max(d_aqis):.0f}, "
              f"range={max(d_aqis)-min(d_aqis):.0f}, "
              f"std={math.sqrt(sum((v-sum(d_aqis)/len(d_aqis))**2 for v in d_aqis)/len(d_aqis)):.1f}")

    # 4e: Coverage inequality
    state_counts = Counter(w["state"] for w in wide_rows)
    top5 = state_counts.most_common(5)
    top5_total = sum(v for _, v in top5)
    single_states = sum(1 for _, v in state_counts.items() if v == 1)
    print(f"\n  [F6] Coverage: top 5 states hold {top5_total}/{len(wide_rows)} stations "
          f"({100*top5_total/len(wide_rows):.1f}%)")
    print(f"       States/UTs with only 1 station: {single_states}")

    # 4f: NH3 never drives AQI
    nh3_dom = sum(1 for w in wide_rows if w.get("dominant_pollutant_by_AQI") == "NH3")
    print(f"\n  [F7] NH3 drives AQI: {nh3_dom} stations (expect 0)")

    # 4g: Full vs partial confidence AQI medians
    full_aqis = sorted(w["calculated_AQI"] for w in wide_rows
                       if w.get("aqi_category") == "FULL" and w["calculated_AQI"])
    part_aqis = sorted(w["calculated_AQI"] for w in wide_rows
                       if w.get("aqi_category") in ("PARTIAL_HIGH_CONFIDENCE","PARTIAL_LOW_CONFIDENCE")
                       and w["calculated_AQI"])
    full_med = full_aqis[len(full_aqis)//2] if full_aqis else None
    part_med = part_aqis[len(part_aqis)//2] if part_aqis else None
    print(f"\n  [F8] Full-confidence stations median AQI:    {full_med}")
    print(f"       Partial-confidence stations median AQI: {part_med}")

    print(f"\n  AQI P75 (used for quadrant thresholds): {p75_aqi:.0f}")

    # 4h: Pollutant missingness summary
    print(f"\n  Pollutant missingness (of 501 stations):")
    for p in POLLUTANTS:
        na = sum(1 for w in wide_rows if w.get(p) is None)
        print(f"    {p:8s}: {na:>3d} ({100*na/len(wide_rows):.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 5 — SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def save_long_csv(long_rows):
    print(f"\n{'='*70}")
    print("STAGE 5a — SAVE CLEANED LONG CSV")
    print(f"{'='*70}")
    if not long_rows:
        print("  No rows — skipped")
        return
    with open(LONG_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(long_rows[0].keys()))
        writer.writeheader()
        writer.writerows(long_rows)
    print(f"  Saved: {LONG_OUT}  ({len(long_rows)} rows × {len(long_rows[0])} cols)")


def save_wide_csv(wide_rows):
    print(f"\n{'='*70}")
    print("STAGE 5b — SAVE CLEANED WIDE CSV")
    print(f"{'='*70}")
    if not wide_rows:
        print("  No rows — skipped")
        return
    with open(WIDE_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(wide_rows[0].keys()))
        writer.writeheader()
        writer.writerows(wide_rows)
    print(f"  Saved: {WIDE_OUT}  ({len(wide_rows)} rows × {len(wide_rows[0])} cols)")


def save_subindex_csv(wide_rows):
    print(f"\n{'='*70}")
    print("STAGE 5c — SAVE AQI SUB-INDEX RESULTS CSV")
    print(f"{'='*70}")
    si_cols = ["SI_PM2.5","SI_PM10","SI_SO2","SI_NO2","SI_CO","SI_NH3","SI_OZONE"]
    fields  = ["station","city","state","calculated_AQI","aqi_label","aqi_category",
               "dominant_pollutant_by_AQI","dominant_AQI_subindex"] + si_cols
    with open(SUBINDEX_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(wide_rows)
    print(f"  Saved: {SUBINDEX_OUT}  ({len(wide_rows)} rows × {len(fields)} cols)")


def save_dashboard_json(wide_rows, long_rows):
    """Delegate to the same logic as prep_dashboard_data.py."""
    print(f"\n{'='*70}")
    print("STAGE 5d — GENERATE DASHBOARD DATA JSON")
    print(f"{'='*70}")

    SI_COLS = ["SI_PM2.5","SI_PM10","SI_SO2","SI_NO2","SI_CO","SI_NH3","SI_OZONE"]

    def _flt(v):
        if v in ("","None","NA",None): return None
        try: return float(v)
        except: return None

    # National summary
    aqi_vals = sorted(w["calculated_AQI"] for w in wide_rows if w["calculated_AQI"] is not None)
    nat_med  = aqi_vals[len(aqi_vals)//2] if aqi_vals else None
    full_pct = round(100 * sum(1 for w in wide_rows if w.get("aqi_category")=="FULL") / len(wide_rows), 1)

    label_dist = dict(Counter(w["aqi_label"] for w in wide_rows))
    dom_dist   = dict(Counter(w["dominant_pollutant_by_AQI"] for w in wide_rows
                              if w.get("dominant_pollutant_by_AQI")))
    cat_dist   = dict(Counter(w["aqi_category"] for w in wide_rows))

    # Pollutant missingness
    pol_na_national = {}
    for p in POLLUTANTS:
        pl = [r for r in long_rows if r.get("pollutant_id","").strip()==p]
        na = sum(1 for r in pl if r.get("is_na_reading") in (True,"True"))
        pol_na_national[p] = {"na":na,"total":len(pl),
                              "pct":round(100*na/len(pl),1) if pl else 0}

    # Stations
    stations_out = []
    for w in wide_rows:
        lat = _flt(w.get("latitude")); lon = _flt(w.get("longitude"))
        if lat is None or lon is None: continue
        si_list = [w.get(k) for k in SI_COLS]
        ent = shannon_entropy(si_list)
        stations_out.append({
            "station":w["station"],"city":w["city"],"state":w["state"],
            "lat":lat,"lon":lon,"aqi":w.get("calculated_AQI"),
            "aqi_label":w.get("aqi_label",""),"aqi_category":w.get("aqi_category",""),
            "dominant":w.get("dominant_pollutant_by_AQI",""),
            "dominant_si":w.get("dominant_AQI_subindex"),
            "board":w.get("board_acronym",""),
            "completeness":w.get("completeness_pct"),
            "suspicious_zero":w.get("suspicious_zero_flag") in (True,"True"),
            "sensor_anomaly":w.get("possible_sensor_anomaly") in (True,"True"),
            "high_miss":w.get("high_missingness_flag") in (True,"True"),
            "pm25":w.get("PM2.5"),"pm10":w.get("PM10"),"so2":w.get("SO2"),
            "no2":w.get("NO2"),"co":w.get("CO"),"nh3":w.get("NH3"),"ozone":w.get("OZONE"),
            "si_pm25":w.get("SI_PM2.5"),"si_pm10":w.get("SI_PM10"),"si_so2":w.get("SI_SO2"),
            "si_no2":w.get("SI_NO2"),"si_co":w.get("SI_CO"),"si_nh3":w.get("SI_NH3"),
            "si_ozone":w.get("SI_OZONE"),"entropy":ent,
            "valid_count":int(w.get("valid_pollutant_count") or 0),
        })

    # Entropy scatter
    entropy_data = [
        {"station":w["station"],"city":w["city"],"state":w["state"],
         "aqi":w["calculated_AQI"],"entropy":shannon_entropy([w.get(k) for k in SI_COLS]),
         "dominant":w.get("dominant_pollutant_by_AQI",""),
         "aqi_label":w.get("aqi_label",""),
         "valid_count":int(w.get("valid_pollutant_count") or 0)}
        for w in wide_rows
        if w["calculated_AQI"] is not None
        and shannon_entropy([w.get(k) for k in SI_COLS]) is not None
    ]

    # City variability
    city_g = defaultdict(list)
    for w in wide_rows: city_g[w["city"]].append(w)
    city_var = []
    for city, rows in city_g.items():
        al = sorted(w["calculated_AQI"] for w in rows if w["calculated_AQI"] is not None)
        if len(al) < 2: continue
        nm = len(al); m = sum(al)/nm
        sd = math.sqrt(sum((v-m)**2 for v in al)/nm)
        city_var.append({
            "city":city,"state":rows[0]["state"],"n":nm,
            "median":round(al[nm//2],1),"mean":round(m,1),"std":round(sd,1),
            "min":al[0],"max":al[-1],"range":round(al[-1]-al[0],1),
            "q1":al[nm//4],"q3":al[(3*nm)//4],"iqr":round(al[(3*nm)//4]-al[nm//4],1),
            "cv":round(sd/m,3) if m>0 else 0,
            "stations":sorted([{"station":w["station"],"aqi":w["calculated_AQI"],
                                 "dominant":w.get("dominant_pollutant_by_AQI",""),
                                 "completeness":w.get("completeness_pct"),
                                 "aqi_label":w.get("aqi_label","")}
                                for w in rows if w["calculated_AQI"]],
                               key=lambda x: -(x["aqi"] or 0))
        })
    city_var.sort(key=lambda x: -x["n"])

    # State coverage
    state_g = defaultdict(list)
    for w in wide_rows: state_g[w["state"]].append(w)
    state_cov = []
    for state, rows in sorted(state_g.items(), key=lambda x:-len(x[1])):
        al = sorted(w["calculated_AQI"] for w in rows if w["calculated_AQI"] is not None)
        nc = len(set(w["city"] for w in rows))
        fc = sum(1 for w in rows if w.get("aqi_category")=="FULL")
        hm = sum(1 for w in rows if w.get("high_missingness_flag") in (True,"True"))
        dm = Counter(w.get("dominant_pollutant_by_AQI","") for w in rows
                     if w.get("dominant_pollutant_by_AQI","")).most_common(1)
        n  = len(rows)
        state_long = [r for r in long_rows if r.get("state")==state]
        pol_na = {}
        for p in POLLUTANTS:
            sp = [r for r in state_long if r.get("pollutant_id","").strip()==p]
            na = sum(1 for r in sp if r.get("is_na_reading") in (True,"True"))
            pol_na[p] = round(100*na/len(sp),1) if sp else 0
        state_cov.append({
            "state":state,"n_stations":n,"n_cities":nc,
            "median_aqi":al[n//2] if al else None,
            "full_aqi_pct":round(100*fc/n,1),
            "high_miss_count":hm,"dom_pollutant":dm[0][0] if dm else "N/A",
            "vp_severe_pct":round(100*sum(1 for v in al if v>=300)/n,1) if n else 0,
            "pol_na":pol_na,"low_sample":n<5,
        })

    # Band data
    bands = [("Good","0–50",0,50),("Satisfactory","51–100",51,100),
             ("Moderate-Low","101–150",101,150),("Moderate-High","151–200",151,200),
             ("Poor","201–300",201,300),("Very Poor","301–500",301,500)]
    band_data = []
    for bname, brange, lo, hi in bands:
        ib = [w for w in wide_rows if w["calculated_AQI"] is not None and lo<=w["calculated_AQI"]<=hi]
        if not ib: continue
        dc = Counter(w.get("dominant_pollutant_by_AQI","") for w in ib
                     if w.get("dominant_pollutant_by_AQI",""))
        band_data.append({"band":bname,"range":brange,"count":len(ib),
                           "dom_dist":dict(dc),"n_distinct_dom":len([k for k,v in dc.items() if k])})

    # National P75 per pollutant
    nat_p75 = {}
    for p in POLLUTANTS:
        pv = sorted(w[p] for w in wide_rows if w.get(p) is not None)
        if pv:
            nat_p75[p] = pv[int(0.75*len(pv))]

    # City profiles
    city_profs = []
    for city, rows in city_g.items():
        prof = {"city":city,"state":rows[0]["state"],"n":len(rows)}
        for p in POLLUTANTS:
            pv = sorted(w[p] for w in rows if w.get(p) is not None)
            if pv:
                med = pv[len(pv)//2]
                prof[p] = med
                ref = nat_p75.get(p) or 1
                prof[f"{p}_norm"] = round(med/ref, 3)
            else:
                prof[p] = prof[f"{p}_norm"] = None
        norms = {p: prof.get(f"{p}_norm") for p in POLLUTANTS if prof.get(f"{p}_norm") is not None}
        prof["signature_pollutant"] = max(norms, key=norms.get) if norms else None
        city_profs.append(prof)
    city_profs.sort(key=lambda x: -(x.get("PM2.5") or 0))

    # Suspicious zeros
    sz = []
    for w in wide_rows:
        if w.get("suspicious_zero_flag") in (True,"True"):
            zp = [p for p in POLLUTANTS if w.get(p) == 0.0]
            sz.append({"station":w["station"],"city":w["city"],"state":w["state"],
                       "zero_pollutants":zp,"aqi":w.get("calculated_AQI"),
                       "completeness":w.get("completeness_pct")})

    # Sensor anomalies
    sa = [{"station":w["station"],"city":w["city"],"state":w["state"],
            "co":w.get("CO"),"aqi":w.get("calculated_AQI"),
            "dominant":w.get("dominant_pollutant_by_AQI","")}
           for w in wide_rows if w.get("possible_sensor_anomaly") in (True,"True")]

    out = {
        "meta":{
            "snapshot_date":"2026-09-23","snapshot_time":"12:00:00 IST",
            "n_stations":len(wide_rows),
            "n_cities":len(set(w["city"] for w in wide_rows)),
            "n_states":len(set(w["state"] for w in wide_rows)),
            "national_median_aqi":nat_med,"complete_aqi_pct":full_pct,
            "disclaimer":"Calculated AQI — CPCB 2014 methodology. Single cross-sectional snapshot. Not official CPCB-reported AQI.",
        },
        "national":{"aqi_label_dist":label_dist,"dom_pollutant_dist":dom_dist,
                    "aqi_category_dist":cat_dist,"pol_na_national":pol_na_national},
        "stations":stations_out,"entropy_scatter":entropy_data,
        "city_variability":city_var,"state_coverage":state_cov,
        "band_data":band_data,"city_profiles":city_profs,"nat_p75":nat_p75,
        "suspicious_zeros":sz,"sensor_anomalies":sa,
    }

    with open(DASHBOARD_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"  Saved: {DASHBOARD_OUT}")
    print(f"    stations:         {len(stations_out)}")
    print(f"    entropy_scatter:  {len(entropy_data)}")
    print(f"    city_variability: {len(city_var)}")
    print(f"    state_coverage:   {len(state_cov)}")
    print(f"    band_data:        {len(band_data)}")
    print(f"    city_profiles:    {len(city_profs)}")
    print(f"    suspicious_zeros: {len(sz)}")
    print(f"    sensor_anomalies: {len(sa)}")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("India Air Quality Intelligence — Reproducible Pipeline")
    print("=" * 70)
    print("IMPORTANT: All AQI values produced here are CALCULATED AQI.")
    print("They are NOT official CPCB-reported AQI values.")
    print("This dataset is a single cross-sectional snapshot (23 Sep 2026, 12:00 IST).")
    print("No temporal trends or seasonal analysis are attempted.")
    print("=" * 70)

    raw          = load_raw(RAW_FILE)
    long_rows, wide_rows = clean_and_engineer(raw)
    wide_rows    = compute_aqi(wide_rows)
    run_eda(wide_rows, long_rows)
    save_long_csv(long_rows)
    save_wide_csv(wide_rows)
    save_subindex_csv(wide_rows)
    save_dashboard_json(wide_rows, long_rows)

    print(f"\n{'='*70}")
    print("PIPELINE COMPLETE")
    print(f"{'='*70}")
    print("Output files:")
    for f in [LONG_OUT, WIDE_OUT, SUBINDEX_OUT, DASHBOARD_OUT]:
        size = os.path.getsize(f) if os.path.exists(f) else 0
        print(f"  {f:40s}  {size/1024:.1f} KB")
    print()
    print("Dashboard:")
    print("  Serve with:  python -m http.server 8000")
    print("  Open:        http://localhost:8000/dashboard.html")
