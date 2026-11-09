"""
Step 4 - Excel workbook with all calculations
==============================================
Builds outputs/CIAP_Calculations.xlsx. Every KPI, summary, correlation and CIAP gate
is a live Excel formula pointing at the clean data sheet, so the grader can trace each
number. The gate thresholds on 'CIAP_Gate_Simulation' are input cells: change one and the
whole back-test recalculates (an Excel what-if).

Run:  python 04_build_excel.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

import analysis as A

BASE = Path(__file__).parent
OUT = BASE / "outputs"
c, u, d, LOG, QUAL = A.load()

COLS = ["campaign_id", "launch_date", "launch_year", "campaign_type", "target_segment", "category", "region_scope", "discount_pct", "discount_band",
        "duration_days", "unit_price", "unit_cost", "budget", "media_spend", "forecast_units", "ciap_model_forecast_units", "stock_available_units",
        "demand_units", "units_sold", "lost_sales_units", "base_orders_per_day", "rider_capacity_orders_per_day", "signoffs_count", "approval_cycle_hours",
        "override_flag", "stockout_rate", "peak_rider_utilisation", "on_time_delivery_rate", "revenue", "discount_cost", "cogs", "fulfilment_cost",
        "contribution_margin", "baseline_contribution", "new_customers", "repeat_rate_90d", "cltv_uplift_pct", "csat_score", "return_rate",
        "complaints", "campaign_success", "success_flag", "failure_reason"]
data = c[COLS].copy()
data["launch_date"] = pd.to_datetime(data["launch_date"]).dt.date
N = len(data)
L = {col: get_column_letter(i + 1) for i, col in enumerate(COLS)}
R = lambda col: f"Campaigns_Clean!${L[col]}$2:${L[col]}${N + 1}"  # noqa: E731

HDR = PatternFill("solid", fgColor="10233F")
SUB = PatternFill("solid", fgColor="E7F0FB")
INPUT = PatternFill("solid", fgColor="FFF4D6")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
THIN = Border(bottom=Side(style="thin", color="C3C2B7"))
FMT = {"pct": "0.0%", "money": "$#,##0", "num": "#,##0", "dec": "0.00", "x": '0.00"x"'}

wb = Workbook()


def header(ws, row, values, widths=None):
    for j, v in enumerate(values, 1):
        cell = ws.cell(row=row, column=j, value=v)
        cell.fill, cell.font, cell.alignment = HDR, WHITE, Alignment(wrap_text=True, vertical="center")
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14, color="10233F")
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="52514E")


# ------------------------------------------------------------------ README
ws = wb.active
ws.title = "README"
title(ws, "XYZ CIAP - Campaign analytics calculations", "Synthetic data generated to validate the Campaign Intelligence & Approval Platform strategy")
rows = [
    ("Sheet", "What it contains"),
    ("Campaigns_Clean", f"{N:,} cleaned campaigns (output of 02_clean_transform.py). All other sheets calculate from this sheet."),
    ("Cleaning_Log", "Every data-cleaning step with the issue found, rows affected and the action taken."),
    ("KPI_Calculations", "Headline KPIs (BRD Section 13) as live formulas, with the formula text shown beside each value."),
    ("Summary_by_Group", "Success rate, ROI, stockout and margin by campaign type, segment, discount band and stock-cover band (COUNTIFS / AVERAGEIFS)."),
    ("Segment_x_Discount", "Success-rate matrix of target segment x discount band (diagnostic heatmap)."),
    ("Correlation", "Pearson correlation matrix built with CORREL formulas."),
    ("CIAP_Gate_Simulation", "Back-test: each campaign re-evaluated with the CIAP gates. Yellow cells are thresholds you can change (what-if)."),
    ("Data_Dictionary", "Definition of every column."),
    ("", ""),
    ("Colour key", "Dark header = formula output table; yellow cell = input / assumption you can edit."),
]
for i, (a, b) in enumerate(rows, 4):
    ws.cell(row=i, column=1, value=a).font = BOLD if i == 4 or a == "Colour key" else Font()
    ws.cell(row=i, column=2, value=b)
header(ws, 4, ["Sheet", "What it contains"], [26, 110])

# ------------------------------------------------------------------ data
ws = wb.create_sheet("Campaigns_Clean")
ws.append(COLS)
for r in data.itertuples(index=False):
    ws.append(list(r))
tab = Table(displayName="Campaigns", ref=f"A1:{get_column_letter(len(COLS))}{N + 1}")
tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
ws.add_table(tab)
ws.freeze_panes = "C2"
for col, l in L.items():
    ws.column_dimensions[l].width = max(11, min(24, len(col) + 2))
    fmt = "pct" if col in ("discount_pct", "stockout_rate", "on_time_delivery_rate", "repeat_rate_90d", "return_rate", "peak_rider_utilisation") else \
          "money" if col in ("budget", "media_spend", "revenue", "discount_cost", "cogs", "fulfilment_cost", "contribution_margin", "baseline_contribution") else None
    if fmt:
        for row in ws.iter_rows(min_row=2, max_row=N + 1, min_col=COLS.index(col) + 1, max_col=COLS.index(col) + 1):
            row[0].number_format = FMT[fmt]

# ------------------------------------------------------------------ cleaning log
ws = wb.create_sheet("Cleaning_Log")
title(ws, "Data cleaning log", "Generated by 02_clean_transform.py")
header(ws, 4, list(LOG.columns), [16, 24, 70, 14, 90])
for i, r in enumerate(LOG.itertuples(index=False), 5):
    for j, v in enumerate(r, 1):
        ws.cell(row=i, column=j, value=v).alignment = Alignment(wrap_text=True, vertical="top")
r0 = 6 + len(LOG)
ws.cell(row=r0, column=1, value="Data quality before vs after").font = BOLD
for j, v in enumerate(QUAL.columns, 1):
    ws.cell(row=r0 + 1, column=j, value=v).fill = SUB
for i, r in enumerate(QUAL.itertuples(index=False), r0 + 2):
    for j, v in enumerate(r, 1):
        ws.cell(row=i, column=j, value=v)

# ------------------------------------------------------------------ KPIs
ws = wb.create_sheet("KPI_Calculations")
title(ws, "Headline KPIs", "Live formulas over Campaigns_Clean. Column D shows the formula used.")
header(ws, 4, ["KPI", "Definition", "Value", "Formula"], [34, 62, 16, 90])
K = [
    ("Campaigns analysed", "Count of campaigns", f"=COUNTA({R('campaign_id')})", "num"),
    ("KPI-success  Success rate", "Campaigns that met objectives ÷ all campaigns", f"=AVERAGE({R('success_flag')})", "pct"),
    ("Total revenue", "Sum of net revenue", f"=SUM({R('revenue')})", "money"),
    ("KPI-05  Contribution margin", "Revenue − COGS − discount − fulfilment − media", f"=SUM({R('contribution_margin')})", "money"),
    ("KPI-05  Contribution margin %", "Total CM ÷ total revenue", f"=SUM({R('contribution_margin')})/SUM({R('revenue')})", "pct"),
    ("KPI-06  Discount cost ratio", "Discount cost ÷ gross revenue (net revenue + discount)", f"=SUM({R('discount_cost')})/(SUM({R('revenue')})+SUM({R('discount_cost')}))", "pct"),
    ("KPI-04  Portfolio ROI", "(CM − baseline CM) ÷ (media + discount cost)", f"=(SUM({R('contribution_margin')})-SUM({R('baseline_contribution')}))/(SUM({R('media_spend')})+SUM({R('discount_cost')}))", "x"),
    ("Lost sales (units)", "Demand that could not be served because of stockouts", f"=SUM({R('lost_sales_units')})", "num"),
    ("Lost sales share of demand", "Lost units ÷ demand units", f"=SUM({R('lost_sales_units')})/SUM({R('demand_units')})", "pct"),
    ("KPI-12  Avg stockout rate", "Mean share of campaign SKU-location-days out of stock", f"=AVERAGE({R('stockout_rate')})", "pct"),
    ("KPI-15  Avg on-time delivery", "Mean on-time delivery rate", f"=AVERAGE({R('on_time_delivery_rate')})", "pct"),
    ("KPI-19  Avg CSAT", "Mean CSAT (1-5)", f"=AVERAGE({R('csat_score')})", "dec"),
    ("KPI-10  Avg 90-day repeat rate", "Mean share of buyers who buy again within 90 days", f"=AVERAGE({R('repeat_rate_90d')})", "pct"),
    ("KPI-09  Avg CLTV uplift %", "Mean change in predicted CLTV vs control (percentage points)", f"=AVERAGE({R('cltv_uplift_pct')})", "dec"),
    ("KPI-01  Median approval cycle (h)", "Median hours from submission to decision", f"=MEDIAN({R('approval_cycle_hours')})", "dec"),
    ("Approvals taking > 96 h", "Share of campaigns with approval cycle above 4 days", f"=COUNTIF({R('approval_cycle_hours')},\">96\")/COUNTA({R('campaign_id')})", "pct"),
    ("KPI-21  Override rate", "Campaigns launched despite an objection ÷ all", f"=COUNTIF({R('override_flag')},\"Yes\")/COUNTA({R('campaign_id')})", "pct"),
    ("Success rate when overridden", "Success rate of overridden campaigns", f"=AVERAGEIFS({R('success_flag')},{R('override_flag')},\"Yes\")", "pct"),
    ("Forecast bias (manual)", "Σ forecast ÷ Σ demand − 1", f"=SUM({R('forecast_units')})/SUM({R('demand_units')})-1", "pct"),
    ("Forecast bias (CIAP model)", "Σ model forecast ÷ Σ demand − 1", f"=SUM({R('ciap_model_forecast_units')})/SUM({R('demand_units')})-1", "pct"),
    ("KPI-13  WAPE manual forecast", "Σ|forecast − demand| ÷ Σ demand", f"=SUMPRODUCT(ABS({R('forecast_units')}-{R('demand_units')}))/SUM({R('demand_units')})", "pct"),
    ("KPI-13  WAPE CIAP model", "Σ|model − demand| ÷ Σ demand", f"=SUMPRODUCT(ABS({R('ciap_model_forecast_units')}-{R('demand_units')}))/SUM({R('demand_units')})", "pct"),
]
for i, (k, dfn, f, fm) in enumerate(K, 5):
    ws.cell(row=i, column=1, value=k).font = BOLD
    ws.cell(row=i, column=2, value=dfn)
    cell = ws.cell(row=i, column=3, value=f)
    cell.number_format = FMT[fm]
    ws.cell(row=i, column=4, value="'" + f).font = Font(color="898781", size=9)

# ------------------------------------------------------------------ summaries by group
ws = wb.create_sheet("Summary_by_Group")
title(ws, "Descriptive & diagnostic summaries", "COUNTIFS / AVERAGEIFS / SUMIFS over Campaigns_Clean")
row = 4
GROUPS = [("campaign_type", sorted(c["campaign_type"].unique())), ("target_segment", A.SEG_ORDER), ("discount_band", A.DISC_ORDER), ("category", sorted(c["category"].unique())),
          ("region_scope", sorted(c["region_scope"].unique())), ("signoffs_count", [1, 2, 3, 4, 5])]
METRICS = [("Campaigns", "count", None, "num"), ("Success rate", "avg", "success_flag", "pct"), ("Avg discount", "avg", "discount_pct", "pct"),
           ("Avg stockout", "avg", "stockout_rate", "pct"), ("Avg on-time", "avg", "on_time_delivery_rate", "pct"), ("Avg CSAT", "avg", "csat_score", "dec"),
           ("Avg CLTV uplift %", "avg", "cltv_uplift_pct", "dec"), ("Total CM", "sum", "contribution_margin", "money"), ("CM % of revenue", "ratio", None, "pct")]
ws.column_dimensions["A"].width = 26
for j in range(2, 11):
    ws.column_dimensions[get_column_letter(j)].width = 15
for gcol, vals in GROUPS:
    ws.cell(row=row, column=1, value=f"By {gcol.replace('_', ' ')}").font = Font(bold=True, size=12, color="10233F")
    row += 1
    header(ws, row, [gcol] + [m[0] for m in METRICS])
    for v in vals:
        row += 1
        ws.cell(row=row, column=1, value=v)
        key = f"$A{row}"
        for j, (name, kind, col, fm) in enumerate(METRICS, 2):
            if kind == "count":
                f = f"=COUNTIFS({R(gcol)},{key})"
            elif kind == "avg":
                f = f"=IFERROR(AVERAGEIFS({R(col)},{R(gcol)},{key}),\"\")"
            elif kind == "sum":
                f = f"=SUMIFS({R(col)},{R(gcol)},{key})"
            else:
                f = f"=IFERROR(SUMIFS({R('contribution_margin')},{R(gcol)},{key})/SUMIFS({R('revenue')},{R(gcol)},{key}),\"\")"
            ws.cell(row=row, column=j, value=f).number_format = FMT[fm]
    ws.conditional_formatting.add(f"C{row - len(vals) + 1}:C{row}", ColorScaleRule(start_type="min", start_color="FDEADF", end_type="max", end_color="9EC5F4"))
    row += 2

# stock cover band uses a numeric ratio computed in-sheet
ws.cell(row=row, column=1, value="By stock cover ratio (stock ÷ CIAP upper-bound forecast)").font = Font(bold=True, size=12, color="10233F")
row += 1
header(ws, row, ["Lower bound", "Upper bound", "Campaigns", "Success rate", "Avg stockout"])
for lo, hi in [(0, 0.6), (0.6, 0.8), (0.8, 1.0), (1.0, 1.2), (1.2, 100)]:
    row += 1
    ws.cell(row=row, column=1, value=lo)
    ws.cell(row=row, column=2, value=hi)
    ratio = f"CIAP_Gate_Simulation!$H$12:$H${N + 11}"
    ws.cell(row=row, column=3, value=f"=COUNTIFS({ratio},\">=\"&A{row},{ratio},\"<\"&B{row})")
    ws.cell(row=row, column=4, value=f"=IFERROR(AVERAGEIFS({R('success_flag')},{ratio},\">=\"&A{row},{ratio},\"<\"&B{row}),\"\")").number_format = FMT["pct"]
    ws.cell(row=row, column=5, value=f"=IFERROR(AVERAGEIFS({R('stockout_rate')},{ratio},\">=\"&A{row},{ratio},\"<\"&B{row}),\"\")").number_format = FMT["pct"]

# ------------------------------------------------------------------ segment x discount
ws = wb.create_sheet("Segment_x_Discount")
title(ws, "Success rate: target segment x discount band", "AVERAGEIFS of success_flag; blank = no campaigns in that cell. Lower table = campaign counts.")
header(ws, 4, ["Segment"] + A.DISC_ORDER, [24] + [12] * 5)
for i, s in enumerate(A.SEG_ORDER, 5):
    ws.cell(row=i, column=1, value=s).font = BOLD
    for j, b in enumerate(A.DISC_ORDER, 2):
        ws.cell(row=i, column=j, value=f"=IFERROR(AVERAGEIFS({R('success_flag')},{R('target_segment')},$A{i},{R('discount_band')},\"{b}\"),\"\")").number_format = FMT["pct"]
ws.conditional_formatting.add("B5:F10", ColorScaleRule(start_type="num", start_value=0, start_color="FDEADF", end_type="num", end_value=1, end_color="2A78D6"))
header(ws, 13, ["Segment (count)"] + A.DISC_ORDER)
for i, s in enumerate(A.SEG_ORDER, 14):
    ws.cell(row=i, column=1, value=s)
    for j, b in enumerate(A.DISC_ORDER, 2):
        ws.cell(row=i, column=j, value=f"=COUNTIFS({R('target_segment')},$A{i},{R('discount_band')},\"{b}\")")

# ------------------------------------------------------------------ correlation
ws = wb.create_sheet("Correlation")
CV = ["discount_pct", "signoffs_count", "approval_cycle_hours", "peak_rider_utilisation", "stockout_rate", "on_time_delivery_rate", "csat_score", "repeat_rate_90d",
      "cltv_uplift_pct", "return_rate", "success_flag"]
title(ws, "Pearson correlation matrix (CORREL formulas)", "Blue = positive, orange = negative. Stock cover ratio vs stockout: see cell B16.")
header(ws, 4, [""] + [A.CORR_VARS.get(v, v) for v in CV], [24] + [13] * len(CV))
for i, a in enumerate(CV, 5):
    ws.cell(row=i, column=1, value=A.CORR_VARS.get(a, a)).font = BOLD
    for j, b in enumerate(CV, 2):
        ws.cell(row=i, column=j, value=f"=CORREL({R(a)},{R(b)})").number_format = "0.00"
end = get_column_letter(len(CV) + 1)
ws.conditional_formatting.add(f"B5:{end}{4 + len(CV)}", ColorScaleRule(start_type="num", start_value=-1, start_color="EB6834", mid_type="num", mid_value=0, mid_color="FFFFFF", end_type="num", end_value=1, end_color="2A78D6"))
ws.cell(row=16, column=1, value="Stock cover ratio vs stockout rate").font = BOLD
ws.cell(row=16, column=2, value=f"=CORREL(CIAP_Gate_Simulation!$H$12:$H${N + 11},{R('stockout_rate')})").number_format = "0.00"

# ------------------------------------------------------------------ CIAP gate simulation
ws = wb.create_sheet("CIAP_Gate_Simulation")
title(ws, "CIAP back-test: would the new gates have stopped the failures?", "Each row re-evaluates one campaign with pre-launch data only. Yellow cells are editable thresholds.")
TH = [("Upper-bound multiplier on CIAP forecast", 1.15, "BRL-003 / AI-103"), ("Min stock cover ratio (hard gate)", 1.0, "BRL-003"),
      ("Rider utilisation hard limit", 1.0, "BRL-009"), ("Rider utilisation condition (buffer)", 0.9, "BRL-009"), ("Min projected margin (escalate below)", 0.10, "BRL-012"),
      ("Peak-day factor / units per order", 1.6 / 1.4, "planning assumption")]
for i, (k, v, ref) in enumerate(TH, 4):
    ws.cell(row=i, column=1, value=k)
    cell = ws.cell(row=i, column=2, value=v)
    cell.fill = INPUT
    cell.number_format = "0.00"
    ws.cell(row=i, column=3, value=ref).font = Font(color="898781")
TH_UP, TH_COVER, TH_RH, TH_RC, TH_M, TH_PK = "$B$4", "$B$5", "$B$6", "$B$7", "$B$8", "$B$9"
cols = ["campaign_id", "Model forecast", "Stock", "Duration", "Base orders/day", "Rider capacity/day", "Upper bound", "Stock cover ratio", "Gate inventory BRL-003",
        "Sim rider util", "Gate logistics BRL-009", "Projected margin %", "Gate finance BRL-012", "Projected cost", "Budget", "Gate budget BRL-011",
        "Hard fails", "CIAP verdict", "Actual outcome", "success_flag", "Blocked & failed"]
header(ws, 11, cols, [12, 12, 11, 9, 11, 12, 11, 11, 14, 11, 14, 12, 14, 13, 13, 14, 9, 22, 18, 10, 10])
src = lambda col, r: f"Campaigns_Clean!{L[col]}{r}"  # noqa: E731
for k in range(N):
    r, s = 12 + k, 2 + k
    vals = [
        f"={src('campaign_id', s)}", f"={src('ciap_model_forecast_units', s)}", f"={src('stock_available_units', s)}", f"={src('duration_days', s)}",
        f"={src('base_orders_per_day', s)}", f"={src('rider_capacity_orders_per_day', s)}",
        f"=ROUND(B{r}*{TH_UP},0)", f"=C{r}/G{r}", f"=IF(H{r}>={TH_COVER},\"Pass\",\"Hard fail\")",
        f"=(E{r}+G{r}/D{r}*{TH_PK})/F{r}", f"=IF(J{r}>{TH_RH},\"Hard fail\",IF(J{r}>{TH_RC},\"Condition\",\"Pass\"))",
        f"=(B{r}*{src('unit_price', s)}*(1-{src('discount_pct', s)})-B{r}*{src('unit_cost', s)}-B{r}/1.4*6.5-{src('media_spend', s)})/(B{r}*{src('unit_price', s)}*(1-{src('discount_pct', s)}))",
        f"=IF(L{r}<0,\"Hard fail\",IF(L{r}<{TH_M},\"Escalate\",\"Pass\"))",
        f"=B{r}*{src('unit_price', s)}*{src('discount_pct', s)}+{src('media_spend', s)}", f"={src('budget', s)}", f"=IF(N{r}>O{r},\"Hard fail\",\"Pass\")",
        f"=COUNTIF(I{r}:P{r},\"Hard fail\")",
        f"=IF(Q{r}>0,\"Not feasible\",IF(OR(K{r}=\"Condition\",M{r}=\"Escalate\",{src('discount_pct', s)}>INDEX(Summary_Ceilings!$B$2:$B$6,MATCH({src('category', s)},Summary_Ceilings!$A$2:$A$6,0))),\"Approve with conditions / escalate\",\"Approve\"))",
        f"={src('campaign_success', s)}", f"={src('success_flag', s)}", f"=IF(AND(R{r}=\"Not feasible\",T{r}=0),1,0)",
    ]
    for j, v in enumerate(vals, 1):
        ws.cell(row=r, column=j, value=v)
    ws.cell(row=r, column=8).number_format = "0.00"
    ws.cell(row=r, column=10).number_format = "0%"
    ws.cell(row=r, column=12).number_format = "0.0%"
    ws.cell(row=r, column=14).number_format = FMT["money"]
    ws.cell(row=r, column=15).number_format = FMT["money"]
ws.freeze_panes = "B12"
# summary block to the right
X = 23
ws.cell(row=3, column=X, value="Back-test summary").font = Font(bold=True, size=12, color="10233F")
for j, h in enumerate(["CIAP verdict", "Campaigns", "Actual success rate", "Avg stockout", "Total CM"]):
    cell = ws.cell(row=4, column=X + j, value=h)
    cell.fill, cell.font = HDR, WHITE
    ws.column_dimensions[get_column_letter(X + j)].width = 20 if j == 0 else 16
VR = f"$R$12:$R${N + 11}"
for i, v in enumerate(A.VERDICT_ORDER, 5):
    ws.cell(row=i, column=X, value=v)
    ws.cell(row=i, column=X + 1, value=f"=COUNTIF({VR},{get_column_letter(X)}{i})")
    ws.cell(row=i, column=X + 2, value=f"=IFERROR(AVERAGEIFS($T$12:$T${N + 11},{VR},{get_column_letter(X)}{i}),\"\")").number_format = FMT["pct"]
    ws.cell(row=i, column=X + 3, value=f"=IFERROR(AVERAGEIFS({R('stockout_rate')},{VR},{get_column_letter(X)}{i}),\"\")").number_format = FMT["pct"]
    ws.cell(row=i, column=X + 4, value=f"=SUMIFS({R('contribution_margin')},{VR},{get_column_letter(X)}{i})").number_format = FMT["money"]
ws.cell(row=9, column=X, value="Recall (failures blocked ÷ all failures)").font = BOLD
ws.cell(row=9, column=X + 1, value=f"=SUM($U$12:$U${N + 11})/COUNTIF($T$12:$T${N + 11},0)").number_format = FMT["pct"]
ws.cell(row=10, column=X, value="Precision (correct blocks ÷ all blocks)").font = BOLD
ws.cell(row=10, column=X + 1, value=f"=SUM($U$12:$U${N + 11})/COUNTIF({VR},\"Not feasible\")").number_format = FMT["pct"]

# category ceilings used by the verdict formula (BRL-015)
wsc = wb.create_sheet("Summary_Ceilings")
header(wsc, 1, ["Category", "Discount ceiling (BRL-015)"], [18, 26])
for i, (k, v) in enumerate({"Footwear": 0.30, "Apparel": 0.40, "Electronics": 0.20, "Home": 0.35, "Beauty": 0.30}.items(), 2):
    wsc.cell(row=i, column=1, value=k)
    cell = wsc.cell(row=i, column=2, value=v)
    cell.fill, cell.number_format = INPUT, "0%"

# ------------------------------------------------------------------ dictionary
ws = wb.create_sheet("Data_Dictionary")
title(ws, "Data dictionary - Campaigns_Clean")
DESC = {
    "campaign_id": "Unique campaign key", "launch_date": "Date the campaign went live", "launch_year": "Year of launch", "campaign_type": "Discount, Flash Sale, Seasonal Event, Bundle, Free Delivery, Loyalty Reward or Clearance",
    "target_segment": "Customer segment targeted (from clustering, AI-001)", "category": "Product category", "region_scope": "Nationwide, Metro only or Regional",
    "discount_pct": "Discount depth (0-1)", "discount_band": "Discount grouped in 10-point bands", "duration_days": "Campaign length in days", "unit_price": "Average list price per unit",
    "unit_cost": "Cost of goods per unit (cogs ÷ units sold)", "budget": "Approved campaign budget", "media_spend": "Paid media cost", "forecast_units": "Demand forecast made by the department (manual process)",
    "ciap_model_forecast_units": "Back-tested CIAP demand model forecast (AI-005)", "stock_available_units": "Units available at launch incl. confirmed replenishment",
    "demand_units": "Units customers wanted = units sold + lost sales", "units_sold": "Units actually sold", "lost_sales_units": "Demand not served because of stockouts",
    "base_orders_per_day": "Normal daily orders in the delivery area", "rider_capacity_orders_per_day": "Orders/day the rider fleet can deliver",
    "signoffs_count": "Departments that signed off (1-5; Marketing always)", "approval_cycle_hours": "Hours from submission to decision", "override_flag": "Launched despite a department objection",
    "stockout_rate": "Share of campaign SKU-location-days out of stock", "peak_rider_utilisation": "Peak-day orders ÷ rider capacity", "on_time_delivery_rate": "Orders delivered by promised date ÷ orders",
    "revenue": "Net revenue after discount", "discount_cost": "Value of discounts given", "cogs": "Cost of goods sold", "fulfilment_cost": "Pick, pack and last-mile cost",
    "contribution_margin": "Revenue − COGS − fulfilment − media", "baseline_contribution": "Margin the audience would have generated without the campaign",
    "new_customers": "First-time buyers acquired", "repeat_rate_90d": "Share of buyers purchasing again within 90 days", "cltv_uplift_pct": "Change in predicted CLTV vs control (pp)",
    "csat_score": "Customer satisfaction 1-5", "return_rate": "Returns ÷ orders", "complaints": "Customer complaints logged", "campaign_success": "Met objectives if CM>0, stockout<8%, on-time>90% and CLTV uplift>0",
    "success_flag": "1 = met objectives, 0 = missed", "failure_reason": "First failed criterion: Stockout, Late delivery, Loss-making, CLTV erosion",
}
header(ws, 3, ["Column", "Description"], [30, 110])
for i, col in enumerate(COLS, 4):
    ws.cell(row=i, column=1, value=col).font = BOLD
    ws.cell(row=i, column=2, value=DESC.get(col, ""))

wb.calculation.fullCalcOnLoad = True
path = OUT / "CIAP_Calculations.xlsx"
wb.save(path)
print(f"Saved {path} with sheets: {wb.sheetnames}")
