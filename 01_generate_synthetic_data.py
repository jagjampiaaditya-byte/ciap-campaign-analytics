"""
Step 1 - Synthetic data generation
===================================
Business idea being validated: XYZ (an e-commerce company) wants to replace its manual,
department-by-department campaign approval with the Campaign Intelligence & Approval
Platform (CIAP), which only launches a campaign when inventory, logistics and finance
"gates" pass.

To validate (and diagnose) that strategy we need history that XYZ does not yet have in
one place, so we simulate it. The generator encodes the cause-and-effect chain the BRD
describes:

    discount depth x segment sensitivity  ->  demand uplift
    demand vs stock planned in silos      ->  stockouts / lost sales
    peak orders vs rider capacity         ->  late deliveries
    stockouts + late deliveries           ->  lower CSAT, repeat purchase and CLTV
    manual sign-offs skipped / slow       ->  more failures, missed demand windows

Three related datasets are produced (deliberately "dirty", like real exports):
    data/raw/campaigns_raw.csv           one row per historical campaign (~1,500)
    data/raw/customers_raw.csv           customers acquired by those campaigns (~6,000)
    data/raw/campaign_daily_raw.csv      day-by-day performance of recent campaigns

Run:  python 01_generate_synthetic_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
OUT = Path(__file__).parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

N_CAMPAIGNS = 1500
N_CUSTOMERS = 6000
N_DAILY_CAMPAIGNS = 250

# ----------------------------------------------------------------------------------
# Reference tables (same assumptions as the CIAP dashboard / BRD)
# ----------------------------------------------------------------------------------
TYPES = {  # share, demand multiplier, discount range, duration range
    "Discount":       (0.30, 1.00, (0.10, 0.35), (7, 28)),
    "Flash Sale":     (0.15, 1.30, (0.20, 0.50), (2, 5)),
    "Seasonal Event": (0.15, 1.10, (0.15, 0.40), (7, 21)),
    "Bundle":         (0.12, 0.80, (0.10, 0.25), (7, 28)),
    "Free Delivery":  (0.10, 0.55, (0.00, 0.05), (7, 21)),
    "Loyalty Reward": (0.10, 0.70, (0.05, 0.15), (7, 28)),
    "Clearance":      (0.08, 1.00, (0.30, 0.60), (7, 21)),
}
SEGMENTS = {  # share, discount sensitivity, base repeat rate, CLTV lift, new-customer share, avg CLTV
    "Champions":           (0.10, 0.80, 0.55, 0.040, 0.00, 1450),
    "Loyal Regulars":      (0.20, 1.00, 0.45, 0.050, 0.02, 820),
    "Potential Loyalists": (0.22, 1.15, 0.30, 0.090, 0.10, 410),
    "Discount Seekers":    (0.20, 1.40, 0.18, -0.020, 0.15, 190),
    "At-Risk / Lapsed":    (0.13, 1.05, 0.15, 0.120, 0.00, 260),
    "New Prospects":       (0.15, 1.10, 0.20, 0.060, 0.90, 300),
}
CATEGORIES = {  # share, elasticity, avg price, cost ratio, base daily units, discount ceiling
    "Footwear":    (0.18, 7.0, 110, 0.48, 380, 0.30),
    "Apparel":     (0.26, 5.0, 45, 0.38, 700, 0.40),
    "Electronics": (0.20, 6.0, 95, 0.50, 420, 0.20),
    "Home":        (0.16, 4.0, 55, 0.40, 260, 0.35),
    "Beauty":      (0.20, 4.5, 32, 0.30, 600, 0.30),
}
REGIONS = {"Nationwide": (0.50, 1.00), "Metro only": (0.30, 0.60), "Regional": (0.20, 0.35)}
CHANNELS = ["Email", "App Push", "Paid Social", "Search", "On-site Banner", "Marketplace"]
FORECAST_TEAMS = {"Marketing": (0.14, 0.28), "Inventory": (-0.08, 0.22), "Finance": (0.00, 0.33)}  # bias, noise


def pick(d, n):
    keys = list(d)
    p = np.array([d[k][0] for k in keys], dtype=float)
    return rng.choice(keys, size=n, p=p / p.sum())


# ----------------------------------------------------------------------------------
# 1. Campaigns
# ----------------------------------------------------------------------------------
n = N_CAMPAIGNS
start, end = pd.Timestamp("2023-01-02"), pd.Timestamp("2026-09-30")
days = pd.date_range(start, end, freq="D")
# more campaigns in Q4 (festive / Black Friday) and in later years (company growth)
w = np.where(days.month.isin([10, 11, 12]), 1.8, 1.0) * (1 + 0.25 * (days.year.to_numpy() - 2023))
launch = pd.to_datetime(rng.choice(days, size=n, p=w / w.sum()))

ctype = pick(TYPES, n)
seg = pick(SEGMENTS, n)
cat = pick(CATEGORIES, n)
region = pick(REGIONS, n)

dur = np.array([rng.integers(TYPES[t][3][0], TYPES[t][3][1] + 1) for t in ctype])
disc = np.array([rng.uniform(*TYPES[t][2]) for t in ctype])
disc = np.round(np.clip(disc + rng.normal(0, 0.02, n), 0, 0.7), 2)
hero = rng.random(n) < 0.45
n_channels = rng.integers(1, 5, n)
primary_channel = rng.choice(CHANNELS, n, p=[0.32, 0.18, 0.2, 0.12, 0.1, 0.08])
zone_share = np.array([REGIONS[r][1] for r in region])

elast = np.array([CATEGORIES[c][1] for c in cat])
price = np.array([CATEGORIES[c][2] for c in cat]) * rng.lognormal(0, 0.2, n)
cost_ratio = np.array([CATEGORIES[c][3] for c in cat]) + rng.normal(0, 0.03, n)
base_daily = np.array([CATEGORIES[c][4] for c in cat]) * zone_share * rng.lognormal(0, 0.35, n) * np.where(hero, 1.4, 0.8)
sens = np.array([SEGMENTS[s][1] for s in seg])
tmult = np.array([TYPES[t][1] for t in ctype])
season = np.where(launch.month.isin([11, 12]), 1.30, np.where(launch.month.isin([6, 7]), 0.9, 1.0))

uplift = 1 + elast * disc * sens * tmult
expected_units = base_daily * dur * uplift * season          # what a perfect forecaster would predict

# --- manual approval process (current state) ---
sc_ok = rng.random(n) < 0.70
inv_ok = rng.random(n) < 0.75
log_ok = rng.random(n) < 0.65
fin_ok = rng.random(n) < 0.80
signoffs = 1 + sc_ok.astype(int) + inv_ok + log_ok + fin_ok         # Marketing always signs
cycle_h = np.round(10 + 13 * signoffs * rng.lognormal(0, 0.35, n) + rng.exponential(10, n), 1)
team = rng.choice(list(FORECAST_TEAMS), n, p=[0.55, 0.25, 0.20])
bias = np.array([FORECAST_TEAMS[t][0] for t in team])
noise = np.array([FORECAST_TEAMS[t][1] for t in team])
forecast = expected_units * (1 + bias) * rng.lognormal(0, noise)
forecast_upper = forecast * 1.20
# back-tested CIAP demand model (AI-005, R^2 ~ 0.7): unbiased, much tighter than the departmental forecasts
model_forecast = expected_units * rng.lognormal(0, 0.12, n)

# stock is planned by Inventory on its own estimate; when Inventory is skipped it is a guess
stock_ratio = np.where(inv_ok, rng.lognormal(np.log(1.30), 0.22, n), rng.lognormal(np.log(0.95), 0.35, n))
# when Supply Chain confirmed a replenishment, more stock arrives in time
stock = expected_units * stock_ratio * np.where(sc_ok, rng.uniform(1.0, 1.15, n), 1.0)

# actual demand: random shock; slow approvals miss demand windows of time-critical campaigns
shock = rng.lognormal(0, 0.25, n)
missed_window = (cycle_h > 96) & np.isin(ctype, ["Flash Sale", "Seasonal Event"])
demand = expected_units * shock * np.where(missed_window, 0.82, 1.0)
units_sold = np.minimum(demand, stock)
lost_units = demand - units_sold
stockout_rate = np.clip(np.maximum(0, 1 - stock / demand) * 0.95 + rng.normal(0, 0.01, n), 0, 1)
stockout_rate = np.where(lost_units <= 1, np.clip(rng.normal(0.004, 0.004, n), 0, 0.02), stockout_rate)

# logistics: peak-day orders against rider capacity (Logistics sign-off adds 3PL riders)
base_orders = np.round(rng.uniform(2500, 9000, n) * zone_share)
peak_orders = units_sold / dur * 1.6 / 1.4
planned_peak = forecast_upper / dur * 1.6 / 1.4          # what Logistics would plan for if consulted
rider_capacity = np.round(np.where(log_ok,
                                   np.maximum(base_orders * rng.uniform(1.2, 1.6, n), (base_orders + planned_peak) * rng.uniform(1.0, 1.2, n)),
                                   base_orders * rng.uniform(1.2, 1.7, n)))
util = (base_orders + peak_orders) / rider_capacity
on_time = np.clip(0.97 - 0.35 * np.maximum(0, util - 0.8) - 0.6 * np.maximum(0, util - 1) + rng.normal(0, 0.01, n), 0.6, 0.995)

# money
media = forecast * price * rng.uniform(0.03, 0.08, n)
budget = (forecast * price * disc * rng.uniform(1.0, 1.5, n) + media) * rng.uniform(0.95, 1.2, n)
revenue = units_sold * price * (1 - disc)
discount_cost = units_sold * price * disc
cogs = units_sold * price * cost_ratio
fulfil = units_sold / 1.4 * 6.5 * (1 + 0.5 * np.maximum(0, util - 1))
cm = revenue - cogs - fulfil - media
# sales the targeted audience would have made anyway, at full price (about half of the SKU's normal run-rate)
baseline_units = base_daily * dur * 0.5
baseline_cm = baseline_units * price * (1 - cost_ratio) - baseline_units / 1.4 * 6.5
roi = (cm - baseline_cm) / (media + discount_cost)

# customers
seg_new = np.array([SEGMENTS[s][4] for s in seg])
seg_rep = np.array([SEGMENTS[s][2] for s in seg])
seg_lift = np.array([SEGMENTS[s][3] for s in seg])
new_customers = np.round(units_sold / 1.6 * seg_new * rng.uniform(0.7, 1.1, n))
repeat = np.clip(seg_rep - 0.8 * stockout_rate - 0.5 * np.maximum(0, 0.93 - on_time) - 0.15 * np.maximum(0, disc - 0.3) + rng.normal(0, 0.03, n), 0.01, 0.9)
cltv_uplift = seg_lift - 0.25 * stockout_rate - 0.3 * np.maximum(0, 0.93 - on_time) - 0.10 * np.maximum(0, disc - 0.3) + rng.normal(0, 0.02, n)
csat = np.clip(4.6 - 6 * np.maximum(0, 0.95 - on_time) - 2.5 * stockout_rate + rng.normal(0, 0.15, n), 1, 5)
returns = np.clip(0.03 + disc * 0.08 + np.where(seg == "Discount Seekers", 0.03, 0) + rng.normal(0, 0.008, n), 0.005, 0.3)
complaints = rng.poisson(units_sold / 1000 * (1 + 20 * stockout_rate + 15 * np.maximum(0, 0.93 - on_time)))
# overrides happen when a department objected (mostly thin stock) but the campaign launched anyway
override = rng.random(n) < np.where(stock_ratio < 0.95, 0.22, 0.03) * np.where(signoffs < 4, 1.3, 1.0)

success = (cm > 0) & (stockout_rate < 0.08) & (on_time > 0.90) & (cltv_uplift > 0)
flip = rng.random(n) < 0.03
success = np.where(flip, ~success, success)

camp = pd.DataFrame({
    "campaign_id": [f"CMP-{i:05d}" for i in range(10001, 10001 + n)],
    "launch_date": launch,
    "duration_days": dur,
    "campaign_type": ctype,
    "target_segment": seg,
    "category": cat,
    "hero_sku": np.where(hero, "Y", "N"),
    "region_scope": region,
    "primary_channel": primary_channel,
    "channel_count": n_channels,
    "discount_pct": disc,
    "unit_price": np.round(price, 2),
    "budget": np.round(budget, 0),
    "media_spend": np.round(media, 0),
    "forecast_team": team,
    "forecast_units": np.round(forecast),
    "ciap_model_forecast_units": np.round(model_forecast),
    "stock_available_units": np.round(stock),
    "supply_chain_signoff": np.where(sc_ok, "Yes", "No"),
    "inventory_signoff": np.where(inv_ok, "Yes", "No"),
    "logistics_signoff": np.where(log_ok, "Yes", "No"),
    "finance_signoff": np.where(fin_ok, "Yes", "No"),
    "approval_cycle_hours": cycle_h,
    "override_flag": np.where(override, "Yes", "No"),
    "base_orders_per_day": base_orders,
    "rider_capacity_orders_per_day": rider_capacity,
    "units_sold": np.round(units_sold),
    "lost_sales_units": np.round(lost_units),
    "stockout_rate": np.round(stockout_rate, 4),
    "peak_rider_utilisation": np.round(util, 3),
    "on_time_delivery_rate": np.round(on_time, 4),
    "revenue": np.round(revenue, 0),
    "discount_cost": np.round(discount_cost, 0),
    "cogs": np.round(cogs, 0),
    "fulfilment_cost": np.round(fulfil, 0),
    "contribution_margin": np.round(cm, 0),
    "baseline_contribution": np.round(baseline_cm, 0),
    "new_customers": new_customers.astype(int),
    "repeat_rate_90d": np.round(repeat, 3),
    "cltv_uplift_pct": np.round(cltv_uplift * 100, 2),
    "csat_score": np.round(csat, 2),
    "return_rate": np.round(returns, 4),
    "complaints": complaints,
    "campaign_success": np.where(success, "Met objectives", "Missed objectives"),
})

# ---------- inject realistic data-quality problems (fixed in step 2) ----------
dirty = camp.copy().astype(object)
idx = lambda frac: rng.choice(n, int(n * frac), replace=False)  # noqa: E731
# 1. inconsistent category labels / stray whitespace / case
for col, variants in {
    "campaign_type": {"Flash Sale": ["flash sale", "FLASH SALE ", "Flash-Sale"], "Free Delivery": ["free delivery", "Free delivery "]},
    "target_segment": {"At-Risk / Lapsed": ["At Risk", "at-risk/lapsed"], "Discount Seekers": ["discount seekers", "Discount seeker"]},
    "region_scope": {"Metro only": ["Metro", "METRO ONLY"], "Nationwide": ["National", " nationwide"]},
}.items():
    for canon, alts in variants.items():
        hits = [i for i in idx(0.25) if dirty.at[i, col] == canon]
        for i in hits:
            dirty.at[i, col] = rng.choice(alts)
# 2. discount stored as text "25%" in some rows
for i in idx(0.12):
    dirty.at[i, "discount_pct"] = f"{float(camp.at[i, 'discount_pct']) * 100:.0f}%"
# 3. currency formatted as text
for i in idx(0.08):
    dirty.at[i, "budget"] = f"${float(camp.at[i, 'budget']):,.0f}"
# 4. mixed date formats
dates = []
for i, d in enumerate(camp["launch_date"]):
    r = rng.random()
    dates.append(d.strftime("%d/%m/%Y") if r < 0.15 else d.strftime("%b %d, %Y") if r < 0.22 else d.strftime("%Y-%m-%d"))
dirty["launch_date"] = dates
# 5. missing values
for col, frac in {"csat_score": 0.06, "media_spend": 0.03, "on_time_delivery_rate": 0.04, "forecast_team": 0.05, "repeat_rate_90d": 0.03}.items():
    for i in idx(frac):
        dirty.at[i, col] = np.nan
# 6. data-entry errors: negative units, budget typed with two extra zeros, impossible rates
for i in idx(0.006):
    dirty.at[i, "units_sold"] = -abs(float(camp.at[i, "units_sold"]))
for i in idx(0.004):
    dirty.at[i, "budget"] = float(camp.at[i, "budget"]) * 100
for i in idx(0.004):
    dirty.at[i, "on_time_delivery_rate"] = 1.5
# 7. yes/no flags written differently
for col in ["inventory_signoff", "logistics_signoff"]:
    for i in idx(0.06):
        dirty.at[i, col] = {"Yes": rng.choice(["Y", "yes", "TRUE"]), "No": rng.choice(["N", "no", "FALSE"])}[camp.at[i, col]]
# 8. duplicated export rows
dups = dirty.iloc[idx(0.025)]
dirty = pd.concat([dirty, dups]).sample(frac=1, random_state=SEED).reset_index(drop=True)
dirty.to_csv(OUT / "campaigns_raw.csv", index=False)

# ----------------------------------------------------------------------------------
# 2. Customers acquired by campaigns
# ----------------------------------------------------------------------------------
acq_w = camp["new_customers"].to_numpy() + 1
acq_idx = rng.choice(n, N_CUSTOMERS, p=acq_w / acq_w.sum())
c_src = camp.iloc[acq_idx].reset_index(drop=True)
c_seg = np.where(rng.random(N_CUSTOMERS) < 0.7, c_src["target_segment"], rng.choice(list(SEGMENTS), N_CUSTOMERS))
lam = np.array([{"Champions": 9, "Loyal Regulars": 5.5, "Potential Loyalists": 3, "Discount Seekers": 2.4, "At-Risk / Lapsed": 1.4, "New Prospects": 2}[s] for s in c_seg])
lam = lam * (1 - 1.5 * c_src["stockout_rate"].to_numpy()) * (1 - 2 * np.maximum(0, 0.93 - c_src["on_time_delivery_rate"].to_numpy()))
orders = rng.poisson(np.maximum(0.2, lam))
aov = np.round(rng.lognormal(np.log(58), 0.35, N_CUSTOMERS) * np.where(c_seg == "Champions", 1.5, 1), 2)
disc_share = np.clip(0.15 + 0.9 * c_src["discount_pct"].to_numpy() + np.where(c_seg == "Discount Seekers", 0.3, 0) + rng.normal(0, 0.08, N_CUSTOMERS), 0, 1)
acq_date = c_src["launch_date"] + pd.to_timedelta(rng.integers(0, 10, N_CUSTOMERS), unit="D")
last_gap = np.round(rng.exponential(365 / np.maximum(orders, 0.5)))
rev12 = np.round(orders * aov, 2)
margin = 0.32 - 0.25 * disc_share
cltv = np.round(rev12 * margin * (1.5 + orders / 3) * rng.lognormal(0, 0.15, N_CUSTOMERS), 2)
cust = pd.DataFrame({
    "customer_id": [f"CUS-{i:06d}" for i in range(200001, 200001 + N_CUSTOMERS)],
    "acquisition_campaign_id": c_src["campaign_id"],
    "acquisition_date": acq_date.dt.strftime("%Y-%m-%d"),
    "segment": c_seg,
    "age_band": rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], N_CUSTOMERS, p=[0.18, 0.34, 0.25, 0.14, 0.09]),
    "city_tier": rng.choice(["Tier 1", "Tier 2", "Tier 3"], N_CUSTOMERS, p=[0.5, 0.32, 0.18]),
    "orders_12m": orders,
    "avg_order_value": aov,
    "revenue_12m": rev12,
    "discount_order_share": np.round(disc_share, 3),
    "returns_12m": rng.binomial(np.maximum(orders, 0), 0.06),
    "days_since_last_order": last_gap.astype(int),
    "predicted_cltv": cltv,
}).astype(object)
for i in rng.choice(N_CUSTOMERS, 240, replace=False):
    cust.at[i, "age_band"] = np.nan
for i in rng.choice(N_CUSTOMERS, 600, replace=False):
    cust.at[i, "city_tier"] = {"Tier 1": rng.choice(["tier-1", "T1"]), "Tier 2": rng.choice(["tier 2", "T2"]), "Tier 3": "T3"}[cust.at[i, "city_tier"]]
for i in rng.choice(N_CUSTOMERS, 25, replace=False):
    cust.at[i, "orders_12m"] = -1
cust = pd.concat([cust, cust.iloc[rng.choice(N_CUSTOMERS, 90, replace=False)]]).sample(frac=1, random_state=SEED).reset_index(drop=True)
cust.to_csv(OUT / "customers_raw.csv", index=False)

# ----------------------------------------------------------------------------------
# 3. Day-by-day performance for the most recent campaigns
# ----------------------------------------------------------------------------------
recent = camp.sort_values("launch_date").tail(N_DAILY_CAMPAIGNS)
rows = []
for _, c in recent.iterrows():
    d = int(c["duration_days"])
    wts = np.exp(-0.06 * np.arange(d)); wts /= wts.sum()
    demand_tot = c["units_sold"] + c["lost_sales_units"]
    fc_tot = c["forecast_units"]
    stock_left = c["stock_available_units"]
    for k in range(d):
        dem = demand_tot * wts[k] * rng.lognormal(0, 0.1)
        sold = min(dem, stock_left)
        stock_left -= sold
        rows.append({
            "campaign_id": c["campaign_id"], "date": (c["launch_date"] + pd.Timedelta(days=k)).strftime("%Y-%m-%d"), "campaign_day": k + 1,
            "forecast_units": round(fc_tot * wts[k]), "demand_units": round(dem), "units_sold": round(sold),
            "stock_end_of_day": round(stock_left), "orders": round(sold / 1.4),
            "on_time_rate": round(float(np.clip(c["on_time_delivery_rate"] + rng.normal(0, 0.012) - (0.03 if k < 2 else 0), 0.6, 0.999)), 4),
        })
daily = pd.DataFrame(rows).astype(object)
for i in rng.choice(len(daily), int(len(daily) * 0.02), replace=False):
    daily.at[i, "units_sold"] = "NA"
daily = pd.concat([daily, daily.iloc[rng.choice(len(daily), 60, replace=False)]]).reset_index(drop=True)
daily.to_csv(OUT / "campaign_daily_raw.csv", index=False)

print(f"campaigns_raw.csv      {len(dirty):>6} rows x {dirty.shape[1]} cols")
print(f"customers_raw.csv      {len(cust):>6} rows x {cust.shape[1]} cols")
print(f"campaign_daily_raw.csv {len(daily):>6} rows x {daily.shape[1]} cols")
print(f"True success rate (before dirtying): {success.mean():.1%}")
