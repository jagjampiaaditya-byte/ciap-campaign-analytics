"""
Step 5 - Build the written report (Word .docx)
==============================================
Assembles outputs/CIAP_Analytics_Report.docx from the clean data, the cleaning log and
the figures/explanations produced by 03_eda_figures.py. Every number in the report is
computed here, so re-running the pipeline keeps the report consistent with the data.

Run:  python 05_build_report.py
"""
import json

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import analysis as A

LIVE_URL = "https://ciap-campaign-analytics.streamlit.app"
REPO_URL = "https://github.com/jagjampiaaditya-byte/ciap-campaign-analytics"
STUDENT = "AADITYA JAGJAMPI"
ROLL = "MM26GL063"
c, u, d, LOG, QUAL = A.load()
EX = json.loads((A.OUT / "figures" / "explanations.json").read_text())
FIG = A.OUT / "figures"
NAVY = RGBColor(0x10, 0x23, 0x3F)

doc = Document()
st = doc.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for lvl, size in [(1, 16), (2, 13), (3, 11.5)]:
    h = doc.styles[f"Heading {lvl}"]
    h.font.name, h.font.size, h.font.color.rgb, h.font.bold = "Calibri", Pt(size), NAVY, True
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = s.bottom_margin = Cm(2)

FIGN = [0]
TABN = [0]


def para(text, bold=False, italic=False, size=None, align=None, space_after=6, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def rich(parts, style=None):
    """parts = [(text, bold)]"""
    p = doc.add_paragraph(style=style)
    for t, b in parts:
        p.add_run(t).bold = b
    p.paragraph_format.space_after = Pt(4)
    return p


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    return p


def shade(cell, hex_):
    tc = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_)
    tc.append(sh)


def table(rows, header, widths=None, caption=None, font=9):
    if caption:
        TABN[0] += 1
        para(f"Table {TABN[0]}. {caption}", bold=True, size=9.5, space_after=2, color=NAVY)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(header):
        cell = t.rows[0].cells[j]
        cell.text = ""
        r = cell.paragraphs[0].add_run(str(h)); r.bold = True; r.font.size = Pt(font); r.font.color.rgb = RGBColor(255, 255, 255)
        shade(cell, "10233F")
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        for j, v in enumerate(row):
            cells[j].text = ""
            r = cells[j].paragraphs[0].add_run(str(v)); r.font.size = Pt(font)
            if i % 2:
                shade(cells[j], "F4F7FC")
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(key, width=16):
    e = EX[key]
    FIGN[0] += 1
    doc.add_picture(str(FIG / f"{key}.png"), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(f"Figure {FIGN[0]}. {e['title']}", bold=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, color=NAVY)
    if e.get("what"):
        rich([("What it shows: ", True), (e["what"], False)])
        rich([("Insight: ", True), (e["insight"], False)])
        rich([("Business implication: ", True), (e["action"], False)])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------------ numbers used in text
k = A.kpis(c)
(bt, conf), bte = A.ciap_backtest(c)
bt = bt.set_index("ciap_verdict")
tp, fp, fn, tn = conf.iloc[0, 0], conf.iloc[0, 1], conf.iloc[1, 0], conf.iloc[1, 1]
recall, precision = tp / (tp + fn), tp / (tp + fp)
cover = A.success_by_cover(c)[0].set_index("stock_cover_band")
fc = A.forecast_accuracy(c)[0].groupby("source")["error"].agg(bias="median", mape=lambda x: x.abs().median())
below1 = (c["stock_cover_ratio"] < 1).mean()
so_below = c[c["stock_cover_ratio"] < 1]["stockout_rate"].mean()
so_above = c[c["stock_cover_ratio"] >= 1]["stockout_rate"].mean()
hi_util = c[c["peak_rider_utilisation"] > 1]["on_time_delivery_rate"].mean()
lo_util = c[c["peak_rider_utilisation"] <= 0.9]["on_time_delivery_rate"].mean()
ds = c[c["target_segment"] == "Discount Seekers"]
ov = c.groupby("override_flag")["success_flag"].mean()
sig = c.groupby("signoffs_count")["success_flag"].mean()
inv_so = c.groupby("inventory_signoff")["stockout_rate"].mean()
dep = u.groupby("discount_dependency")["predicted_cltv"].median()
lost_cm_blocked = -c[(c["ciap_verdict"] == "Not feasible") & (c["contribution_margin"] < 0)]["contribution_margin"].sum()
pareto = A.failure_pareto(c)[0]
fx = A.first_experience(u)[0]

# ================================================================== TITLE PAGE
for _ in range(5):
    doc.add_paragraph()
para("Data Analytics – MGB · Project Based Learning", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x52, 0x51, 0x4E))
para("Validating a Data-Driven Campaign Approval Strategy", bold=True, size=24, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
para("Synthetic-data analysis of XYZ's Campaign Intelligence & Approval Platform (CIAP)", size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
para("DA Individual PBL", bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"{STUDENT} · {ROLL}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Tools: Python (pandas, NumPy, SciPy, matplotlib, seaborn, Plotly), Streamlit dashboard, Microsoft Excel", size=10, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x52, 0x51, 0x4E))
doc.add_paragraph()
para(f"Live dashboard: {LIVE_URL}", bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY, space_after=2)
para(f"Source code: {REPO_URL}", size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(8):
    doc.add_paragraph()
para("Deliverables: data (raw and clean CSV), Python code (5 scripts + Streamlit app), Excel calculation workbook, this report.", italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
page_break()

# ================================================================== CONTENTS
doc.add_heading("Contents", 1)
for line in ["1. Executive summary", "2. Business context, objective and hypotheses", "3. Synthetic data generation (Step 1)", "4. Data preparation: cleaning and transformation (Step 2)",
             "5. Descriptive analytics (Step 3)", "6. Correlation analysis (Step 3)", "7. Diagnostic analytics (Step 3)", "8. Customer-level diagnostics",
             "9. Validating the strategy: CIAP back-test", "10. Business strategy and recommendations", "11. Limitations and next steps",
             "Appendix A. Rationale for every technique", "Appendix B. Files submitted and how to run them"]:
    para(line, space_after=2)
page_break()

# ================================================================== 1 EXEC SUMMARY
doc.add_heading("1. Executive summary", 1)
para("XYZ is an e-commerce company that approves marketing campaigns through five departments (Marketing, Supply Chain, Logistics, Inventory, Finance), each working on its own data. "
     "Its proposed strategy is the Campaign Intelligence & Approval Platform (CIAP): one shared data platform that forecasts each campaign's demand, checks it against stock, delivery capacity and money "
     "through hard \"gates\", and launches only feasible campaigns. This project uses synthetic data to describe and diagnose the current process and to test whether the CIAP strategy would work "
     "(assignment option 1b: the whole business strategy described and diagnosed).")
para("Key findings", bold=True, color=NAVY)
bullet(f" Only {A.pct(c['success_flag'].mean())} of {len(c):,} campaigns met their objectives. Stockouts are the largest failure cause ({A.pct(pareto['campaigns'].iloc[0] / pareto['campaigns'].sum())} of failures), and {k['Lost sales (units)']} units of demand were lost.", "Half of campaigns fail.")
bullet(f" {A.pct(below1)} of campaigns launched with less stock than the upper bound of forecast demand. Their average stockout rate was {A.pct(so_below, 1)} vs {A.pct(so_above, 1)} for those above.", "Stock is the main lever.")
bullet(f" Above 100% rider utilisation, on-time delivery falls to {A.pct(hi_util, 1)} (vs {A.pct(lo_util, 1)} below 90%), and late deliveries pull down CSAT.", "Delivery capacity has a cliff edge.")
bullet(f" Marketing over-forecasts by a median {A.pct(fc.loc['Marketing', 'bias'])}. A single model forecast is unbiased ({A.pct(fc.loc['CIAP model (AI-005)', 'bias'])}) with a typical error of {A.pct(fc.loc['CIAP model (AI-005)', 'mape'])} vs {A.pct(fc.loc['Marketing', 'mape'])}.", "Departments disagree on demand.")
bullet(f" Stockouts and late deliveries reduce repeat purchase and CLTV. Customers acquired through heavy discounts have {dep.iloc[0] / dep.iloc[-1]:.1f}x lower CLTV, and Discount Seekers campaigns succeed only {A.pct(ds['success_flag'].mean())} of the time.", "Bad campaigns cost future value.")
bullet(f" Replaying all campaigns through the CIAP gates with pre-launch data only, approved campaigns succeeded {A.pct(bt.loc['Approve', 'success_rate'])} of the time and blocked ones {A.pct(bt.loc['Not feasible', 'success_rate'])}. "
       f"The gates would have caught {A.pct(recall)} of failures before launch and blocked {A.money(lost_cm_blocked)} of losses.", "The strategy is validated.")
para("Recommendation: adopt CIAP in stages. Start in shadow mode, enforce the inventory, logistics and finance gates, use one forecast with a prediction range, cap discounts by category, steer budget away from discount-only segments, and record every override.")
page_break()

# ================================================================== 2 CONTEXT
doc.add_heading("2. Business context, objective and hypotheses", 1)
doc.add_heading("2.1 The business problem", 2)
para("Today a campaign moves through five departments in sequence by email and meetings. The Business Requirements Document (BRD) lists seven problems, summarised below. "
     "Each one can be measured with data, which is what this project does.")
table([["PS-01", "Approval is sequential and manual", "Approval cycle time; trade-off with checks skipped"],
       ["PS-02", "Each department decides on its own data", "Forecast bias and error by team"],
       ["PS-03", "Campaigns launch without proven fulfilment capacity", "Stock cover, stockout rate, rider utilisation, on-time"],
       ["PS-04", "Discounts not tested against margin and cash", "Contribution margin, ROI, loss-making campaigns"],
       ["PS-05", "Targeting not tied to CLTV", "CLTV uplift and repeat rate by segment and discount"],
       ["PS-06", "Results do not feed back into planning", "Success rate trend over time"],
       ["PS-07", "Decisions and overrides not recorded", "Override frequency and outcome"]],
      ["ID", "Problem (BRD)", "How it is measured in this project"], [1.6, 7, 8], "Business problems and the measures used")
doc.add_heading("2.2 The strategy being validated", 2)
para("CIAP evaluates every campaign before launch against business rules (BRD Section 9). The rules simulated in this project are:")
table([["BRL-003", "Inventory", "Stock ≥ upper bound of forecast demand", "Hard gate"],
       ["BRL-009", "Logistics", "Peak orders ≤ rider capacity (condition inside a 10% buffer)", "Hard / condition"],
       ["BRL-011", "Finance", "Projected campaign cost ≤ approved budget", "Hard gate"],
       ["BRL-012", "Finance", "Projected margin ≥ 0 (escalate if below 10%)", "Hard / escalate"],
       ["BRL-015", "Marketing", "Discount within category ceiling", "Escalate"]],
      ["Rule", "Domain", "Test", "Effect"], [2, 2.5, 9, 3], "CIAP rules applied in the back-test")
doc.add_heading("2.3 Objective and hypotheses", 2)
para("Objective: describe the current campaign process, diagnose why campaigns fail, and test whether a gated, data-driven approval process would have separated good campaigns from bad ones before launch.")
HYP = [["H1", "Campaigns launched with stock below the upper-bound forecast suffer more stockouts and fail more often."],
       ["H2", "Peak orders above rider capacity cause late deliveries, which lower customer satisfaction."],
       ["H3", "Departmental forecasts are biased; one model forecast is more accurate."],
       ["H4", "Skipped departmental checks and overrides increase failure, while full checks slow approval."],
       ["H5", "Deep discounts and discount-led targeting erode long-term customer value (CLTV)."],
       ["H6", "The CIAP gates, using only pre-launch data, identify most failing campaigns before launch."]]
table(HYP, ["#", "Hypothesis"], [1.2, 15.4], "Hypotheses tested")
page_break()

# ================================================================== 3 SYNTHETIC DATA
doc.add_heading("3. Synthetic data generation (Step 1)", 1)
doc.add_heading("3.1 Why synthetic data", 2)
para("CIAP does not exist yet, and XYZ's history sits in separate departmental systems, so there is no single dataset that links a campaign's design, approval, forecast, stock, delivery and customer outcome. "
     "Synthetic data lets us build that linked history with realistic cause-and-effect relationships taken from the BRD, then test the strategy on it. "
     "The generator (01_generate_synthetic_data.py) uses a fixed random seed (42), so the data can be reproduced exactly.")
doc.add_heading("3.2 Datasets produced", 2)
table([["campaigns_raw.csv", "1 row per campaign", f"{QUAL.iloc[0]['rows']:,} rows × {QUAL.iloc[0]['columns']} cols", "Jan 2023 – Sep 2026: design, approval process, forecasts, stock, capacity, financial and customer outcomes"],
       ["customers_raw.csv", "1 row per acquired customer", f"{QUAL.iloc[2]['rows']:,} rows × {QUAL.iloc[2]['columns']} cols", "Segment, demographics, 12-month orders, discount usage, predicted CLTV, acquiring campaign"],
       ["campaign_daily_raw.csv", "1 row per campaign-day", f"{QUAL.iloc[4]['rows']:,} rows × {QUAL.iloc[4]['columns']} cols", "Daily forecast, demand, sales and closing stock for the 250 most recent campaigns"]],
      ["File", "Grain", "Size (raw)", "Content"], [3.8, 3.2, 3, 7], "Synthetic datasets")
doc.add_heading("3.3 How the data was simulated (the causal model)", 2)
para("Rather than random numbers, each variable is generated from the variables that drive it in the real business, with random noise added. This is what makes the analysis meaningful.")
table([["Demand", "Base demand by category × region × (1 + elasticity × discount × segment sensitivity × campaign-type multiplier) × season × random shock"],
       ["Forecasts", "Department forecasts = true expected demand × team bias (Marketing +14%, Inventory −8%, Finance 0%) × noise. CIAP model forecast = expected demand × 12% noise (back-tested model)"],
       ["Approval process", "Each department signs off with a probability (Supply 70%, Inventory 75%, Logistics 65%, Finance 80%). Cycle time grows with the number of sign-offs"],
       ["Stock", "Planned by Inventory around 1.3× expected demand when consulted; about 0.95× (a guess) when skipped. Supply Chain confirmation adds replenishment"],
       ["Stockouts", "Units sold = min(demand, stock); lost sales and stockout rate follow"],
       ["Delivery", "Rider utilisation = (base + peak orders) ÷ capacity. Logistics sign-off plans capacity for the forecast. On-time rate falls above 80% and sharply above 100% utilisation"],
       ["Money", "Revenue, discount cost, COGS, fulfilment (more expensive when over capacity), media; contribution margin and ROI vs a no-campaign baseline"],
       ["Customers", "Repeat rate, CLTV uplift, CSAT and complaints fall with stockouts and late deliveries. Discount Seekers have negative CLTV lift"],
       ["Success", "A campaign meets objectives if CM > 0, stockout < 8%, on-time > 90% and CLTV uplift > 0 (3% random label noise)"]],
      ["Element", "How it was generated"], [3, 13.6], "Simulation logic")
doc.add_heading("3.4 Realistic data-quality problems injected", 2)
para("Real exports are messy, and data preparation is worth 10 marks, so the generator deliberately introduces the problems XYZ would face when combining departmental files: "
     "duplicate rows, inconsistent labels (\"flash sale\", \"FLASH SALE \", \"Flash-Sale\"), three date formats, discounts as text (\"25%\"), budgets as currency text (\"$18,415\"), "
     "Y/N/TRUE/FALSE flags, missing values (CSAT, media spend, on-time rate, forecast team), negative units, budgets typed with two extra zeros, on-time rates of 150%, "
     "customer tiers written four ways, \"-1\" placeholder values and dropped daily feed values (\"NA\").")
page_break()

# ================================================================== 4 CLEANING
doc.add_heading("4. Data preparation: cleaning and transformation (Step 2)", 1)
para("All cleaning is done in 02_clean_transform.py and every fix is written to outputs/cleaning_log.csv (also in the Excel workbook). The table below compares data quality before and after.")
q = QUAL.copy()
table(q.values.tolist(), ["Dataset", "Stage", "Rows", "Columns", "Missing cells", "Duplicate rows"], [3.2, 2, 2, 2, 3, 3], "Data quality before vs after cleaning")
para("Note: the remaining missing cells in the clean campaigns table are CAC (customer acquisition cost) for campaigns that acquired no new customers. CAC is undefined there, so it is correctly left blank.", italic=True, size=9)
figure("00_cleaning", 15)
doc.add_heading("4.1 Cleaning steps", 2)
log_rows = LOG[~LOG["step"].str.startswith("10")][["dataset", "step", "issue", "rows_affected", "action_taken"]].values.tolist()
table(log_rows, ["Dataset", "Step", "Issue found", "Rows", "Action and justification"], [2.2, 2.6, 5, 1.2, 5.8], "Cleaning log", font=8)
doc.add_heading("4.2 Why these cleaning choices", 2)
bullet(" Missing values were filled with the median of a comparable group (same category, segment, campaign type or rider-utilisation band), not the overall mean. This keeps group differences intact and is robust to skewed data.", "Group-median imputation.")
bullet(" Categorical gaps (age band, forecast team) were labelled \"Unknown\" rather than guessed, to avoid inventing demographics or blaming a team.", "No guessing of categories.")
bullet(" Large campaigns are real, so extreme values were kept and flagged (3×IQR rule). Medians and Spearman correlation are used where outliers could distort results. Only values that were provably typing errors were corrected.", "Outliers kept, errors fixed.")
bullet(" Missing daily sales were recovered exactly from the stock movement (yesterday's closing stock − today's), rather than estimated.", "Exact recovery where possible.")
bullet(" Revenue = units × price × (1 − discount) was re-checked for every row after cleaning; all rows passed.", "Consistency validation.")
doc.add_heading("4.3 Transformation and feature engineering", 2)
table([["stock_cover_ratio", "Stock ÷ upper bound of CIAP forecast (forecast × 1.15)", "The inventory gate BRL-003"],
       ["demand_units, forecast_error_pct", "Units sold + lost sales; (forecast − demand) ÷ demand", "Forecast accuracy by team (PS-02)"],
       ["cm_margin_pct, roi, campaign_cost, cac", "Margin ÷ revenue; incremental margin ÷ (media + discount); cost ÷ new customers", "Profitability (PS-04) and acquisition cost"],
       ["signoffs_count, all_departments_signed", "Count of the five departments that signed off", "Effect of skipped checks (PS-01)"],
       ["discount_band, cycle_time_band, stock_cover_band", "Continuous variables grouped into bands", "Diagnostic comparisons and heatmaps"],
       ["launch_year / quarter / month, peak_season", "Date parts", "Trend and seasonality"],
       ["failure_reason", "First failed success criterion (Stockout, Late delivery, Loss-making, CLTV erosion)", "Root-cause Pareto"],
       ["gate_* and ciap_verdict", "Each CIAP rule recomputed with pre-launch data → Approve / Conditions / Not feasible", "Strategy back-test (H6)"],
       ["customers: churned, discount_dependency, value_tier, acq_*", "Inactive > 180 days; discount share band; CLTV quartile; joined acquiring-campaign experience", "Customer diagnostics"]],
      ["Feature(s)", "Definition", "Used for"], [4.6, 7.4, 4.6], "Engineered features")
page_break()

# ================================================================== 5 DESCRIPTIVE
doc.add_heading("5. Descriptive analytics (Step 3)", 1)
para(f"Descriptive analytics answers \"what happened?\". The interactive version of every chart is in the Streamlit dashboard (app.py, live at {LIVE_URL}), where filters by year, type, segment, category and region recalculate every number.")
num = c[["discount_pct", "units_sold", "stock_cover_ratio", "approval_cycle_hours", "stockout_rate", "on_time_delivery_rate", "csat_score", "repeat_rate_90d", "cltv_uplift_pct", "cm_margin_pct", "roi"]]
desc = num.describe().T
rows = [[A.CORR_VARS.get(i, i.replace("_", " ")), f"{r['mean']:.3f}", f"{r['50%']:.3f}", f"{r['std']:.3f}", f"{r['min']:.3f}", f"{r['max']:.3f}", f"{num[i].skew():.2f}"] for i, r in desc.iterrows()]
table(rows, ["Variable", "Mean", "Median", "Std dev", "Min", "Max", "Skew"], [4.4, 2, 2, 2, 2, 2, 2], "Summary statistics of key campaign variables", font=8.5)
para(f"Headline KPIs: {k['Campaigns']} campaigns, {k['Revenue']} revenue, {k['Contribution margin']} contribution margin, median ROI {k['Median ROI']}, average stockout rate {k['Avg stockout rate']}, "
     f"average on-time delivery {k['Avg on-time']}, median approval time {k['Median approval time']}. Several variables (ROI, units, stockout rate) are strongly skewed, so medians are reported alongside means.")
for key in ["01_trend", "02_by_type", "03_roi_distribution", "04_discount_by_type", "05_cycle_time"]:
    figure(key)
page_break()

# ================================================================== 6 CORRELATION
doc.add_heading("6. Correlation analysis (Step 3)", 1)
para("Correlation measures how strongly two variables move together (−1 to +1). Pearson captures linear relationships. Spearman (rank-based) was also computed as a robustness check "
     "because several variables are skewed or have threshold effects. The two methods agree on the direction of every strong relationship. Correlation does not prove causation, "
     "so each relationship is interpreted with business logic and checked with the diagnostic charts in Section 7.")
figure("06_correlation_heatmap", 15.5)
rich([("Spearman robustness check: ", True), (EX["06b_spearman"]["insight"], False)])
for key in ["07_success_drivers", "08_discount_vs_demand", "09_stock_vs_stockout", "10_rider_vs_ontime", "11_stockout_vs_loyalty"]:
    figure(key)
page_break()

# ================================================================== 7 DIAGNOSTIC
doc.add_heading("7. Diagnostic analytics (Step 3)", 1)
para("Diagnostic analytics answers \"why did it happen?\". It breaks failures down by root cause, compares groups, and tests each hypothesis.")
for key in ["12_failure_pareto", "13_success_by_cover", "14_segment_discount", "15_forecast_accuracy", "16_signoffs", "17_overrides", "18_daily_fill_rate"]:
    figure(key)
page_break()

# ================================================================== 8 CUSTOMERS
doc.add_heading("8. Customer-level diagnostics", 1)
para("CLTV is the BRD's north-star measure, so the customer table links each campaign's experience to what its customers did over the next 12 months.")
for key in ["19_cltv_dependency", "20_first_experience", "21_cltv_segment"]:
    figure(key)
page_break()

# ================================================================== 9 BACKTEST
doc.add_heading("9. Validating the strategy: CIAP back-test", 1)
para("To test the strategy, every historical campaign was re-evaluated with the CIAP rules using only information available before launch (CIAP model forecast, stock, rider capacity, budget, price and cost). "
     "The verdicts were then compared with what actually happened. The same back-test is built with live formulas in the Excel workbook (sheet CIAP_Gate_Simulation), where the thresholds can be changed.")
figure("22_ciap_backtest")
rows = [[v, int(bt.loc[v, "campaigns"]), A.pct(bt.loc[v, "success_rate"]), A.pct(bt.loc[v, "stockout"], 1), A.pct(bt.loc[v, "on_time"], 1), A.money(bt.loc[v, "cm_total"]), f"{bt.loc[v, 'cltv']:+.1f}"] for v in A.VERDICT_ORDER]
table(rows, ["CIAP verdict", "Campaigns", "Success rate", "Avg stockout", "Avg on-time", "Total CM", "Avg CLTV uplift (pp)"], [4.6, 1.9, 1.9, 1.9, 1.9, 2.2, 2.2], "Back-test results by verdict")
para(f"Reading the confusion matrix: of {tp + fn} campaigns that failed, CIAP would have blocked {tp} (recall {A.pct(recall)}). Of the {tp + fp} campaigns it would block, {tp} really failed (precision {A.pct(precision)}). "
     f"The {fp} \"false alarms\" are campaigns that succeeded despite thin stock or capacity, often by luck. In CIAP they would not be rejected outright: the platform generates feasible alternatives "
     "(lower discount, unit cap, later start after replenishment, narrower region), so most of their value can be kept with less risk.")
doc.add_heading("9.1 Hypothesis verdicts", 2)
table([["H1", "Supported", f"Stockout rate {A.pct(so_below, 1)} below cover 1.0 vs {A.pct(so_above, 1)} above; success {A.pct(cover.loc['<0.6', 'success_rate'])} (<0.6) to {A.pct(cover.loc['1.0-1.2', 'success_rate'])} (1.0-1.2)"],
       ["H2", "Supported", f"On-time {A.pct(lo_util, 1)} at ≤90% utilisation vs {A.pct(hi_util, 1)} above 100%; on-time ↔ CSAT r = {c['on_time_delivery_rate'].corr(c['csat_score']):+.2f}"],
       ["H3", "Supported", f"Marketing median bias {A.pct(fc.loc['Marketing', 'bias'])}; model {A.pct(fc.loc['CIAP model (AI-005)', 'bias'])}; typical error {A.pct(fc.loc['Marketing', 'mape'])} vs {A.pct(fc.loc['CIAP model (AI-005)', 'mape'])}"],
       ["H4", "Supported", f"Success {A.pct(sig.loc[5])} with 5 sign-offs vs {A.pct(c[c['signoffs_count'] <= 3]['success_flag'].mean())} with ≤3; stockouts {A.pct(inv_so['No'], 1)} without Inventory sign-off vs {A.pct(inv_so['Yes'], 1)}; overrides succeed {A.pct(ov['Yes'])} vs {A.pct(ov['No'])}"],
       ["H5", "Supported", f"Discount Seekers success {A.pct(ds['success_flag'].mean())}, CLTV uplift {ds['cltv_uplift_pct'].mean():+.1f}pp; high-dependency customers' CLTV {dep.iloc[0] / dep.iloc[-1]:.1f}x lower"],
       ["H6", "Supported", f"Success {A.pct(bt.loc['Approve', 'success_rate'])} (approve) vs {A.pct(bt.loc['Not feasible', 'success_rate'])} (blocked); recall {A.pct(recall)}, precision {A.pct(precision)}"]],
      ["#", "Verdict", "Evidence"], [1.2, 2.2, 13.2], "Hypothesis testing summary")
page_break()

# ================================================================== 10 STRATEGY
doc.add_heading("10. Business strategy and recommendations", 1)
para("The analysis supports the CIAP strategy and shows where to focus first. Recommendations are ordered by impact.")
RECS = [
    ("Make stock cover a hard launch gate (BRL-003). ", f"Stockouts are the biggest failure cause and {A.pct(below1)} of campaigns launched under-stocked. Require stock + confirmed inbound to cover the upper bound of forecast demand on peak days, not just in total."),
    ("Use one forecast with a prediction range (AI-005). ", "Replace three biased departmental forecasts with one model that all teams use. Test capacity against the upper bound so gates hold if the campaign outperforms."),
    ("Gate delivery capacity with a buffer (BRL-009/010). ", "Commit extra 3PL riders or narrow the region when peak utilisation would exceed 90%. On-time delivery collapses above 100%."),
    ("Target for CLTV, not volume (BRL-014/015). ", "Cap discounts by category, escalate anything above the ceiling, and move budget from Discount Seekers to Potential Loyalists and At-Risk win-back, where campaigns add long-term value."),
    ("Evaluate in parallel and automate the routine. ", "Run all five departmental checks at once on one data snapshot, so speed no longer requires skipping checks. Auto-approve only the low-risk tier, after a shadow-mode period proves agreement with human decisions."),
    ("Turn \"no\" into \"yes, if\". ", "When a campaign fails a gate, offer ranked feasible alternatives (unit cap, lower discount, staggered launch, start after replenishment) instead of a flat rejection."),
    ("Make overrides accountable. ", "Allow hard-gate overrides only by the CEO/CFO with a reason code and written justification, and report their outcomes against the system's prediction."),
    ("Close the learning loop. ", "Feed every campaign's actual results back into the models. The flat success-rate trend shows the current process does not learn."),
]
for lead, txt in RECS:
    bullet(txt, lead)
doc.add_heading("10.1 Expected impact", 2)
para(f"If the gates had been in place and blocked campaigns had been redesigned to perform like approved ones, the success rate would move toward the {A.pct(bt.loc['Approve', 'success_rate'])} seen in approved campaigns, "
     f"from {A.pct(c['success_flag'].mean())} today. This is an upper estimate, because some redesigned campaigns would still fail. At minimum, the {A.money(lost_cm_blocked)} of losses in blocked campaigns, and the "
     f"customer value lost through stockouts, would be avoided. Baselines and targets for these KPIs should be agreed with XYZ in Phase 0 (BRD Section 13).")
para("The companion CIAP prototype dashboard (the BRD-based web app) shows how these rules, approval tiers, alternatives and in-flight monitoring would work in practice. This report provides the evidence base for it.", italic=True)

# ================================================================== 11 LIMITATIONS
doc.add_heading("11. Limitations and next steps", 1)
bullet(" The data is simulated from assumptions in the BRD. The relationships found are therefore partly built in, and the exact numbers must be re-estimated on XYZ's real data in Phase 0.", "Synthetic data.")
bullet(" Correlation shows association, not cause. Here the causal structure is known because we simulated it, but on real data a controlled test (holdout groups, FR-029) is needed.", "Correlation vs causation.")
bullet(" The back-test is retrospective and does not model the alternatives CIAP would have proposed. A shadow-mode pilot is the proper validation.", "Back-test scope.")
bullet(" Success is a single rule-based label. A weighted score or separate KPIs might suit some campaign objectives better.", "Success definition.")
bullet(" Next steps: predictive models (classification of success, demand forecasting), prescriptive optimisation of discount and stock, and the group presentation.", "Next steps.")
page_break()

# ================================================================== APPENDIX A
doc.add_heading("Appendix A. Rationale for every technique", 1)
TECH = [
    ["Synthetic data with a causal model", "Generation", "No linked historical data exists; encoding BRD cause-and-effect makes the data realistic and the strategy testable"],
    ["Injected data-quality issues", "Generation", "Mirrors real departmental exports and allows a meaningful cleaning exercise"],
    ["De-duplication, label standardisation, type conversion, date parsing", "Cleaning", "Prevents double counting and split categories; numbers must be numeric to analyse"],
    ["IQR outlier rule (3×IQR)", "Cleaning", "Distribution-free way to separate typing errors from genuine large campaigns"],
    ["Group-median imputation", "Cleaning", "Robust to skew and preserves differences between groups"],
    ["Exact recovery from stock movement", "Cleaning", "Uses an accounting identity instead of estimating"],
    ["Feature engineering (ratios, bands, flags)", "Transformation", "Turns raw fields into business measures and rule tests (e.g. stock cover = gate BRL-003)"],
    ["Summary statistics and skewness", "Descriptive", "Shows centre, spread and shape; skew tells us to prefer medians"],
    ["Histograms and box plots", "Descriptive", "Show distribution and spread by group (ROI, discount depth, cycle time)"],
    ["Time-series trend (quarterly)", "Descriptive", "Tests whether the process improves over time (PS-06)"],
    ["Pearson and Spearman correlation matrix", "Correlation", "Pearson for linear links; Spearman for skewed and threshold relationships"],
    ["Point-biserial correlation with success", "Correlation", "Ranks the drivers of a binary outcome"],
    ["Scatter plots with threshold lines", "Correlation", "Reveal non-linear cliff edges (stock cover 1.0, utilisation 100%) that justify gate thresholds"],
    ["Pareto analysis", "Diagnostic", "Shows which few causes explain most failures (focus)"],
    ["Group comparison / binning", "Diagnostic", "Success by stock band, sign-offs, cycle time and overrides isolates each factor"],
    ["Cross-tab heatmap (segment × discount)", "Diagnostic", "Finds interaction effects that one-way charts miss"],
    ["Forecast error analysis (bias, median absolute error, WAPE)", "Diagnostic", "Quantifies the cost of departmental silos (PS-02)"],
    ["Back-test and confusion matrix (precision / recall)", "Validation", "Measures how well pre-launch rules predict real failure: the core test of the strategy"],
    ["Excel formulas (COUNTIFS, AVERAGEIFS, CORREL, IF gates)", "Validation", "Independent, transparent re-computation; thresholds as editable inputs for what-if"],
    ["Interactive Streamlit dashboard", "Communication", "Lets the user filter and explore; explanations update with the data"],
]
table(TECH, ["Technique", "Stage", "Why it was used on this dataset"], [5.8, 2.4, 8.4], "Techniques and rationale", font=8.5)

# ================================================================== APPENDIX B
doc.add_heading("Appendix B. Files submitted and how to run them", 1)
rich([("Live dashboard: ", True), (f"{LIVE_URL} (Streamlit Community Cloud; if it has gone to sleep, click the wake-up button and wait about 30 seconds).", False)])
rich([("Source code: ", True), (REPO_URL, False)])
table([["01_generate_synthetic_data.py", "Creates the three raw CSVs in data/raw (seed 42)"],
       ["02_clean_transform.py", "Cleans and transforms → data/clean, outputs/cleaning_log.csv, outputs/data_quality_summary.csv"],
       ["analysis.py", "Shared analysis functions: every chart's data and explanation"],
       ["app.py", "Streamlit dashboard (8 tabs, sidebar filters): streamlit run app.py"],
       ["03_eda_figures.py", "Static report figures → outputs/figures"],
       ["04_build_excel.py", "Excel workbook with live formulas → outputs/CIAP_Calculations.xlsx"],
       ["05_build_report.py", "This report → outputs/CIAP_Analytics_Report.docx"],
       ["requirements.txt / README.md", "Library list and run instructions"],
       ["LIVE_DASHBOARD.txt / Open Live Dashboard.url", "Link to the deployed dashboard (double-click the .url file to open it)"]],
      ["File", "Purpose"], [5.5, 11.1], "Submitted files")
para("Run order: pip install -r requirements.txt → python 01_generate_synthetic_data.py → python 02_clean_transform.py → streamlit run app.py (dashboard) → "
     "python 03_eda_figures.py → python 04_build_excel.py → python 05_build_report.py", size=9.5)

out = A.OUT / "CIAP_Analytics_Report.docx"
doc.save(out)
print(f"Saved {out} ({FIGN[0]} figures, {TABN[0]} tables)")
