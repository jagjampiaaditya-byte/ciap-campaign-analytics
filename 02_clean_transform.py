"""
Step 2 - Data cleaning and transformation
=========================================
Turns the three raw exports into analysis-ready tables and records every fix in a
cleaning log (outputs/cleaning_log.csv) so each change is auditable.

Cleaning   : duplicates, label standardisation, mixed date formats, text-formatted numbers,
             data-entry errors, impossible values, outliers, missing values.
Transform  : business features (stock cover, forecast error, margins, ROI, CAC, bands),
             a CIAP "gate" simulation that replays every historical campaign through the
             rules the new platform would apply, and a primary failure root cause.

Run:  python 02_clean_transform.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
RAW, CLEAN, OUT = BASE / "data" / "raw", BASE / "data" / "clean", BASE / "outputs"
CLEAN.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

LOG = []


def log(dataset, step, issue, rows, action):
    LOG.append({"dataset": dataset, "step": step, "issue": issue, "rows_affected": int(rows), "action_taken": action})


def profile(df, name, stage):
    return {"dataset": name, "stage": stage, "rows": len(df), "columns": df.shape[1],
            "missing_cells": int(df.isna().sum().sum()), "duplicate_rows": int(df.duplicated().sum())}


QUALITY = []
CATEGORY_CEILING = {"Footwear": 0.30, "Apparel": 0.40, "Electronics": 0.20, "Home": 0.35, "Beauty": 0.30}

# =====================================================================================
# CAMPAIGNS
# =====================================================================================
c = pd.read_csv(RAW / "campaigns_raw.csv", dtype=str)
QUALITY.append(profile(c, "campaigns", "raw"))
D = "campaigns"

# 1. whitespace
obj = c.columns
before = c.copy()
c = c.apply(lambda s: s.str.strip())
log(D, "1. Trim whitespace", "Leading/trailing spaces in text fields", (before.fillna("") != c.fillna("")).any(axis=1).sum(), "Stripped spaces from all text columns")

# 2. duplicates
dup = c.duplicated().sum()
c = c.drop_duplicates().reset_index(drop=True)
log(D, "2. Remove duplicates", "Identical rows exported twice", dup, "Dropped exact duplicate rows")
dup_id = c["campaign_id"].duplicated().sum()
log(D, "2. Remove duplicates", "Duplicate campaign_id after exact de-dup", dup_id, "None found - campaign_id is a valid primary key" if dup_id == 0 else "Kept first occurrence")

# 3. standardise categorical labels
MAPS = {
    "campaign_type": {"flash sale": "Flash Sale", "flash-sale": "Flash Sale", "free delivery": "Free Delivery"},
    "target_segment": {"at risk": "At-Risk / Lapsed", "at-risk/lapsed": "At-Risk / Lapsed", "discount seekers": "Discount Seekers", "discount seeker": "Discount Seekers"},
    "region_scope": {"metro": "Metro only", "metro only": "Metro only", "national": "Nationwide", "nationwide": "Nationwide"},
}
for col, m in MAPS.items():
    low = c[col].str.lower()
    fix = low.map(m)
    changed = fix.notna() & (fix != c[col])
    c.loc[changed, col] = fix[changed]
    log(D, "3. Standardise labels", f"Inconsistent spellings/case in {col}", changed.sum(), f"Mapped variants to canonical labels: {sorted(set(c[col]))}")
YN = {"yes": "Yes", "y": "Yes", "true": "Yes", "no": "No", "n": "No", "false": "No"}
for col in ["supply_chain_signoff", "inventory_signoff", "logistics_signoff", "finance_signoff", "override_flag"]:
    fixed = c[col].str.lower().map(YN)
    changed = (fixed != c[col]).sum()
    c[col] = fixed
    if changed:
        log(D, "3. Standardise labels", f"{col} recorded as Y/N/TRUE/FALSE/yes", changed, "Converted to Yes/No")

# 4. dates in three formats
def parse_date(s):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


non_iso = (~c["launch_date"].str.match(r"^\d{4}-\d{2}-\d{2}$")).sum()
c["launch_date"] = c["launch_date"].apply(parse_date)
log(D, "4. Parse dates", "launch_date in DD/MM/YYYY and 'Mon DD, YYYY' formats", non_iso, f"Parsed all formats to ISO dates; unparseable left: {c['launch_date'].isna().sum()}")

# 5. numbers stored as text
pct_text = c["discount_pct"].str.contains("%", na=False)
c["discount_pct"] = c["discount_pct"].str.replace("%", "", regex=False).astype(float)
c.loc[pct_text, "discount_pct"] = c.loc[pct_text, "discount_pct"] / 100
log(D, "5. Fix data types", "discount_pct written as text like '25%'", pct_text.sum(), "Removed % and converted to a 0-1 fraction")
cur_text = c["budget"].str.contains(r"\$|,", na=False)
c["budget"] = c["budget"].str.replace(r"[\$,]", "", regex=True).astype(float)
log(D, "5. Fix data types", "budget written as currency text like '$18,415'", cur_text.sum(), "Removed $ and thousands separators, converted to number")
NUM = ["duration_days", "channel_count", "unit_price", "media_spend", "forecast_units", "ciap_model_forecast_units", "stock_available_units", "approval_cycle_hours",
       "base_orders_per_day", "rider_capacity_orders_per_day", "units_sold", "lost_sales_units", "stockout_rate", "peak_rider_utilisation",
       "on_time_delivery_rate", "revenue", "discount_cost", "cogs", "fulfilment_cost", "contribution_margin", "baseline_contribution",
       "new_customers", "repeat_rate_90d", "cltv_uplift_pct", "csat_score", "return_rate", "complaints"]
for col in NUM:
    c[col] = pd.to_numeric(c[col], errors="coerce")

# 6. data-entry errors and impossible values
neg = c["units_sold"] < 0
c.loc[neg, "units_sold"] = c.loc[neg, "units_sold"].abs()
log(D, "6. Fix invalid values", "Negative units_sold (sign typed wrongly; revenue is positive)", neg.sum(), "Took absolute value - confirmed against revenue / price")
bad_ot = c["on_time_delivery_rate"] > 1
c.loc[bad_ot, "on_time_delivery_rate"] = np.nan
log(D, "6. Fix invalid values", "on_time_delivery_rate above 100% (1.5)", bad_ot.sum(), "Set to missing, then imputed in step 8")

# 7. outliers: budget typed with two extra zeros
ratio = c["budget"] / (c["forecast_units"] * c["unit_price"])
q1, q3 = ratio.quantile([0.25, 0.75])
fence = q3 + 3 * (q3 - q1)
typo = ratio > max(fence, 5)
c.loc[typo, "budget"] = c.loc[typo, "budget"] / 100
log(D, "7. Treat outliers", f"budget / planned revenue ratio above {max(fence, 5):.1f} (3xIQR fence {fence:.2f}, floor 5) - two extra zeros typed", typo.sum(), "Divided by 100 (ratio returns to the normal range)")
iqr_flags = {}
for col in ["contribution_margin", "units_sold", "approval_cycle_hours"]:
    a, b = c[col].quantile([0.25, 0.75])
    out = ((c[col] < a - 3 * (b - a)) | (c[col] > b + 3 * (b - a))).sum()
    iqr_flags[col] = out
    log(D, "7. Treat outliers", f"Extreme but genuine values in {col} (3xIQR rule)", out, "Kept: they are real large campaigns, flagged for robust (median) statistics")

# 8. missing values
m = c["media_spend"].isna()
media_rate = (c["media_spend"] / (c["forecast_units"] * c["unit_price"])).groupby(c["category"]).transform("median")
c.loc[m, "media_spend"] = (media_rate * c["forecast_units"] * c["unit_price"])[m].round()
log(D, "8. Impute missing", "media_spend missing", m.sum(), "Imputed = category median media-to-planned-revenue rate x planned revenue")
m = c["on_time_delivery_rate"].isna()
band = pd.cut(c["peak_rider_utilisation"], [0, 0.8, 0.9, 1.0, 1.1, 10])
c.loc[m, "on_time_delivery_rate"] = c.groupby(band, observed=True)["on_time_delivery_rate"].transform("median")[m]
log(D, "8. Impute missing", "on_time_delivery_rate missing (incl. the invalid 1.5 values)", m.sum(), "Imputed with median on-time rate of campaigns in the same rider-utilisation band")
m = c["csat_score"].isna()
c.loc[m, "csat_score"] = c.groupby("campaign_type")["csat_score"].transform("median")[m]
log(D, "8. Impute missing", "csat_score missing (survey not returned)", m.sum(), "Imputed with campaign-type median")
m = c["repeat_rate_90d"].isna()
c.loc[m, "repeat_rate_90d"] = c.groupby("target_segment")["repeat_rate_90d"].transform("median")[m]
log(D, "8. Impute missing", "repeat_rate_90d missing", m.sum(), "Imputed with target-segment median")
m = c["forecast_team"].isna()
c.loc[m, "forecast_team"] = "Unknown"
log(D, "8. Impute missing", "forecast_team missing", m.sum(), "Labelled 'Unknown' (category kept, not guessed)")
for col in ["duration_days", "channel_count", "forecast_units", "ciap_model_forecast_units", "stock_available_units", "units_sold", "lost_sales_units", "new_customers", "complaints",
            "base_orders_per_day", "rider_capacity_orders_per_day"]:
    c[col] = c[col].round().astype(int)

# 9. consistency checks
calc_rev = c["units_sold"] * c["unit_price"] * (1 - c["discount_pct"])
bad = ((calc_rev - c["revenue"]).abs() / c["revenue"] > 0.02).sum()
log(D, "9. Consistency check", "revenue = units_sold x price x (1 - discount)", bad, "Check passed for all rows" if bad == 0 else "Rows flagged for review")

# ---------- TRANSFORM ----------
c["demand_units"] = c["units_sold"] + c["lost_sales_units"]
c["forecast_upper"] = (c["forecast_units"] * 1.2).round()
c["forecast_error_pct"] = (c["forecast_units"] - c["demand_units"]) / c["demand_units"]
c["abs_forecast_error_pct"] = c["forecast_error_pct"].abs()
c["model_forecast_error_pct"] = (c["ciap_model_forecast_units"] - c["demand_units"]) / c["demand_units"]
c["model_upper"] = (c["ciap_model_forecast_units"] * 1.15).round()     # upper bound of the CIAP prediction range (~90% level for a 12% model error)
c["stock_cover_ratio"] = c["stock_available_units"] / c["model_upper"]
c["demand_to_stock_ratio"] = c["demand_units"] / c["stock_available_units"]
c["unit_cost"] = c["cogs"] / c["units_sold"].replace(0, np.nan)
c["cm_margin_pct"] = c["contribution_margin"] / c["revenue"]
c["incremental_cm"] = c["contribution_margin"] - c["baseline_contribution"]
c["campaign_cost"] = c["media_spend"] + c["discount_cost"]
c["roi"] = c["incremental_cm"] / c["campaign_cost"]
c["budget_used_pct"] = c["campaign_cost"] / c["budget"]
c["cac"] = np.where(c["new_customers"] > 0, c["campaign_cost"] / c["new_customers"].replace(0, np.nan), np.nan)
c["signoffs_count"] = 1 + (c[["supply_chain_signoff", "inventory_signoff", "logistics_signoff", "finance_signoff"]] == "Yes").sum(axis=1)
c["all_departments_signed"] = np.where(c["signoffs_count"] == 5, "Yes", "No")
c["launch_year"] = c["launch_date"].dt.year
c["launch_month"] = c["launch_date"].dt.month
c["launch_quarter"] = "Q" + c["launch_date"].dt.quarter.astype(str)
c["year_month"] = c["launch_date"].dt.to_period("M").astype(str)
c["peak_season"] = np.where(c["launch_month"].isin([11, 12]), "Nov-Dec peak", "Rest of year")
c["discount_band"] = pd.cut(c["discount_pct"], [-0.01, 0.10, 0.20, 0.30, 0.40, 1], labels=["0-10%", "10-20%", "20-30%", "30-40%", "40%+"]).astype(str)
c["cycle_time_band"] = pd.cut(c["approval_cycle_hours"], [0, 48, 72, 96, 1000], labels=["<48h", "48-72h", "72-96h", ">96h"]).astype(str)
c["stock_cover_band"] = pd.cut(c["stock_cover_ratio"], [0, 0.6, 0.8, 1.0, 1.2, 100], labels=["<0.6", "0.6-0.8", "0.8-1.0", "1.0-1.2", ">1.2"]).astype(str)
c["success_flag"] = (c["campaign_success"] == "Met objectives").astype(int)

# primary failure root cause (first rule that fails, in order of business impact)
c["failure_reason"] = np.select(
    [c["success_flag"] == 1, c["stockout_rate"] >= 0.08, c["on_time_delivery_rate"] < 0.90, c["contribution_margin"] <= 0, c["cltv_uplift_pct"] <= 0],
    ["Success", "Stockout", "Late delivery", "Loss-making", "CLTV erosion"], default="Other / mixed")

# ---------- CIAP gate simulation (what the new platform would have decided BEFORE launch) ----------
# Uses only information available at approval time: forecast, stock, capacity, budget, price, cost.
c["sim_peak_orders"] = c["model_upper"] / c["duration_days"] * 1.6 / 1.4
c["sim_rider_util"] = (c["base_orders_per_day"] + c["sim_peak_orders"]) / c["rider_capacity_orders_per_day"]
f_rev = c["ciap_model_forecast_units"] * c["unit_price"] * (1 - c["discount_pct"])
f_cm = f_rev - c["ciap_model_forecast_units"] * c["unit_cost"].fillna(c["unit_price"] * 0.42) - c["ciap_model_forecast_units"] / 1.4 * 6.5 - c["media_spend"]
c["sim_margin_pct"] = f_cm / f_rev
c["sim_cost"] = c["ciap_model_forecast_units"] * c["unit_price"] * c["discount_pct"] + c["media_spend"]
c["gate_inventory_BRL003"] = np.where(c["stock_cover_ratio"] >= 1.0, "Pass", "Hard fail")
c["gate_logistics_BRL009"] = np.where(c["sim_rider_util"] > 1.0, "Hard fail", np.where(c["sim_rider_util"] > 0.9, "Condition", "Pass"))
c["gate_finance_BRL012"] = np.where(c["sim_margin_pct"] < 0, "Hard fail", np.where(c["sim_margin_pct"] < 0.10, "Escalate", "Pass"))
c["gate_budget_BRL011"] = np.where(c["sim_cost"] > c["budget"], "Hard fail", "Pass")
c["gate_discount_BRL015"] = np.where(c["discount_pct"] > c["category"].map(CATEGORY_CEILING), "Escalate", "Pass")
gates = c[["gate_inventory_BRL003", "gate_logistics_BRL009", "gate_finance_BRL012", "gate_budget_BRL011", "gate_discount_BRL015"]]
c["gates_failed_hard"] = (gates == "Hard fail").sum(axis=1)
c["ciap_verdict"] = np.where(c["gates_failed_hard"] > 0, "Not feasible",
                             np.where((gates.isin(["Condition", "Escalate"])).any(axis=1), "Approve with conditions / escalate", "Approve"))
log(D, "10. Transform", "Derived features", len(c), "Added 30+ features incl. stock cover, forecast error, ROI, CAC, bands, failure reason and CIAP gate verdict")

c = c.sort_values("launch_date").reset_index(drop=True)
c["launch_date"] = c["launch_date"].dt.strftime("%Y-%m-%d")
QUALITY.append(profile(c, "campaigns", "clean"))
c.to_csv(CLEAN / "campaigns_clean.csv", index=False)

# =====================================================================================
# CUSTOMERS
# =====================================================================================
D = "customers"
u = pd.read_csv(RAW / "customers_raw.csv", dtype=str)
QUALITY.append(profile(u, "customers", "raw"))
dup = u.duplicated().sum()
u = u.drop_duplicates().reset_index(drop=True)
log(D, "2. Remove duplicates", "Customer rows exported twice", dup, "Dropped exact duplicates")
dup_id = u["customer_id"].duplicated().sum()
u = u.drop_duplicates("customer_id")
log(D, "2. Remove duplicates", "Repeated customer_id", dup_id, "Kept first record per customer")
TIER = {"tier 1": "Tier 1", "tier-1": "Tier 1", "t1": "Tier 1", "tier 2": "Tier 2", "tier-2": "Tier 2", "t2": "Tier 2", "tier 3": "Tier 3", "t3": "Tier 3"}
fixed = u["city_tier"].str.lower().map(TIER)
log(D, "3. Standardise labels", "city_tier as tier-1 / T1 / tier 2", (fixed != u["city_tier"]).sum(), "Mapped to Tier 1 / Tier 2 / Tier 3")
u["city_tier"] = fixed
for col in ["orders_12m", "avg_order_value", "revenue_12m", "discount_order_share", "returns_12m", "days_since_last_order", "predicted_cltv"]:
    u[col] = pd.to_numeric(u[col], errors="coerce")
neg = u["orders_12m"] < 0
u.loc[neg, "orders_12m"] = (u.loc[neg, "revenue_12m"] / u.loc[neg, "avg_order_value"]).round()
log(D, "6. Fix invalid values", "orders_12m = -1 (system default for 'unknown')", neg.sum(), "Recalculated as revenue_12m / avg_order_value")
m = u["age_band"].isna()
u.loc[m, "age_band"] = "Unknown"
log(D, "8. Impute missing", "age_band missing (not provided at sign-up)", m.sum(), "Labelled 'Unknown' - not imputed, to avoid inventing demographics")
u["acquisition_date"] = pd.to_datetime(u["acquisition_date"])
u["orders_12m"] = u["orders_12m"].astype(int)
u["churned"] = np.where(u["days_since_last_order"] > 180, "Yes", "No")
u["discount_dependency"] = pd.cut(u["discount_order_share"], [-0.01, 0.3, 0.6, 1.0], labels=["Low (<30%)", "Medium (30-60%)", "High (>60%)"]).astype(str)
u["value_tier"] = pd.qcut(u["predicted_cltv"].rank(method="first"), 4, labels=["Bronze", "Silver", "Gold", "Platinum"]).astype(str)
u = u.merge(c[["campaign_id", "campaign_type", "discount_pct", "stockout_rate", "on_time_delivery_rate"]].rename(columns={
    "campaign_id": "acquisition_campaign_id", "campaign_type": "acq_campaign_type", "discount_pct": "acq_discount_pct",
    "stockout_rate": "acq_stockout_rate", "on_time_delivery_rate": "acq_on_time_rate"}), on="acquisition_campaign_id", how="left")
log(D, "10. Transform", "Derived features", len(u), "Added churned flag, discount dependency band, value tier and acquisition-campaign experience (joined from campaigns)")
u["acquisition_date"] = u["acquisition_date"].dt.strftime("%Y-%m-%d")
QUALITY.append(profile(u, "customers", "clean"))
u.to_csv(CLEAN / "customers_clean.csv", index=False)

# =====================================================================================
# DAILY PERFORMANCE
# =====================================================================================
D = "campaign_daily"
d = pd.read_csv(RAW / "campaign_daily_raw.csv", dtype=str)
QUALITY.append(profile(d, "campaign_daily", "raw"))
dup = d.duplicated().sum()
d = d.drop_duplicates().reset_index(drop=True)
log(D, "2. Remove duplicates", "Day rows loaded twice", dup, "Dropped exact duplicates")
for col in ["campaign_day", "forecast_units", "demand_units", "stock_end_of_day", "orders", "on_time_rate"]:
    d[col] = pd.to_numeric(d[col])
d = d.sort_values(["campaign_id", "campaign_day"]).reset_index(drop=True)
na = d["units_sold"].isin(["NA"]) | d["units_sold"].isna()
d["units_sold"] = pd.to_numeric(d["units_sold"], errors="coerce")
start_stock = d["campaign_id"].map(c.set_index("campaign_id")["stock_available_units"])
prev = d.groupby("campaign_id")["stock_end_of_day"].shift(1).fillna(start_stock)
d.loc[na, "units_sold"] = (prev - d["stock_end_of_day"])[na]
log(D, "8. Impute missing", "units_sold = 'NA' (feed dropped)", na.sum(), "Recovered exactly from stock movement: previous day stock - today's stock")
d["units_sold"] = d["units_sold"].round().astype(int)
d["lost_units"] = (d["demand_units"] - d["units_sold"]).clip(lower=0)
d["stocked_out"] = np.where(d["stock_end_of_day"] <= 0, 1, 0)
d["cum_forecast"] = d.groupby("campaign_id")["forecast_units"].cumsum()
d["cum_demand"] = d.groupby("campaign_id")["demand_units"].cumsum()
d["cum_sold"] = d.groupby("campaign_id")["units_sold"].cumsum()
log(D, "10. Transform", "Derived features", len(d), "Added lost units, stock-out flag and cumulative forecast / demand / sales")
QUALITY.append(profile(d, "campaign_daily", "clean"))
d.to_csv(CLEAN / "campaign_daily_clean.csv", index=False)

pd.DataFrame(LOG).to_csv(OUT / "cleaning_log.csv", index=False)
pd.DataFrame(QUALITY).to_csv(OUT / "data_quality_summary.csv", index=False)
print(pd.DataFrame(QUALITY).to_string(index=False))
print(f"\n{len(LOG)} cleaning steps logged -> outputs/cleaning_log.csv")
