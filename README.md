# India Air Quality Intelligence

**Discovering Pollution Signatures, Temporal Patterns, Station Variability & Data Quality**

A complete data analytics and exploratory data analysis project built on the official CPCB Real-time Air Quality Index dataset from the Government of India's Open Government Data Platform (data.gov.in).

---

## Quick Start

```bash
# From the project folder, start a local HTTP server
python -m http.server 8000

# Open the dashboard in your browser
http://localhost:8000/dashboard.html
```

> **Important:** The dashboard fetches `dashboard_data.json` via a relative URL. It must be served from a local HTTP server — opening `dashboard.html` directly as a `file://` URL will block the fetch and show an error.

---

## Project Overview

| Item | Value |
|---|---|
| Data source | data.gov.in — CPCB CAAQMS Real-time AQI |
| Resource UUID | `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` |
| Snapshot date/time | 23 September 2026, 12:00:00 IST |
| Monitoring stations | 501 |
| Cities covered | 263 |
| States / UTs covered | 31 |
| National median Calculated AQI | 84.0 (Satisfactory) |
| Full-confidence AQI stations | 359 (71.7%) |

---

## Dashboard Pages

| Page | Title | Key Question Answered |
|---|---|---|
| 1 | National Snapshot | What is the national AQI picture across all 501 stations? |
| 2 | AQI Drivers | Which pollutants drive Calculated AQI, and where? |
| 3 | Composition Divergence | Can stations have the same AQI but different dominant pollutants? |
| 4 | Pollution Signatures | Do cities have identifiable pollutant profile fingerprints? |
| 5 | Concentration vs Diversity | Does higher pollution mean lower pollutant diversity? |
| 6 | Within-City Variability | How much does AQI vary within a single city? |
| 7 | Coverage & Data Quality | Where is monitoring strongest, and where are data gaps? |
| 8 | Methodology | How was Calculated AQI computed? What are the limitations? |

---

## Key Findings

1. **PM2.5 drives Calculated AQI at 71.5% of stations** (358/501). Above AQI 150, PM2.5 drives 100% of stations.
2. **OZONE drives AQI at 45 stations (9%)** — Odisha is the only state where OZONE is the plurality AQI driver (52.6%).
3. **10,905 station-pairs share similar AQI (within 20 pts) but different dominant pollutants** — entirely confined to AQI < 150.
4. **Spearman ρ(AQI, entropy) = −0.619** — higher AQI = lower pollutant-profile diversity. Strong negative association.
5. **Delhi's 45 stations span AQI 41–388 simultaneously** (range = 347, std = 82.9). City-level averages hide this variation.
6. **Top 5 states hold 55.5% of all stations**; 9 states/UTs have only 1 station each.
7. **NH3 never drives composite AQI** — all 501 observed values (max 40 µg/m³) fall in the "Good" sub-index range.
8. **Partial-confidence stations (B/C) have lower median AQI (67.5) than Full-confidence stations (93.0)** — incomplete sensor suites are not random.

---

## Methodology Notes

### AQI Calculation
All AQI values in this project are **Calculated AQI** — computed using the **CPCB 2014 National AQI Framework** (piecewise linear sub-index formula; composite = maximum sub-index). They are **not** the official CPCB-reported AQI values.

### CO Unit Resolution
CO values in the dataset are in **µg/m³** (not mg/m³). Confirmed by physical plausibility — the mg/m³ interpretation would classify every station as Severe, which is impossible. CO values are divided by 1000 before applying CPCB breakpoints (which use mg/m³).

### Averaging Period Assumption
The `pollutant_avg` field's averaging window is not documented in the CSV. **Assumed:**
- 24-hour average for PM2.5, PM10, SO2, NO2, NH3
- 8-hour average for CO and OZONE

### AQI Confidence Categories
| Category | Criteria | Count |
|---|---|---|
| Full (A) | All 7 pollutant sub-indexes available | 359 |
| Partial-High (B) | 4–6 sub-indexes valid | 110 |
| Partial-Low (C) | 1–3 sub-indexes valid | 26 |
| Single (D) | 1 sub-index only | 6 |

### Data Quality Flags
- **13 suspicious zero readings** (NH3 = 11, SO2 = 2) at 12 stations — retained, flagged
- **3 possible sensor anomalies** (CO flat readings > 100 µg/m³: Skara Yokma/Leh, New Anaj Mandi/Khairthal, Kalyana Nagara/Chikkamagaluru) — retained, flagged
- **343 NA readings** (9.8% of 3,507 records) — retained, not imputed

### Cross-sectional Limitation
This is a **single point-in-time snapshot**. No temporal trends, seasonality, or changes over time can be established from this dataset. All associations are observational — no causal claims are made.

---

## File Inventory

```
AQI Project/
├── 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69.csv   # ORIGINAL raw data — DO NOT MODIFY
├── aqi_cleaned_long.csv                         # Cleaned long format (3507 rows × 30 cols)
├── aqi_cleaned_wide.csv                         # Station-level wide format (501 rows × 49 cols)
│                                                #   Includes: calculated_AQI, aqi_label,
│                                                #   aqi_category, dominant_pollutant_by_AQI,
│                                                #   SI_PM2.5–SI_OZONE, possible_sensor_anomaly,
│                                                #   suspicious_zero_flag, completeness_pct, etc.
├── aqi_subindex_results.csv                     # Standalone AQI sub-index results (501 rows × 16 cols)
├── cleaning_audit_log.txt                       # Full transformation audit trail
├── main.py                                      # Reproducible pipeline (stdlib only — no pip needed)
├── requirements.txt                             # Python dependencies (all stdlib, no pip install required)
├── dashboard_data.json                          # Pre-processed dashboard data (~740 KB)
├── prep_dashboard_data.py                       # Alternative script to regenerate dashboard_data.json
├── dashboard.html                               # MAIN DASHBOARD — 8 pages, ECharts + SVG map
│                                                #   Dependencies: ECharts 5.4.3 (CDN), dashboard_data.json
├── India_Air_Quality_Intelligence_Report.pdf    # Final project report (25 pages, ReportLab)
├── generate_report.py                           # PDF report generator (requires: pip install reportlab)
├── india-aqi-dataset-eda-inspection-report.html # Archived EDA inspection report
└── README.md                                    # This file
```

### Key processed columns in `aqi_cleaned_wide.csv`

| Column | Description |
|---|---|
| `calculated_AQI` | Composite AQI (max sub-index, CPCB 2014) |
| `aqi_label` | Good / Satisfactory / Moderate / Poor / Very Poor / Severe |
| `aqi_category` | FULL / PARTIAL_HIGH_CONFIDENCE / PARTIAL_LOW_CONFIDENCE / SINGLE_POLLUTANT_ONLY |
| `dominant_pollutant_by_AQI` | Pollutant with highest sub-index |
| `dominant_AQI_subindex` | Value of the highest sub-index |
| `SI_PM2.5` … `SI_OZONE` | Individual pollutant sub-index values (0–500) |
| `completeness_pct` | % of 7 pollutants with valid readings |
| `suspicious_zero_flag` | TRUE if any pollutant has a suspicious zero reading |
| `possible_sensor_anomaly` | TRUE if CO flat reading > 100 µg/m³ |
| `shannon_entropy` | Shannon entropy of sub-index profile (pollutant diversity measure) |

---

## Running the Reproducible Pipeline

`main.py` is a single-file reproducible pipeline using **only Python standard library** (no pip install required):

```bash
python main.py
```

This will:
1. Load `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69.csv` (raw data)
2. Clean and engineer features → `aqi_cleaned_long.csv`, `aqi_cleaned_wide.csv`
3. Compute CPCB 2014 AQI sub-indexes → `aqi_subindex_results.csv`
4. Print EDA summary statistics
5. Generate `dashboard_data.json`

---

## Data Source

- **Platform:** data.gov.in (Government of India Open Government Data Platform)
- **Dataset:** CPCB Real-time Air Quality Index Data
- **Publisher:** Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change
- **Resource URL:** https://data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69
- **License:** National Data Sharing and Accessibility Policy (NDSAP), Government of India

---

## Limitations

1. **Single snapshot** — no temporal or seasonal analysis possible
2. **Averaging period undocumented** — assumed per CPCB 2014 methodology
3. **Highly unequal station coverage** — top 5 states hold 55.5% of stations; 9 states/UTs have 1 station
4. **Missing lat/lon** — some stations plotted from city-centroid approximations
5. **NH3 and SO2 suspicious zeros** — 13 readings flagged as potentially invalid sensor outputs
6. **CO sensor anomalies** — 3 stations show flat CO readings; AQI may be inflated at these sites
7. **Calculated AQI ≠ Official AQI** — composite AQI is recomputed, not taken from the source field
8. **Cross-sectional associations only** — no causal inference possible
