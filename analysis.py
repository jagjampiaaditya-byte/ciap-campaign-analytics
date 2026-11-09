"""
Shared analysis layer used by both the Streamlit dashboard (app.py) and the report
figures (03_eda_figures.py). Every chart has one function that returns the data it
plots plus a plain-English explanation computed from that same data, so the numbers
quoted in the dashboard and in the report always match.
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
CLEAN = BASE / "data" / "clean"
OUT = BASE / "outputs"

CORR_VARS = {
    "discount_pct": "Discount %",
    "stock_cover_ratio": "Stock cover ratio",
    "approval_cycle_hours": "Approval cycle (h)",
    "signoffs_count": "Departments signed off",
    "abs_forecast_error_pct": "Forecast error (abs)",
    "peak_rider_utilisation": "Peak rider utilisation",
    "stockout_rate": "Stockout rate",
    "on_time_delivery_rate": "On-time delivery",
    "csat_score": "CSAT",
    "repeat_rate_90d": "Repeat rate 90d",
    "cltv_uplift_pct": "CLTV uplift %",
    "cm_margin_pct": "Contribution margin %",
    "roi": "ROI",
    "return_rate": "Return rate",
    "success_flag": "Success (1/0)",
}
SEG_ORDER = ["Champions", "Loyal Regulars", "Potential Loyalists", "At-Risk / Lapsed", "New Prospects", "Discount Seekers"]
DISC_ORDER = ["0-10%", "10-20%", "20-30%", "30-40%", "40%+"]
COVER_ORDER = ["<0.6", "0.6-0.8", "0.8-1.0", "1.0-1.2", ">1.2"]
CYCLE_ORDER = ["<48h", "48-72h", "72-96h", ">96h"]
VERDICT_ORDER = ["Approve", "Approve with conditions / escalate", "Not feasible"]


def load():
    c = pd.read_csv(CLEAN / "campaigns_clean.csv", parse_dates=["launch_date"])
    u = pd.read_csv(CLEAN / "customers_clean.csv", parse_dates=["acquisition_date"])
    d = pd.read_csv(CLEAN / "campaign_daily_clean.csv", parse_dates=["date"])
    log = pd.read_csv(OUT / "cleaning_log.csv")
    q = pd.read_csv(OUT / "data_quality_summary.csv")
    return c, u, d, log, q


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def money(x):
    a = abs(x)
    s = "-" if x < 0 else ""
    return f"{s}${a / 1e6:.2f}M" if a >= 1e6 else f"{s}${a / 1e3:.0f}k" if a >= 1e3 else f"{s}${a:.0f}"


def explain(what, insight, action):
    return {"what": what, "insight": insight, "action": action}


# ------------------------------------------------------------------ headline KPIs
def kpis(c):
    return {
        "Campaigns": f"{len(c):,}",
        "Success rate": pct(c["success_flag"].mean()),
        "Revenue": money(c["revenue"].sum()),
        "Contribution margin": money(c["contribution_margin"].sum()),
        "Median ROI": f"{c['roi'].median():.2f}x",
        "Lost sales (units)": f"{c['lost_sales_units'].sum() / 1e6:.2f}M",
        "Avg stockout rate": pct(c["stockout_rate"].mean(), 1),
        "Avg on-time": pct(c["on_time_delivery_rate"].mean(), 1),
        "Median approval time": f"{c['approval_cycle_hours'].median():.0f} h",
    }


# ================================================================== DESCRIPTIVE
def monthly_trend(c):
    m = c.groupby(c["launch_date"].dt.to_period("Q").astype(str)).agg(campaigns=("campaign_id", "count"), success_rate=("success_flag", "mean")).reset_index().rename(columns={"launch_date": "quarter"})
    best, worst = m.loc[m["success_rate"].idxmax()], m.loc[m["success_rate"].idxmin()]
    q4 = c[c["launch_month"].isin([11, 12])]["success_flag"].mean()
    rest = c[~c["launch_month"].isin([11, 12])]["success_flag"].mean()
    return m, explain(
        "Number of campaigns launched per quarter (bars) and the share that met their objectives (line).",
        f"Volume grows every year and peaks in Q4, but the success rate does not improve with experience: it swings between {pct(worst['success_rate'])} ({worst['quarter']}) and {pct(best['success_rate'])} ({best['quarter']}). "
        f"Nov-Dec campaigns succeed {pct(q4)} of the time vs {pct(rest)} for the rest of the year.",
        "More campaigns are not translating into better campaigns, which shows the manual process is not learning (problem PS-06). Peak season needs the strictest feasibility checks.")


def by_type(c):
    t = c.groupby("campaign_type").agg(campaigns=("campaign_id", "count"), success_rate=("success_flag", "mean"), median_roi=("roi", "median"),
                                       avg_discount=("discount_pct", "mean"), avg_stockout=("stockout_rate", "mean")).reset_index().sort_values("success_rate")
    lo, hi = t.iloc[0], t.iloc[-1]
    return t, explain(
        "Campaign count and success rate for each campaign type.",
        f"{hi['campaign_type']} campaigns succeed most often ({pct(hi['success_rate'])}); {lo['campaign_type']} campaigns least ({pct(lo['success_rate'])}, average discount {pct(lo['avg_discount'])}, average stockout {pct(lo['avg_stockout'], 1)}).",
        "High-discount, high-velocity types need tighter stock and capacity gates. This is why CIAP picks which models and rules to run by campaign type (BRD Section 10.2).")


def metric_distribution(c, col="roi"):
    s = c[col].dropna()
    skew = s.skew()
    neg = (s < 0).mean()
    return s, explain(
        f"Distribution (histogram) of {CORR_VARS.get(col, col)} across all campaigns.",
        f"Median {s.median():.2f}, mean {s.mean():.2f}, skewness {skew:.2f}. {pct(neg)} of campaigns have a negative value.",
        "The distribution is skewed with a long tail, so the analysis uses medians and robust comparisons rather than the mean alone. The negative tail is the money CIAP's finance gate (BRL-012) aims to stop.")


def discount_by_type(c):
    over = (c["gate_discount_BRL015"] == "Escalate").mean()
    return c[["campaign_type", "discount_pct"]], explain(
        "Spread of discount depth for each campaign type (box = middle 50%, line = median, whiskers = typical range).",
        f"Clearance and Flash Sale campaigns use the deepest discounts and have the widest spread. {pct(over)} of all campaigns went above the category discount ceiling that CIAP would escalate (BRL-015).",
        "Discount depth is set case by case with no common ceiling. Category ceilings with escalation give consistency without banning deep discounts.")


def cycle_time(c):
    g = c.groupby("signoffs_count")["approval_cycle_hours"].median()
    return c[["approval_cycle_hours", "signoffs_count"]], explain(
        "Distribution of approval cycle time (hours from proposal to launch decision), coloured by how many departments signed off.",
        f"Median approval takes {c['approval_cycle_hours'].median():.0f} h, and {pct((c['approval_cycle_hours'] > 96).mean())} of campaigns take more than 4 days. "
        f"Each extra department adds time: median {g.iloc[0]:.0f} h with {g.index[0]} sign-off vs {g.iloc[-1]:.0f} h with {g.index[-1]}.",
        "The manual process forces a trade-off: being thorough (all five checks) is slow, and being fast means skipping checks. CIAP removes the trade-off by running all five evaluations in parallel (FR-014).")


# ================================================================== CORRELATION
def corr_matrix(c, method="pearson"):
    m = c[list(CORR_VARS)].rename(columns=CORR_VARS).corr(method=method)
    pairs = m.where(np.triu(np.ones(m.shape), 1).astype(bool)).stack().sort_values(key=abs, ascending=False)
    top = pairs.head(5)
    txt = "; ".join(f"{a} and {b} ({v:+.2f})" for (a, b), v in top.items())
    return m, explain(
        f"{method.title()} correlation between 15 numeric campaign variables (+1 = move together, -1 = move opposite, 0 = no linear link).",
        f"Strongest relationships: {txt}.",
        "Two chains stand out. Stock cover drives stockouts, which hurt CSAT, repeat purchase and CLTV. Rider utilisation drives late deliveries, which hurt CSAT. These are exactly the operational gates CIAP enforces before launch.")


def success_drivers(c):
    s = c[list(CORR_VARS)].corr()["success_flag"].drop("success_flag").rename(index=CORR_VARS).sort_values()
    return s, explain(
        "Correlation of each variable with campaign success (point-biserial correlation with the 1/0 success flag).",
        f"Most positive: {s.index[-1]} ({s.iloc[-1]:+.2f}) and {s.index[-2]} ({s.iloc[-2]:+.2f}). Most negative: {s.index[0]} ({s.iloc[0]:+.2f}) and {s.index[1]} ({s.iloc[1]:+.2f}).",
        "Outcome variables (CLTV, repeat rate, CSAT) naturally correlate with success. The decision levers available before launch, namely stock cover, discount depth and rider capacity, are the ones CIAP can act on.")


def discount_uplift(c):
    df = c[["discount_pct", "target_segment", "demand_units", "duration_days", "category"]].copy()
    base = c["baseline_contribution"]  # proxy not needed; uplift vs model forecast without discount isn't stored
    df["units_per_day"] = df["demand_units"] / df["duration_days"]
    r = df.groupby("target_segment").apply(lambda g: g["discount_pct"].corr(np.log(g["units_per_day"])), include_groups=False).sort_values()
    overall = df["discount_pct"].corr(np.log(df["units_per_day"]))
    return df, explain(
        "Each dot is a campaign: discount depth against demand per day (log scale), coloured by target segment.",
        f"Deeper discounts lift demand (correlation with log demand {overall:+.2f}). The response is strongest for {r.index[-1]} ({r.iloc[-1]:+.2f}) and weakest for {r.index[0]} ({r.iloc[0]:+.2f}).",
        "A discount is a demand multiplier, so every extra point of discount must be matched by stock and delivery capacity. That is why CIAP tests feasibility against the upper bound of the forecast, not the average.")


def stock_vs_stockout(c):
    below = c[c["stock_cover_ratio"] < 1]
    above = c[c["stock_cover_ratio"] >= 1]
    r = c["stock_cover_ratio"].corr(c["stockout_rate"], method="spearman")
    return c[["stock_cover_ratio", "stockout_rate", "campaign_success"]], explain(
        "Stock available at launch divided by the upper bound of the CIAP demand forecast (x-axis) against the share of campaign days out of stock (y-axis).",
        f"Clear threshold effect (Spearman {r:+.2f}). Below a cover ratio of 1.0 the average stockout rate is {pct(below['stockout_rate'].mean(), 1)}; at 1.0 or above it is {pct(above['stockout_rate'].mean(), 1)}. "
        f"{pct(len(below) / len(c))} of campaigns launched below 1.0.",
        "This validates rule BRL-003: requiring stock to cover the forecast upper bound removes most stockouts. The threshold sits at 1.0, as the BRD specifies.")


def rider_vs_ontime(c):
    hi = c[c["peak_rider_utilisation"] > 1]
    lo = c[c["peak_rider_utilisation"] <= 0.9]
    r = c["peak_rider_utilisation"].corr(c["on_time_delivery_rate"])
    return c[["peak_rider_utilisation", "on_time_delivery_rate", "region_scope"]], explain(
        "Peak-day rider utilisation (orders ÷ rider capacity) against on-time delivery rate.",
        f"Correlation {r:+.2f}. Campaigns that stayed under 90% utilisation delivered {pct(lo['on_time_delivery_rate'].mean(), 1)} on time; those above 100% only {pct(hi['on_time_delivery_rate'].mean(), 1)} ({len(hi)} campaigns).",
        "Delivery performance holds until capacity is exhausted, then falls sharply. This supports BRL-009 (hard gate above 100%, condition inside a 10% buffer) and BRL-010.")


def experience_vs_loyalty(c):
    b = c.assign(stockout_band=pd.cut(c["stockout_rate"], [-0.01, 0.02, 0.08, 0.2, 1], labels=["<2%", "2-8%", "8-20%", ">20%"]).astype(str))
    t = b.groupby("stockout_band").agg(csat=("csat_score", "mean"), repeat=("repeat_rate_90d", "mean"), cltv=("cltv_uplift_pct", "mean"), n=("campaign_id", "count")).reindex(["<2%", "2-8%", "8-20%", ">20%"]).reset_index()
    return t, explain(
        "Average CSAT, 90-day repeat rate and CLTV uplift for campaigns grouped by stockout rate.",
        f"As stockouts rise from <2% to >20%, CSAT falls from {t['csat'].iloc[0]:.2f} to {t['csat'].iloc[-1]:.2f}, repeat rate from {pct(t['repeat'].iloc[0])} to {pct(t['repeat'].iloc[-1])} and CLTV uplift from {t['cltv'].iloc[0]:+.1f}% to {t['cltv'].iloc[-1]:+.1f}%.",
        "A stockout costs twice: the sale today and customer value tomorrow (BRD Section 2). This puts a number on the CLTV argument for blocking infeasible campaigns.")


# ================================================================== DIAGNOSTIC
def failure_pareto(c):
    f = c[c["failure_reason"] != "Success"]["failure_reason"].value_counts().reset_index()
    f.columns = ["reason", "campaigns"]
    f["cum_share"] = f["campaigns"].cumsum() / f["campaigns"].sum()
    lost_cm = c[c["failure_reason"] == "Loss-making"]["contribution_margin"].sum()
    return f, explain(
        "Pareto chart of the primary reason each failed campaign missed its objectives (bars) with the cumulative share (line).",
        f"{len(c) - c['success_flag'].sum():,} campaigns failed. {f['reason'].iloc[0]} is the biggest cause ({pct(f['campaigns'].iloc[0] / f['campaigns'].sum())}), and the top two causes explain {pct(f['cum_share'].iloc[1])}. Loss-making campaigns lost {money(-lost_cm)} of margin in total.",
        "Most failures are operational (stock and delivery), not creative. They can be predicted before launch, which is the core claim of the CIAP strategy.")


def success_by_cover(c):
    t = c.groupby("stock_cover_band").agg(success_rate=("success_flag", "mean"), stockout=("stockout_rate", "mean"), n=("campaign_id", "count")).reindex(COVER_ORDER).reset_index()
    return t, explain(
        "Success rate and average stockout rate for campaigns grouped by stock cover ratio band.",
        f"Success rate climbs from {pct(t['success_rate'].iloc[0])} when stock covers under 60% of upper-bound demand to {pct(t[t['stock_cover_band'] == '1.0-1.2']['success_rate'].iloc[0])} at 1.0-1.2. Above 1.2 it does not improve further ({pct(t['success_rate'].iloc[-1])}).",
        "There is an optimum: enough stock to cover the upper bound, but no more. Extra cover only ties up working capital (BRL-005 / BRL-013).")


def segment_discount_heatmap(c):
    p = c.pivot_table(index="target_segment", columns="discount_band", values="success_flag", aggfunc="mean").reindex(index=SEG_ORDER, columns=DISC_ORDER)
    n = c.pivot_table(index="target_segment", columns="discount_band", values="success_flag", aggfunc="count").reindex(index=SEG_ORDER, columns=DISC_ORDER)
    ds = c[c["target_segment"] == "Discount Seekers"]
    return (p, n), explain(
        "Success rate for each combination of target segment (rows) and discount band (columns). Darker = more successful.",
        f"Discount Seekers fail in almost every discount band (overall {pct(ds['success_flag'].mean())} success, average CLTV uplift {ds['cltv_uplift_pct'].mean():+.1f}%). For other segments success drops sharply once discounts pass 40%.",
        "Targeting matters as much as the offer. Campaigns aimed at Discount Seekers buy short-term volume but erode long-term value (problem PS-05, rule BRL-014).")


def forecast_accuracy(c):
    df = pd.concat([
        c[["forecast_team", "forecast_error_pct"]].rename(columns={"forecast_team": "source", "forecast_error_pct": "error"}),
        pd.DataFrame({"source": "CIAP model (AI-005)", "error": c["model_forecast_error_pct"]}),
    ])
    s = df.groupby("source")["error"].agg(bias="median", mape=lambda x: x.abs().median()).sort_values("mape")
    mk = s.loc["Marketing"]
    return df, explain(
        "Forecast error = (forecast − actual demand) ÷ actual demand, by who made the forecast. Above zero = over-forecast.",
        f"Each department forecasts differently (problem PS-02). Marketing over-forecasts by a median {pct(mk['bias'])} (typical error {pct(mk['mape'])}). The back-tested CIAP model has a median bias of {pct(s.loc['CIAP model (AI-005)', 'bias'])} and typical error of {pct(s.loc['CIAP model (AI-005)', 'mape'])}.",
        "One shared, unbiased forecast with a prediction range replaces three conflicting ones (BRD Section 6, future state).")


def signoffs_effect(c):
    t = c.groupby("signoffs_count").agg(success_rate=("success_flag", "mean"), stockout=("stockout_rate", "mean"), n=("campaign_id", "count")).reset_index()
    inv = c.groupby("inventory_signoff")["stockout_rate"].mean()
    tc = c.groupby("cycle_time_band").agg(success_rate=("success_flag", "mean"), signoffs=("signoffs_count", "mean")).reindex(CYCLE_ORDER)
    five = t[t["signoffs_count"] == 5]["success_rate"].iloc[0]
    few = c[c["signoffs_count"] <= 3]["success_flag"].mean()
    return (t, tc), explain(
        "Left: success rate by how many of the five departments signed off. Right: success rate by approval cycle time, with the average number of sign-offs in each band.",
        f"Campaigns with all 5 sign-offs succeed {pct(five)} vs {pct(few)} with 3 or fewer. Skipping the Inventory check raises the average stockout rate from {pct(inv['Yes'], 1)} to {pct(inv['No'], 1)}. "
        f"Fast approvals are not better approvals: campaigns decided in under 48 h succeed {pct(tc['success_rate'].iloc[0])} (average {tc['signoffs'].iloc[0]:.1f} sign-offs) vs {pct(tc['success_rate'].iloc[2])} at 72-96 h ({tc['signoffs'].iloc[2]:.1f} sign-offs), because speed was bought by skipping checks.",
        "The manual process forces a choice between fast and thorough. Running all five evaluations in parallel on one data snapshot gives both (FR-014, BR-013).")


def overrides(c):
    t = c.groupby("override_flag").agg(success_rate=("success_flag", "mean"), cm=("contribution_margin", "median"), n=("campaign_id", "count")).reset_index()
    return t, explain(
        "Campaigns launched despite a department objection (override) compared with normal launches.",
        f"{int(t[t['override_flag'] == 'Yes']['n'].iloc[0])} campaigns were overridden. They succeeded {pct(t[t['override_flag'] == 'Yes']['success_rate'].iloc[0])} of the time vs {pct(t[t['override_flag'] == 'No']['success_rate'].iloc[0])} for the rest. Today nobody records why they were overridden.",
        "Overrides should stay possible but be authorised, justified and tracked against outcome (FR-032/033, KPI-21).")


def ciap_backtest(c):
    t = c.groupby("ciap_verdict").agg(campaigns=("campaign_id", "count"), success_rate=("success_flag", "mean"), stockout=("stockout_rate", "mean"),
                                      on_time=("on_time_delivery_rate", "mean"), cm_total=("contribution_margin", "sum"), cltv=("cltv_uplift_pct", "mean")).reindex(VERDICT_ORDER).reset_index()
    blocked = c["ciap_verdict"] == "Not feasible"
    failed = c["success_flag"] == 0
    tp, fp = (blocked & failed).sum(), (blocked & ~failed).sum()
    fn, tn = (~blocked & failed).sum(), (~blocked & ~failed).sum()
    prec, rec = tp / (tp + fp), tp / (tp + fn)
    neg_cm = c[blocked & (c["contribution_margin"] < 0)]["contribution_margin"].sum()
    conf = pd.DataFrame([[tp, fp], [fn, tn]], index=["CIAP: Not feasible", "CIAP: Approve / conditions"], columns=["Actually failed", "Actually succeeded"])
    a = t.set_index("ciap_verdict")
    return (t, conf), explain(
        "Back-test: every historical campaign was replayed through the CIAP gates using only information available before launch, then compared with what actually happened.",
        f"Campaigns CIAP would approve succeeded {pct(a.loc['Approve', 'success_rate'])} of the time; campaigns it would block succeeded only {pct(a.loc['Not feasible', 'success_rate'])}. "
        f"Of the campaigns that failed, CIAP would have caught {pct(rec)} before launch (recall), and {pct(prec)} of its blocks were correct (precision). Blocked campaigns included {money(-neg_cm)} of losses.",
        "This is the key validation of the strategy: the gates separate good from bad campaigns using pre-launch data only. Blocked campaigns are not simply rejected; CIAP proposes feasible alternatives (FR-020), so good ideas can still be recovered.")


def daily_stockout_curve(d, c):
    so = c.set_index("campaign_id")["stockout_rate"]
    dd = d.copy()
    dd["group"] = np.where(dd["campaign_id"].map(so) >= 0.08, "Campaigns that stocked out", "Campaigns with enough stock")
    t = dd[dd["campaign_day"] <= 14].groupby(["group", "campaign_day"]).agg(sell_through=("units_sold", "sum"), demand=("demand_units", "sum"), stocked_out=("stocked_out", "mean")).reset_index()
    t["fill_rate"] = t["sell_through"] / t["demand"]
    s = t[t["group"] == "Campaigns that stocked out"]
    first = s[s["stocked_out"] >= 0.5]["campaign_day"].min()
    return t, explain(
        "Day-by-day fill rate (units sold ÷ units demanded) for the 250 most recent campaigns, split by whether they stocked out.",
        f"Campaigns that stocked out run out early: half of them were empty by day {int(first) if pd.notna(first) else 'n/a'}, so most of the campaign ran with no stock while media spend continued.",
        "Demand is front-loaded (the BRD example puts 40% of volume in week 1), so the stock check must hold on the peak days, not just in total. CIAP checks SKU x location x day (DATA-003).")


# ================================================================== CUSTOMERS
def customer_cltv_by_dependency(u):
    t = u.groupby("discount_dependency")["predicted_cltv"].median().reindex(["Low (<30%)", "Medium (30-60%)", "High (>60%)"])
    return u[["discount_dependency", "predicted_cltv"]], explain(
        "Predicted CLTV of 6,000 campaign-acquired customers, grouped by the share of their orders that used a discount.",
        f"Median CLTV is {money(t.iloc[0])} for low-discount-dependency customers vs {money(t.iloc[-1])} for highly dependent ones ({t.iloc[0] / t.iloc[-1]:.1f}x).",
        "Customers acquired through heavy discounts are worth much less. CLTV, not campaign revenue, should be the north-star measure (BRD guiding principle).")


def first_experience(u):
    b = u.assign(band=pd.cut(u["acq_stockout_rate"], [-0.01, 0.02, 0.08, 0.2, 1], labels=["<2%", "2-8%", "8-20%", ">20%"]).astype(str))
    t = b.groupby("band").agg(orders=("orders_12m", "mean"), churn=("churned", lambda x: (x == "Yes").mean()), n=("customer_id", "count")).reindex(["<2%", "2-8%", "8-20%", ">20%"]).reset_index()
    return t, explain(
        "Customers grouped by the stockout rate of the campaign that acquired them: average orders in the next 12 months and churn rate.",
        f"Customers whose first campaign had under 2% stockouts placed {t['orders'].iloc[0]:.1f} orders a year; those from campaigns with over 20% stockouts placed {t['orders'].iloc[-1]:.1f}, and churn rose from {pct(t['churn'].iloc[0])} to {pct(t['churn'].iloc[-1])}.",
        "A bad first experience teaches new customers that XYZ promotions are unreliable. Operational feasibility is therefore a customer-value issue, not just an operations issue.")


def cltv_by_segment(u):
    t = u.groupby("segment").agg(cltv=("predicted_cltv", "median"), orders=("orders_12m", "mean"), customers=("customer_id", "count"), disc=("discount_order_share", "mean")).reindex(SEG_ORDER).reset_index()
    return t, explain(
        "Median predicted CLTV and average orders per customer by segment.",
        f"Champions are worth {money(t['cltv'].iloc[0])} each vs {money(t[t['segment'] == 'Discount Seekers']['cltv'].iloc[0])} for Discount Seekers, who also use discounts on {pct(t[t['segment'] == 'Discount Seekers']['disc'].iloc[0])} of orders.",
        "Budget should shift toward segments with high CLTV and genuine response (Potential Loyalists, At-Risk win-back) and away from discount-only buyers.")
