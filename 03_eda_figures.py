"""
Step 3b - Static EDA figures for the report
===========================================
Re-draws the dashboard's charts with matplotlib/seaborn (PNG, 200 dpi) and saves each
chart's explanation to outputs/figures/explanations.json, so the report quotes exactly
the numbers the dashboard shows.

Run:  python 03_eda_figures.py
"""
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402
import seaborn as sns  # noqa: E402

import analysis as A  # noqa: E402

FIG = A.OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, AQUA, YELLOW, PINK, GREEN, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
PAL = [BLUE, ORANGE, AQUA, YELLOW, PINK, GREEN, VIOLET, RED]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#e1e0d9", "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 100})
PCT = mt.PercentFormatter(1.0, decimals=0)

c, u, d, LOG, QUAL = A.load()
EXPL = {}


def save(name, fig, e, title):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    EXPL[name] = dict(e, title=title)


# 1 trend
m, e = A.monthly_trend(c)
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(m["quarter"], m["campaigns"], color=BLUE, label="Campaigns")
ax.set_ylabel("Campaigns launched")
ax2 = ax.twinx()
ax2.plot(m["quarter"], m["success_rate"], color=ORANGE, marker="o", lw=2, label="Success rate")
ax2.set_ylim(0, 1); ax2.yaxis.set_major_formatter(PCT); ax2.set_ylabel("Success rate"); ax2.grid(False)
ax.tick_params(axis="x", rotation=45)
fig.legend(loc="upper left", bbox_to_anchor=(0.07, 0.95), frameon=False)
ax.set_title("Campaigns per quarter and success rate")
save("01_trend", fig, e, "Campaign volume and success rate over time")

# 2 by type
t, e = A.by_type(c)
fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(t["campaign_type"], t["success_rate"], color=BLUE)
for y, (v, n) in enumerate(zip(t["success_rate"], t["campaigns"])):
    ax.text(v + 0.01, y, f"{v:.0%}  (n={n})", va="center", fontsize=9)
ax.xaxis.set_major_formatter(PCT); ax.set_xlim(0, 0.85); ax.set_title("Success rate by campaign type")
save("02_by_type", fig, e, "Success rate by campaign type")

# 3 ROI distribution
s, e = A.metric_distribution(c, "roi")
fig, ax = plt.subplots(figsize=(8, 4))
clip = c[c["roi"].between(c["roi"].quantile(0.01), c["roi"].quantile(0.99))]
for lab, col in [("Met objectives", BLUE), ("Missed objectives", ORANGE)]:
    ax.hist(clip[clip["campaign_success"] == lab]["roi"], bins=45, alpha=0.7, color=col, label=lab)
ax.axvline(s.median(), color="#222", ls="--", lw=1); ax.text(s.median(), ax.get_ylim()[1] * 0.92, f"  median {s.median():.2f}", fontsize=9)
ax.axvline(0, color=RED, lw=1)
ax.set_xlabel("ROI = incremental margin ÷ (media + discount cost)"); ax.set_ylabel("Campaigns"); ax.legend(frameon=False); ax.set_title("Distribution of campaign ROI (1st-99th percentile)")
save("03_roi_distribution", fig, e, "Distribution of campaign ROI")

# 4 discount by type
_, e = A.discount_by_type(c)
order = c.groupby("campaign_type")["discount_pct"].median().sort_values().index
fig, ax = plt.subplots(figsize=(9, 4))
sns.boxplot(data=c, x="campaign_type", y="discount_pct", order=order, color="#b7d3f6", ax=ax, fliersize=2, linecolor=BLUE)
ax.yaxis.set_major_formatter(PCT); ax.set_xlabel(""); ax.set_ylabel("Discount depth"); ax.tick_params(axis="x", rotation=20); ax.set_title("Discount depth by campaign type")
save("04_discount_by_type", fig, e, "Discount depth by campaign type")

# 5 cycle time
_, e = A.cycle_time(c)
fig, ax = plt.subplots(figsize=(9, 4))
cols5 = sns.color_palette("Blues", 6)[1:]
ax.hist([c[c["signoffs_count"] == k]["approval_cycle_hours"] for k in range(1, 6)], bins=30, stacked=True, color=cols5, label=[f"{k} sign-off{'s' if k > 1 else ''}" for k in range(1, 6)])
ax.axvline(96, color=RED, ls="--"); ax.text(97, ax.get_ylim()[1] * 0.9, "4 days", color=RED, fontsize=9)
ax.set_xlabel("Approval cycle time (hours)"); ax.set_ylabel("Campaigns"); ax.legend(frameon=False, ncol=5, fontsize=8, loc="upper right"); ax.set_title("Approval cycle time by number of departments that signed off")
save("05_cycle_time", fig, e, "Approval cycle time")

# 6 correlation heatmap
mtx, e = A.corr_matrix(c, "pearson")
fig, ax = plt.subplots(figsize=(11, 9))
mask = np.triu(np.ones_like(mtx, dtype=bool), 1)
sns.heatmap(mtx, mask=mask, annot=True, fmt=".2f", cmap="RdBu", vmin=-1, vmax=1, center=0, square=True, linewidths=0.5, cbar_kws={"shrink": 0.7}, annot_kws={"size": 8}, ax=ax)
ax.set_title("Pearson correlation matrix of campaign variables")
save("06_correlation_heatmap", fig, e, "Correlation matrix")

# 6b spearman (saved for appendix)
mtx_s, e_s = A.corr_matrix(c, "spearman")
EXPL["06b_spearman"] = dict(e_s, title="Spearman correlation (robustness check)")

# 7 success drivers
s, e = A.success_drivers(c)
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(s.index, s.values, color=[BLUE if v >= 0 else ORANGE for v in s.values])
for y, v in enumerate(s.values):
    ax.text(v + (0.01 if v >= 0 else -0.01), y, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)
ax.axvline(0, color="#222", lw=0.8); ax.set_xlim(-0.7, 0.8); ax.set_title("Correlation with campaign success (1 = met objectives)")
save("07_success_drivers", fig, e, "What correlates with success")

# 8 discount vs demand
df, e = A.discount_uplift(c)
fig, ax = plt.subplots(figsize=(9, 5))
for i, sg in enumerate(A.SEG_ORDER):
    g = df[df["target_segment"] == sg]
    ax.scatter(g["discount_pct"], g["units_per_day"], s=10, alpha=0.5, color=PAL[i], label=sg)
b1, b0 = np.polyfit(df["discount_pct"], np.log(df["units_per_day"]), 1)
xs = np.linspace(0, df["discount_pct"].max(), 50)
ax.plot(xs, np.exp(b0 + b1 * xs), color="#222", ls="--", lw=1.5, label="Overall log-linear trend")
ax.set_yscale("log"); ax.xaxis.set_major_formatter(PCT); ax.set_xlabel("Discount depth"); ax.set_ylabel("Demand per day (log scale)")
ax.legend(frameon=False, fontsize=8, ncol=2); ax.set_title("Discount depth vs demand per day")
save("08_discount_vs_demand", fig, e, "Discount depth vs demand")

# 9 stock cover vs stockout
df, e = A.stock_vs_stockout(c)
fig, ax = plt.subplots(figsize=(9, 5))
for lab, col in [("Met objectives", BLUE), ("Missed objectives", ORANGE)]:
    g = df[df["campaign_success"] == lab]
    ax.scatter(g["stock_cover_ratio"], g["stockout_rate"], s=10, alpha=0.5, color=col, label=lab)
ax.axvline(1.0, color=RED, ls="--"); ax.text(1.02, 0.6, "CIAP gate BRL-003\nstock ≥ upper-bound forecast", color=RED, fontsize=9)
ax.set_xlim(0, 2.5); ax.yaxis.set_major_formatter(PCT); ax.set_xlabel("Stock cover ratio (stock ÷ upper-bound forecast)"); ax.set_ylabel("Stockout rate"); ax.legend(frameon=False)
ax.set_title("Stock cover ratio vs stockout rate")
save("09_stock_vs_stockout", fig, e, "Stock cover vs stockouts")

# 10 rider vs on-time
df, e = A.rider_vs_ontime(c)
fig, ax = plt.subplots(figsize=(9, 5))
for i, rg in enumerate(sorted(df["region_scope"].unique())):
    g = df[df["region_scope"] == rg]
    ax.scatter(g["peak_rider_utilisation"], g["on_time_delivery_rate"], s=10, alpha=0.5, color=PAL[i], label=rg)
ax.axvline(1.0, color=RED, ls="--"); ax.axvline(0.9, color="#888", ls=":")
ax.text(1.01, 0.66, "capacity", color=RED, fontsize=9); ax.text(0.78, 0.66, "10% buffer", color="#666", fontsize=9)
ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT); ax.set_xlabel("Peak-day rider utilisation"); ax.set_ylabel("On-time delivery rate"); ax.legend(frameon=False)
ax.set_title("Rider utilisation vs on-time delivery")
save("10_rider_vs_ontime", fig, e, "Rider capacity vs on-time delivery")

# 11 experience vs loyalty
t, e = A.experience_vs_loyalty(c)
fig, ax = plt.subplots(figsize=(9, 4.5))
x = np.arange(len(t)); w = 0.38
ax.bar(x - w / 2, t["repeat"] * 100, w, color=BLUE, label="Repeat rate 90d (%)")
ax.bar(x + w / 2, t["cltv"], w, color=ORANGE, label="CLTV uplift (pp)")
ax.axhline(0, color="#222", lw=0.8)
ax2 = ax.twinx(); ax2.plot(x, t["csat"], color=GREEN, marker="o", lw=2, label="CSAT (right axis)"); ax2.set_ylim(1, 5); ax2.grid(False); ax2.set_ylabel("CSAT (1-5)")
ax.set_xticks(x, t["stockout_band"]); ax.set_xlabel("Stockout rate band"); fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.92), frameon=False, fontsize=8)
ax.set_title("Stockouts vs customer outcomes")
save("11_stockout_vs_loyalty", fig, e, "Stockouts vs customer outcomes")

# 12 pareto
f, e = A.failure_pareto(c)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(f["reason"], f["campaigns"], color=ORANGE)
ax2 = ax.twinx(); ax2.plot(f["reason"], f["cum_share"], color=BLUE, marker="o", lw=2); ax2.set_ylim(0, 1.05); ax2.yaxis.set_major_formatter(PCT); ax2.grid(False)
for i, v in enumerate(f["campaigns"]):
    ax.text(i, v + 3, str(v), ha="center", fontsize=9)
ax.set_ylabel("Failed campaigns"); ax2.set_ylabel("Cumulative share"); ax.set_title("Why campaigns fail: primary failure reason (Pareto)")
save("12_failure_pareto", fig, e, "Failure root causes")

# 13 cover band
t, e = A.success_by_cover(c)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(t["stock_cover_band"], t["success_rate"], color=BLUE, label="Success rate")
ax.plot(t["stock_cover_band"], t["stockout"], color=ORANGE, marker="o", lw=2, label="Avg stockout rate")
for i, (v, n) in enumerate(zip(t["success_rate"], t["n"])):
    ax.text(i, v + 0.02, f"{v:.0%}\nn={n}", ha="center", fontsize=8)
ax.yaxis.set_major_formatter(PCT); ax.set_ylim(0, 0.85); ax.set_xlabel("Stock cover ratio band"); ax.legend(frameon=False); ax.set_title("Success and stockouts by stock cover band")
save("13_success_by_cover", fig, e, "Success by stock cover")

# 14 segment x discount heatmap
(p, n), e = A.segment_discount_heatmap(c)
fig, ax = plt.subplots(figsize=(8, 4.5))
annot = p.map(lambda v: "" if pd.isna(v) else f"{v:.0%}") + n.map(lambda v: "" if pd.isna(v) or v == 0 else f"\nn={int(v)}")
sns.heatmap(p, annot=annot, fmt="", cmap="Blues", vmin=0, vmax=1, linewidths=0.5, cbar_kws={"format": PCT}, annot_kws={"size": 8}, ax=ax)
ax.set_xlabel("Discount band"); ax.set_ylabel(""); ax.set_title("Success rate by target segment × discount band")
save("14_segment_discount", fig, e, "Segment × discount diagnostic")

# 15 forecast accuracy
df, e = A.forecast_accuracy(c)
fig, ax = plt.subplots(figsize=(8, 4.5))
order = ["CIAP model (AI-005)", "Inventory", "Finance", "Marketing", "Unknown"]
sns.boxplot(data=df, x="source", y="error", order=order, color="#b7d3f6", linecolor=BLUE, showfliers=False, ax=ax)
ax.axhline(0, color=RED, ls="--", lw=1); ax.yaxis.set_major_formatter(PCT); ax.set_xlabel(""); ax.set_ylabel("Forecast error (+ = over-forecast)")
ax.set_title("Forecast error by forecaster")
save("15_forecast_accuracy", fig, e, "Forecast accuracy by team")

# 16 signoffs
(t, tc), e = A.signoffs_effect(c)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
a1.bar(t["signoffs_count"].astype(str), t["success_rate"], color=BLUE)
for i, v in enumerate(t["success_rate"]):
    a1.text(i, v + 0.01, f"{v:.0%}", ha="center", fontsize=9)
a1.yaxis.set_major_formatter(PCT); a1.set_xlabel("Departments that signed off"); a1.set_title("Success by sign-offs")
a2.bar(tc.index, tc["success_rate"], color=AQUA)
for i, (v, s_) in enumerate(zip(tc["success_rate"], tc["signoffs"])):
    a2.text(i, v + 0.01, f"{v:.0%}\n{s_:.1f} sign-offs", ha="center", fontsize=8)
a2.yaxis.set_major_formatter(PCT); a2.set_ylim(0, 0.8); a2.set_xlabel("Approval cycle time"); a2.set_title("Success by approval time")
save("16_signoffs", fig, e, "Sign-offs and approval time")

# 17 overrides
t, e = A.overrides(c)
fig, ax = plt.subplots(figsize=(6, 4))
ax.bar(t["override_flag"].map({"No": "Normal launch", "Yes": "Overridden"}), t["success_rate"], color=[BLUE if x == "No" else ORANGE for x in t["override_flag"]])
for i, (v, nn) in enumerate(zip(t["success_rate"], t["n"])):
    ax.text(i, v + 0.01, f"{v:.0%} (n={nn})", ha="center")
ax.yaxis.set_major_formatter(PCT); ax.set_ylim(0, 0.7); ax.set_title("Success rate: overridden vs normal launches")
save("17_overrides", fig, e, "Overrides")

# 18 daily fill rate
t, e = A.daily_stockout_curve(d, c)
fig, ax = plt.subplots(figsize=(9, 4))
for i, (g, gg) in enumerate(t.groupby("group")):
    ax.plot(gg["campaign_day"], gg["fill_rate"], marker="o", lw=2, color=[ORANGE, BLUE][i], label=g)
ax.yaxis.set_major_formatter(PCT); ax.set_xlabel("Campaign day"); ax.set_ylabel("Fill rate (sold ÷ demanded)"); ax.legend(frameon=False); ax.set_title("Fill rate by campaign day")
save("18_daily_fill_rate", fig, e, "When stock runs out")

# 19 customers dependency
_, e = A.customer_cltv_by_dependency(u)
fig, ax = plt.subplots(figsize=(7, 4))
sns.boxplot(data=u, x="discount_dependency", y="predicted_cltv", order=["Low (<30%)", "Medium (30-60%)", "High (>60%)"], color="#b7d3f6", linecolor=BLUE, showfliers=False, ax=ax)
ax.set_xlabel("Share of orders using a discount"); ax.set_ylabel("Predicted CLTV ($)"); ax.set_title("Predicted CLTV by discount dependency")
save("19_cltv_dependency", fig, e, "Discount dependency vs CLTV")

# 20 first experience
t, e = A.first_experience(u)
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(t["band"], t["orders"], color=BLUE, label="Orders in next 12 months")
ax2 = ax.twinx(); ax2.plot(t["band"], t["churn"], color=ORANGE, marker="o", lw=2, label="Churn rate"); ax2.yaxis.set_major_formatter(PCT); ax2.set_ylim(0, 1); ax2.grid(False)
ax.set_xlabel("Stockout rate of the campaign that acquired the customer"); ax.set_ylabel("Avg orders"); fig.legend(loc="upper right", bbox_to_anchor=(0.88, 0.92), frameon=False, fontsize=8)
ax.set_title("First campaign experience vs later loyalty")
save("20_first_experience", fig, e, "First experience vs loyalty")

# 21 cltv by segment
t, e = A.cltv_by_segment(u)
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(t["segment"], t["cltv"], color=BLUE)
for i, v in enumerate(t["cltv"]):
    ax.text(i, v + 5, A.money(v), ha="center", fontsize=9)
ax.set_ylabel("Median predicted CLTV ($)"); ax.tick_params(axis="x", rotation=15); ax.set_title("Median predicted CLTV by segment")
save("21_cltv_segment", fig, e, "CLTV by segment")

# 22 CIAP back-test
(t, conf), e = A.ciap_backtest(c)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.5, 1]})
x = np.arange(len(t)); w = 0.38
a1.bar(x - w / 2, t["success_rate"], w, color=BLUE, label="Actual success rate")
a1.bar(x + w / 2, t["stockout"], w, color=ORANGE, label="Avg stockout rate")
for i, (v, nn) in enumerate(zip(t["success_rate"], t["campaigns"])):
    a1.text(i - w / 2, v + 0.01, f"{v:.0%}\nn={nn}", ha="center", fontsize=8)
a1.set_xticks(x, ["Approve", "Conditions /\nescalate", "Not feasible"]); a1.yaxis.set_major_formatter(PCT); a1.set_ylim(0, 0.95); a1.legend(frameon=False, fontsize=8)
a1.set_title("Actual outcome by CIAP verdict")
sns.heatmap(conf, annot=True, fmt="d", cmap="Blues", cbar=False, ax=a2, annot_kws={"size": 12})
a2.set_title("Confusion matrix"); a2.tick_params(axis="y", rotation=0)
save("22_ciap_backtest", fig, e, "CIAP back-test")

# 23 cleaning summary
fig, ax = plt.subplots(figsize=(9, 4.5))
g = LOG[LOG["rows_affected"] > 0].groupby(["step", "dataset"])["rows_affected"].sum().unstack(fill_value=0)
g = g[~g.index.str.startswith("10")]
g.plot.barh(stacked=True, color=[BLUE, ORANGE, AQUA][: g.shape[1]], ax=ax)
ax.set_xlabel("Rows fixed"); ax.set_ylabel(""); ax.legend(frameon=False); ax.set_title("Rows fixed by each cleaning step")
save("00_cleaning", fig, A.explain("Rows affected by each cleaning step.", "", ""), "Cleaning summary")

(A.OUT / "figures" / "explanations.json").write_text(json.dumps(EXPL, indent=2))
print(f"Saved {len(list(FIG.glob('*.png')))} figures to {FIG}")
