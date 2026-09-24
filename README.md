# India's Air Quality Intelligence (Analysis)

### Discovering Pollution Signatures, AQI Drivers, Within-City Variability & Data Quality

An end-to-end **Data Analytics & Exploratory Data Analysis project** using the **CPCB Continuous Ambient Air Quality Monitoring Station (CAAQMS)** dataset from the Government of India's Open Government Data Platform.

This project transforms raw air-quality monitoring data into a cleaned analytical dataset, calculates **CPCB 2014-based AQI sub-indexes**, identifies dominant pollution drivers, measures pollutant-profile diversity, analyzes monitoring coverage and data quality, and presents the findings through an **interactive 8-page dashboard**.

> **Important:** All AQI values in this project are **Calculated AQI values derived using the CPCB 2014 National Air Quality Index methodology**. They are not official CPCB-reported AQI values.

---

## 📌 Project Overview

Air-quality dashboards often reduce pollution to a single AQI number. This project goes beyond the overall AQI to investigate the underlying pollutant composition and data quality.

### Key Questions

- Which pollutant actually drives AQI at each monitoring station?
- Does the dominant pollutant vary across states and regions?
- Can two stations have similar AQI values but fundamentally different pollution profiles?
- How much does AQI vary between monitoring stations within the same city?
- Is higher AQI associated with lower pollutant-profile diversity?
- Where is air-quality monitoring coverage concentrated?
- Where are the largest data-quality gaps?
- How does missing pollutant data affect AQI confidence?
- Which pollutants contribute most to the calculated AQI?

The project uses the **monitoring station as the primary analytical unit** instead of relying only on city-level averages.

---

## 📊 Dataset

### Source

**Government of India Open Government Data Platform — data.gov.in**

- **Dataset:** CPCB Real-time Air Quality Index
- **Publisher:** Central Pollution Control Board (CPCB), MoEFCC, Government of India
- **Resource UUID:** `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`
- **Snapshot:** 23 September 2026, 12:00 IST
- **Data type:** Single cross-sectional snapshot
- **License:** National Data Sharing and Accessibility Policy (NDSAP)

### Dataset Dimensions

| Metric | Value |
|---|---:|
| Raw rows | 3,507 |
| Raw columns | 11 |
| Monitoring stations | 501 |
| Cities | 263 |
| States / UTs | 31 |
| Pollutants | 7 |
| Missing pollutant readings | 343 |
| Missingness | 9.8% |

The raw dataset is in **long format**, with each monitoring station appearing once for each of the seven pollutants.

### Pollutants

- PM2.5
- PM10
- SO2
- NO2
- CO
- NH3
- OZONE

---

# 🔄 Project Workflow

Raw CPCB CAAQMS Dataset
          │
          ▼
     Data Inspection
          │
          ▼
Data Cleaning & Validation
          │
          ├── Numeric parsing
          ├── Missing-value detection
          ├── Station-name standardisation
          ├── Coordinate validation
          ├── Suspicious-zero detection
          └── CO unit conversion
          │
          ▼
 Feature Engineering
          │
          ├── Station completeness
          ├── Pollutant profiles
          ├── Z-scores
          ├── AQI confidence
          └── Quality flags
          │
          ▼
CPCB 2014 AQI Calculation
          │
          ├── Pollutant sub-indexes
          ├── Composite AQI
          └── Dominant pollutant
          │
          ▼
Exploratory Data Analysis
          │
          ├── AQI distribution
          ├── Pollutant dominance
          ├── Composition divergence
          ├── Shannon entropy
          ├── Regional signatures
          ├── Within-city variability
          └── Monitoring coverage
          │
          ▼
 Interactive Dashboard
          │
          ▼
 Analytical Report


### 🧹 Data Cleaning & Quality
The raw dataset was preserved and all transformations were performed on a working copy.

## 1. Numeric Parsing
The following fields were converted to numeric values:
- pollutant_min
-pollutant_max
- pollutant_avg
- latitude
- longitude

The original pollutant fields were preserved while numeric versions were created for analysis.
- NA values were converted to null/NaN.

## 2. Missing Values
- There were 343 missing pollutant_avg readings, representing approximately 9.8% of all raw records.
- Missing values were not imputed.
- Instead, missingness was retained and propagated through the analysis. AQI confidence categories were used to communicate the completeness of the underlying pollutant measurements.

## 3. Station Name Cleaning
- 35 station names contained leading/trailing whitespace.
- These values were standardised before station-level aggregation.
- Board acronyms were also extracted from station names containing the " - " suffix pattern.

## 4. Geographic Validation
The dataset was checked for:
- Missing latitude
- Missing longitude
- Coordinates outside India
- Duplicate coordinates
- Duplicate station names

## Results
# Quality Check	       Result
- Missing latitude	          0
- Missing longitude	          0
- Coordinates outside India	0
- Duplicate coordinates	0
- Duplicate station names	0

## 5. Suspicious Zero Detection
- Zero readings for NH3 and SO2 were flagged when they occurred at stations that were otherwise actively reporting other pollutants.
- These records were not deleted.
- They were retained and marked as suspicious observations requiring validation rather than being automatically treated as erroneous measurements.

## 6. CO Unit Conversion
The source CSV contains CO values interpreted as µg/m³.
However, the CPCB AQI breakpoints for CO are expressed in mg/m³.
Therefore:
# CO_mg/m³ = CO_µg/m³ ÷ 1000
The original CO value was retained and the converted value was used for AQI sub-index calculation.

### 📐 AQI Methodology

The project implements the CPCB 2014 National Air Quality Index framework using a piecewise-linear sub-index calculation.

For each pollutant:

## SI = I_low + (C - C_low) × (I_high - I_low) / (C_high - C_low)

Where:
C = observed pollutant concentration
C_low = lower concentration breakpoint
C_high = upper concentration breakpoint
I_low = lower AQI breakpoint
I_high = upper AQI breakpoint

The station-level Calculated AQI is the maximum available pollutant sub-index:

Calculated AQI =
MAX(
    SI_PM2.5,
    SI_PM10,
    SI_SO2,
    SI_NO2,
    SI_CO,
    SI_NH3,
    SI_OZONE
)

The pollutant with the highest sub-index is identified as the dominant AQI-driving pollutant.

## 📋 CPCB AQI Categories
AQI Range	Category
0–50	Good
51–100	Satisfactory
101–200	Moderate
201–300	Poor
301–400	Very Poor
401–500	Severe

## 🧮 Pollutant Breakpoints
The project implements the CPCB 2014 pollutant breakpoints for:
PM2.5
PM10
SO2
NO2
CO
NH3
OZONE

CO breakpoints are applied after converting the dataset's CO values from µg/m³ to mg/m³.

The implemented breakpoint tables are contained directly in the Python analysis pipeline.

## 📊 AQI Confidence Classification

Not every station has all seven pollutant measurements.

To avoid treating incomplete measurements as equivalent to fully measured stations, the project classifies AQI results into four confidence groups:

FULL
PARTIAL_HIGH_CONFIDENCE
PARTIAL_LOW_CONFIDENCE
SINGLE_POLLUTANT_ONLY

This allows calculated AQI to be interpreted together with the completeness of the underlying pollutant data.

## 🔬 Feature Engineering

The project creates station-level analytical features including:

Pollution Profile Features
Valid pollutant count
Missing pollutant count
Completeness percentage
Total concentration
Mean concentration
Median concentration
Concentration range
Maximum pollutant concentration
AQI Features
Calculated AQI
AQI category
AQI confidence category
Dominant pollutant
Dominant AQI sub-index
Individual pollutant AQI sub-indexes
Data Quality Features
Missing-value flags
Suspicious-zero flags
Sensor-anomaly flags
Station completeness
Geographic validation flags
Statistical Features
Pollutant z-scores
Shannon entropy

Z-scores are used for clustering/similarity analysis only and are not used in AQI computation.

## 📈 Exploratory Data Analysis
1. Dominant Pollutant Analysis

For every station, the pollutant with the highest AQI sub-index was identified.

This allows pollutant dominance to be analyzed at:

National level
State level
City level
Individual station level
2. Composition Divergence

The project investigates whether stations with similar AQI values necessarily have similar pollutant compositions.

Stations with similar AQI values were compared based on their dominant AQI-driving pollutant.

This analysis demonstrates that similar AQI values can correspond to different pollution compositions.

3. Shannon Entropy

Shannon entropy was calculated from the pollutant AQI sub-index profile.

It is used as a measure of pollutant-profile diversity.

Conceptually:

Low entropy
    ↓
One or a few pollutants dominate

High entropy
    ↓
Multiple pollutants contribute more evenly

The project then examines the relationship between AQI magnitude and pollutant-profile diversity.

4. Within-City Variability

Rather than representing a city using a single AQI number, the project analyzes station-level AQI distributions within cities.

Metrics include:

Minimum AQI
Maximum AQI
AQI range
Standard deviation
Station-level distribution

This highlights differences between monitoring locations inside the same city.

5. Monitoring Coverage

Station counts were analyzed across states and UTs to identify differences in monitoring infrastructure.

The analysis highlights regions where city/state-level conclusions may be based on relatively limited station coverage.

6. Data Quality Analysis

The project tracks:

Missing pollutant readings
Station completeness
Suspicious zero readings
Potential CO sensor anomalies
Coordinate validity
AQI confidence categories
🔎 Key Findings
1. PM2.5 Dominates National AQI

PM2.5 is the dominant AQI driver at:

358 / 501 stations

or approximately:

71.5%

of monitoring stations in the snapshot.

This makes PM2.5 the most prominent AQI-driving pollutant nationally in this dataset.

2. Similar AQI Does Not Mean Similar Pollution Composition

The analysis identified:

10,700+

station pairs with similar AQI values but different dominant pollutants.

This demonstrates that two locations can report similar AQI levels while being driven by different pollutants.

The composition divergence is particularly visible at lower AQI levels.

3. Odisha Shows a Strong OZONE Signature

OZONE drives the Calculated AQI at:

45 stations nationally

In Odisha:

52.6%

of monitoring stations are OZONE-driven.

This creates a distinct regional pollution signature that would be less visible from national-level averages alone.

4. Higher AQI Is Associated With Lower Pollutant Diversity

The relationship between Calculated AQI and Shannon entropy produced:

Spearman ρ = -0.619

The negative association indicates that higher-AQI stations tend to have less diverse pollutant sub-index profiles, while lower-AQI stations generally show more balanced pollutant contributions.

This is an observed statistical association and should not be interpreted as proof of causation.

5. Large Within-City Variation in Delhi

Delhi contains:

45 monitoring stations

in this snapshot.

The station-level Calculated AQI ranges from:

41 → 388

with a range of:

347 AQI points

and a standard deviation of approximately:

82.9

This demonstrates substantial variation between monitoring locations within the same city.

6. Unequal Monitoring Coverage

The top five states account for:

55.5%

of all monitoring stations.

At the same time:

9 states / UTs

have only one monitoring station.

This creates an important limitation when comparing regional air-quality conditions using station-level observations.

7. NH3 Does Not Drive Calculated AQI

NH3 drives the Calculated AQI at:

0 / 501 stations

in this snapshot.

The observed NH3 concentrations remain well below the CPCB breakpoint levels required for NH3 to become a high AQI contributor.

NH3 also has the highest missingness among the seven pollutants:

17.8%
8. AQI Confidence and Missing Data

The analysis found different median AQI values between confidence groups:

AQI Confidence	Median Calculated AQI
Full confidence	93.0
Partial confidence	67.5

This difference indicates that missing pollutant measurements may not be randomly distributed across stations and should therefore be considered when interpreting aggregate AQI statistics.

🖥️ Interactive Dashboard

The project includes an 8-page interactive analytical dashboard built using:

HTML5
CSS3
JavaScript
SVG
ECharts 5.4.3
JSON

The dashboard uses the pre-processed:

dashboard_data.json

file as its analytical data source.

📑 Dashboard Pages
Page	Analysis
1	National AQI Snapshot
2	AQI Drivers
3	Composition Divergence
4	Pollution Signatures
5	Concentration vs Diversity
6	Within-City Variability
7	Coverage & Data Quality
8	Methodology
📊 Dashboard Visualizations

The dashboard contains analytical views including:

National AQI distribution
AQI category distribution
Dominant pollutant analysis
India monitoring-station map
State-level pollutant drivers
Station-level pollutant profiles
AQI-band analysis
City pollution heatmaps
City pollutant radar profiles
Shannon entropy scatter plot
AQI vs diversity analysis
Within-city AQI distributions
Monitoring coverage analysis
Missing-data analysis
AQI confidence analysis
Data-quality flags
CPCB AQI breakpoint reference
📁 Repository Structure
India-Air-Quality-Intelligence/
│
├── 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69.csv
│   └── Raw CPCB CAAQMS dataset
│
├── SakshiMukherjee_IndiaAirQualityIntelligence.py
│   └── Reproducible Python analysis pipeline
│
├── aqi_cleaned_long.csv
│   └── Cleaned long-format station × pollutant dataset
│
├── aqi_cleaned_wide.csv
│   └── Station-level wide-format analytical dataset
│
├── aqi_subindex_results.csv
│   └── Pollutant-level CPCB AQI sub-index calculations
│
├── dashboard_data.json
│   └── Dashboard-ready analytical dataset
│
├── dashboard.html
│   └── Interactive 8-page dashboard
│
├── cleaning_audit_log.txt
│   └── Data-cleaning and quality-control audit trail
│
├── India_Air_Quality_Intelligence_Report_Final.pdf
│   └── Detailed analytical report
│
├── requirements.txt
│   └── Dependency and environment information
│
└── README.md
    └── Project documentation
⚙️ Technologies Used
Python 3
HTML5
CSS3
JavaScript
ECharts 5.4.3
SVG
JSON
CSV
Git
GitHub
🐍 Python Dependencies

The analysis pipeline uses only the Python standard library.

No third-party Python packages are required.

Standard-library modules include:

csv
json
math
os
sys
collections
statistics
▶️ Running the Project
1. Clone the Repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd India-Air-Quality-Intelligence
2. Run the Python Pipeline
python SakshiMukherjee_IndiaAirQualityIntelligence.py

The pipeline performs:

Raw Data Loading
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
CPCB AQI Sub-index Calculation
        ↓
Exploratory Data Analysis
        ↓
Dashboard Data Generation

The following analytical outputs are generated or updated:

aqi_cleaned_long.csv
aqi_cleaned_wide.csv
aqi_subindex_results.csv
dashboard_data.json
🌐 Running the Dashboard

The dashboard is a standalone HTML/JavaScript application.

Because the dashboard loads dashboard_data.json using fetch(), it should be served through a local HTTP server rather than opened directly using file://.

Run:

python -m http.server 8000

Then open:

http://localhost:8000/dashboard.html

The dashboard will load the processed JSON data and render the interactive visualizations.

🔁 Reproducible Pipeline

The Python script follows five major stages:

STAGE 1
Load Raw Data

        ↓

STAGE 2
Data Cleaning & Feature Engineering

        ↓

STAGE 3
CPCB 2014 AQI Sub-index Calculation

        ↓

STAGE 4
Exploratory Data Analysis

        ↓

STAGE 5
Dashboard Data Generation

This makes the project reproducible from the raw dataset through to the dashboard-ready output.

📦 Main Output Files
aqi_cleaned_long.csv

Cleaned long-format dataset containing station × pollutant observations and additional quality/feature-engineering columns.

aqi_cleaned_wide.csv

Station-level dataset where pollutant measurements are represented as separate columns.

It also contains station-level pollution-profile and AQI-related features.

aqi_subindex_results.csv

Contains the calculated CPCB pollutant-level AQI sub-index results.

dashboard_data.json

Pre-processed analytical data used by the interactive dashboard.

It contains national summaries, station-level AQI information, pollutant sub-indexes, completeness information, and analytical metrics.

cleaning_audit_log.txt

Documents the data-cleaning and validation operations performed during preprocessing.

India_Air_Quality_Intelligence_Report_Final.pdf

Detailed analytical report containing:

Executive Summary
Problem Statement
Dataset Documentation
Data Dictionary
Data Cleaning
AQI Methodology
Methodology Assumptions
EDA Methodology
Key Findings
Fact → Insight → Risk → Opportunity → Action
Dashboard Overview
Analytical Limitations
Conclusion
Future Scope
References
🧠 Analytical Skills Demonstrated

This project demonstrates practical experience in:

Data Cleaning
Data Validation
Exploratory Data Analysis
Feature Engineering
Statistical Analysis
Missing Data Analysis
Data Quality Assessment
AQI Computation
Piecewise Linear Interpolation
Pollutant Profiling
Shannon Entropy
Correlation Analysis
Geographic Analysis
Within-City Variability Analysis
Monitoring Coverage Analysis
Dashboard Development
Data Visualization
Analytical Storytelling
Reproducible Data Pipelines
Python
JavaScript
ECharts
Git/GitHub
🎯 Business / Analytical Value

The project demonstrates why a single AQI number is not always sufficient for understanding air quality.

The analysis provides a more detailed view by connecting:

AQI Level
   +
Dominant Pollutant
   +
Pollutant Diversity
   +
Station-Level Variation
   +
Monitoring Coverage
   +
Data Quality

This allows users to distinguish between:

How polluted a location is
What pollutant is driving the pollution
How concentrated the pollution profile is
How much variation exists within a city
How complete the underlying measurements are
⚠️ Methodological Assumptions
1. Single Snapshot

The analysis uses:

23 September 2026
12:00 IST

Therefore, the project does not establish:

Temporal trends
Seasonal patterns
Diurnal patterns
Long-term AQI changes

The timestamp is treated as snapshot metadata rather than as a time-series dimension.

2. Pollutant Averaging Period

The source CSV does not document the averaging window represented by pollutant_avg.

For AQI computation, the project assumes:

PM2.5 → 24-hour
PM10  → 24-hour
SO2   → 24-hour
NO2   → 24-hour
NH3   → 24-hour
CO    → 8-hour
OZONE → 8-hour

This assumption follows the averaging periods used in the CPCB 2014 AQI methodology but is not independently verified from the source CSV metadata.

3. Calculated AQI vs Official AQI

All AQI values in this project are calculated independently using CPCB 2014 breakpoints.

They are not official CPCB-reported AQI values.

4. Missing Values

Missing values were not imputed.

Available pollutant measurements were used for calculating available sub-indexes, while AQI confidence categories communicate measurement completeness.

5. Suspicious Measurements

Potentially suspicious NH3/SO2 zero readings and possible CO anomalies were retained and flagged rather than automatically removed.

⚠️ Analytical Limitations

This project has several limitations:

The dataset is a single cross-sectional snapshot.
The averaging period of pollutant_avg is not documented in the source CSV.
Calculated AQI may differ from official CPCB-reported AQI.
Some CO readings may represent sensor anomalies.
Suspicious NH3/SO2 zero values require external validation.
Monitoring coverage is uneven across states.
Station density varies substantially between regions.
No meteorological data is included.
No traffic-density data is included.
No industrial-location data is included.
No land-use data is included.
No health-outcome data is included.
Pollution sources cannot be causally attributed from this dataset alone.
The analysis does not establish causal relationships.
🚀 Future Scope
Time-Series Analysis

With multiple CPCB snapshots or hourly observations, the project could be extended to analyze:

Seasonal trends
Diurnal pollution patterns
AQI changes
Pollution episodes
Long-term trends
Meteorological Integration

Integrating:

Temperature
Humidity
Wind speed
Wind direction
Rainfall

could help investigate relationships between meteorological conditions and pollutant concentrations.

Pollution Source Analysis

Additional datasets could be integrated for:

Traffic density
Industrial locations
Land use
Population density
Road networks

to investigate potential pollution-source associations.

Machine Learning

The station-level pollutant profiles can be extended into:

Station clustering
Pollution-profile classification
Anomaly detection
Similarity analysis

With time-series data, forecasting models could also be explored.

Monitoring Network Optimization

Station coverage analysis could be extended into a monitoring-network optimization study to identify areas where additional monitoring stations may provide greater analytical coverage.

Health Data Integration

Future work could explore relationships between air-quality measurements and health datasets, while accounting for confounding variables and avoiding unsupported causal conclusions.

📌 Project Deliverables

This repository contains the complete analytical workflow and supporting outputs:

Raw CPCB dataset
Cleaned long-format dataset
Cleaned station-level wide-format dataset
CPCB AQI sub-index calculations
Dashboard-ready JSON
Interactive 8-page dashboard
Cleaning and quality audit log
Detailed analytical report
Reproducible Python pipeline
Project documentation
📚 Data Source

Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change, Government of India

Dataset:

CPCB Real-time Air Quality Index

Resource UUID:

3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69

Source platform:

Government of India Open Government Data Platform — data.gov.in

👩‍💻 Author
Sakshi Mukherjee

B.Tech — Computer Science & Engineering
