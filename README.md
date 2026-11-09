# Data Analytics – MGB · Individual Submission
## Validating XYZ's Campaign Intelligence & Approval Platform (CIAP) with synthetic data

Business strategy described and diagnosed (assignment option 1b): would a data-driven, gated campaign
approval process launch better campaigns than XYZ's manual, department-by-department sign-off?

**Live dashboard:** https://ciap-campaign-analytics.streamlit.app
**Source code:** https://github.com/jagjampiaaditya-byte/ciap-campaign-analytics

### What to submit (maps to the assignment)
| Requirement | File(s) |
|---|---|
| 1. Data and Python code | `data/raw/*.csv`, `data/clean/*.csv`, `01_…py` to `05_…py`, `analysis.py`, `app.py` |
| 2. Excel sheet with all calculations | `outputs/CIAP_Calculations.xlsx` |
| 3. Report | `outputs/CIAP_Analytics_Report.docx` (put your name and roll number on the title page) |

| Marks | Step | Where |
|---|---|---|
| 10 | Synthetic data that validates the strategy | `01_generate_synthetic_data.py`, report Section 3 |
| 10 | Data cleaning and transformation | `02_clean_transform.py`, `outputs/cleaning_log.csv`, report Section 4 |
| 30 | Descriptive and diagnostic analytics, Streamlit dashboard, correlation graphs, every graph explained | `app.py`, `analysis.py`, report Sections 5–9 |

### Run
```bash
pip install -r requirements.txt
python 01_generate_synthetic_data.py   # raw data (seed 42, reproducible)
python 02_clean_transform.py           # clean data + cleaning log
streamlit run app.py                   # interactive dashboard (http://localhost:8501)
python 03_eda_figures.py               # report figures
python 04_build_excel.py               # Excel workbook with live formulas
python 05_build_report.py              # Word report
```

### Dashboard tabs
Overview · Data & cleaning · Descriptive · Correlation · Diagnostic · Customers · CIAP back-test · Data explorer.
The sidebar filters (year, type, segment, category, region) recalculate every chart and every explanation.
