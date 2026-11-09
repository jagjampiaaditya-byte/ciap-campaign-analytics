"""
Step 3 - Descriptive & diagnostic analytics dashboard (Streamlit)
=================================================================
Run:  streamlit run app.py
Every chart is followed by an explanation box (what it shows / insight / business
implication). The numbers in the boxes are recalculated from whatever the sidebar
filters select.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analysis as A

st.set_page_config(page_title="XYZ CIAP · Campaign Analytics", page_icon="📊", layout="wide")

BLUE, ORANGE, AQUA, YELLOW, PINK, GREEN, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
SEQ = px.colors.sequential.Blues
SUCCESS_COLORS = {"Met objectives": BLUE, "Missed objectives": ORANGE}
px.defaults.template = "simple_white"
px.defaults.color_discrete_sequence = [BLUE, ORANGE, AQUA, YELLOW, PINK, GREEN, VIOLET, RED]


@st.cache_data
def data():
    return A.load()


c_all, u_all, d_all, LOG, QUAL = data()


def explain_box(e):
    with st.container(border=True):
        st.markdown(f"**What it shows:** {e['what']}  \n**Insight:** {e['insight']}  \n**Business implication:** {e['action']}")


def safe(fn):
    try:
        fn()
    except Exception as ex:  # small filtered samples can make a chart meaningless
        st.warning(f"Not enough data for this chart with the current filters ({type(ex).__name__}). Widen the filters.")


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), font=dict(size=13))
    return fig


# ------------------------------------------------------------------ sidebar filters
st.sidebar.title("Filters")
years = sorted(c_all["launch_year"].unique())
yr = st.sidebar.select_slider("Launch year", options=years, value=(years[0], years[-1]))
types = st.sidebar.multiselect("Campaign type", sorted(c_all["campaign_type"].unique()), default=sorted(c_all["campaign_type"].unique()))
segs = st.sidebar.multiselect("Target segment", A.SEG_ORDER, default=A.SEG_ORDER)
cats = st.sidebar.multiselect("Category", sorted(c_all["category"].unique()), default=sorted(c_all["category"].unique()))
regs = st.sidebar.multiselect("Region scope", sorted(c_all["region_scope"].unique()), default=sorted(c_all["region_scope"].unique()))
c = c_all[c_all["launch_year"].between(*yr) & c_all["campaign_type"].isin(types) & c_all["target_segment"].isin(segs) & c_all["category"].isin(cats) & c_all["region_scope"].isin(regs)]
u = u_all[u_all["acquisition_campaign_id"].isin(c["campaign_id"])]
d = d_all[d_all["campaign_id"].isin(c["campaign_id"])]
st.sidebar.caption(f"{len(c):,} of {len(c_all):,} campaigns · {len(u):,} customers · {len(d):,} campaign-days selected")
st.sidebar.markdown("---")
st.sidebar.caption("Synthetic data generated for the XYZ CIAP business case (see report). Data → `01_generate_synthetic_data.py`, cleaning → `02_clean_transform.py`.")

if len(c) < 30:
    st.error("Fewer than 30 campaigns match the filters. Please widen them.")
    st.stop()

st.title("XYZ Campaign Intelligence & Approval Platform — Campaign Analytics")
st.caption("Business question: would a data-driven, gated approval process (CIAP) launch better campaigns than XYZ's manual, department-by-department sign-off? "
           "Descriptive analytics show what happened; diagnostic analytics show why.")

tabs = st.tabs(["1 · Overview", "2 · Data & cleaning", "3 · Descriptive", "4 · Correlation", "5 · Diagnostic", "6 · Customers", "7 · CIAP back-test", "8 · Data explorer"])

# ================================================================== 1. OVERVIEW
with tabs[0]:
    k = A.kpis(c)
    items = list(k.items())
    for i in range(0, len(items), 3):          # 3 KPIs per row so labels stay readable
        for col, (name, val) in zip(st.columns(3), items[i:i + 3]):
            col.metric(name, val)
    st.markdown("#### The business problem in four numbers")
    bt, _ = A.ciap_backtest(c)
    t, conf = bt
    a = t.set_index("ciap_verdict")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Campaigns that missed objectives", A.pct(1 - c["success_flag"].mean()))
    m2.metric("Launched with stock below forecast upper bound", A.pct((c["stock_cover_ratio"] < 1).mean()))
    m3.metric("Success if CIAP would approve", A.pct(a.loc["Approve", "success_rate"]))
    m4.metric("Success if CIAP would block", A.pct(a.loc["Not feasible", "success_rate"]))
    with st.container(border=True):
        st.markdown(
            "**How to read this dashboard.** Tabs 3-4 describe the campaign history (*what happened*). Tab 5 diagnoses failures (*why it happened*). "
            "Tab 6 links campaign experience to long-term customer value (CLTV). Tab 7 replays every campaign through the CIAP rules to test the strategy. "
            "Use the sidebar to filter; every explanation updates with the filtered data.")
    safe(lambda: st.plotly_chart(style(px.pie(c, names="failure_reason", hole=0.55, title="Outcome of every campaign",
                                              color="failure_reason", color_discrete_map={"Success": BLUE, "Stockout": ORANGE, "CLTV erosion": PINK, "Loss-making": RED, "Late delivery": YELLOW, "Other / mixed": "#999"})), width="stretch"))

# ================================================================== 2. DATA & CLEANING
with tabs[1]:
    st.subheader("Datasets")
    st.markdown("""
| Dataset | Grain | Why it is needed |
|---|---|---|
| `campaigns` | one row per campaign (1,500, 2023-2026) | design, approval process, forecast, stock, capacity, financial and customer outcomes |
| `customers` | one row per acquired customer (6,000) | links a campaign's experience to 12-month behaviour and predicted CLTV |
| `campaign_daily` | one row per campaign-day (250 recent campaigns) | shows *when* stock runs out inside a campaign |
""")
    st.subheader("Data quality: before vs after cleaning")
    st.dataframe(QUAL, width="stretch", hide_index=True)
    st.subheader("Cleaning log (every fix, with rows affected)")
    st.dataframe(LOG, width="stretch", hide_index=True)
    fig = px.bar(LOG[LOG["rows_affected"] > 0].groupby(["dataset", "step"], as_index=False)["rows_affected"].sum(), x="rows_affected", y="step", color="dataset", orientation="h", title="Rows fixed by cleaning step")
    st.plotly_chart(style(fig, 420), width="stretch")
    explain_box(A.explain("Rows affected by each cleaning step, by dataset.",
                          f"{int(LOG[LOG['step'].str.startswith(('2', '3', '4', '5', '6', '7', '8'))]['rows_affected'].sum()):,} cell/row fixes were made. The biggest issues were inconsistent labels, mixed date formats and text-formatted numbers, which are typical of exports from separate departmental tools.",
                          "Inconsistent data across departments is problem PS-02 in the BRD. CIAP's single canonical data model (DATA-001) and data-quality rules (DATA-005) prevent it at the source."))

# ================================================================== 3. DESCRIPTIVE
with tabs[2]:
    st.subheader("Descriptive statistics")
    num = c[["discount_pct", "budget", "units_sold", "stock_cover_ratio", "approval_cycle_hours", "stockout_rate", "on_time_delivery_rate", "csat_score", "repeat_rate_90d", "cltv_uplift_pct", "cm_margin_pct", "roi"]]
    st.dataframe(num.describe().T.assign(skew=num.skew(), missing=num.isna().sum()).round(3), width="stretch")

    l, r = st.columns(2)
    with l:
        def _trend():
            m, e = A.monthly_trend(c)
            fig = go.Figure()
            fig.add_bar(x=m["quarter"], y=m["campaigns"], name="Campaigns", marker_color=BLUE)
            fig.add_scatter(x=m["quarter"], y=m["success_rate"] * 100, name="Success rate %", yaxis="y2", line=dict(color=ORANGE, width=2), mode="lines+markers")
            fig.update_layout(title="Campaigns per quarter and success rate", yaxis=dict(title="Campaigns"), yaxis2=dict(title="Success %", overlaying="y", side="right", range=[0, 100]))
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_trend)
    with r:
        def _type():
            t, e = A.by_type(c)
            fig = px.bar(t, x="success_rate", y="campaign_type", orientation="h", text=t["success_rate"].map(A.pct), hover_data=["campaigns", "avg_discount", "avg_stockout"], title="Success rate by campaign type")
            fig.update_traces(marker_color=BLUE); fig.update_xaxes(tickformat=".0%", title="Success rate")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_type)
    l, r = st.columns(2)
    with l:
        def _dist():
            col = st.selectbox("Metric", ["roi", "cm_margin_pct", "cltv_uplift_pct", "stockout_rate", "csat_score"], format_func=lambda x: A.CORR_VARS.get(x, x))
            s, e = A.metric_distribution(c, col)
            fig = px.histogram(c, x=col, color="campaign_success", nbins=50, barmode="overlay", opacity=0.75, color_discrete_map=SUCCESS_COLORS, title=f"Distribution of {A.CORR_VARS.get(col, col)}")
            fig.add_vline(s.median(), line_dash="dash", annotation_text="median")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_dist)
    with r:
        def _disc():
            _, e = A.discount_by_type(c)
            fig = px.box(c, x="campaign_type", y="discount_pct", title="Discount depth by campaign type", points=False)
            fig.update_traces(marker_color=BLUE, line_color=BLUE); fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_disc)
    def _cycle():
        _, e = A.cycle_time(c)
        fig = px.histogram(c, x="approval_cycle_hours", color=c["signoffs_count"].astype(str), nbins=40, title="Approval cycle time (hours) by number of departments that signed off",
                           category_orders={"color": ["1", "2", "3", "4", "5"]}, color_discrete_sequence=SEQ[3:])
        fig.update_layout(legend_title_text="Sign-offs")
        st.plotly_chart(style(fig), width="stretch"); explain_box(e)
    safe(_cycle)

# ================================================================== 4. CORRELATION
with tabs[3]:
    method = st.radio("Correlation method", ["pearson", "spearman"], horizontal=True, help="Pearson = linear relationships; Spearman = rank-based, robust to outliers and curved (monotonic) relationships.")
    l, r = st.container(), st.container()     # stacked: the matrix needs the full width to stay readable
    with l:
        def _heat():
            m, e = A.corr_matrix(c, method)
            fig = px.imshow(m, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto", title=f"{method.title()} correlation matrix")
            st.plotly_chart(style(fig, 640), width="stretch"); explain_box(e)
        safe(_heat)
    with r:
        def _drv():
            s, e = A.success_drivers(c)
            fig = px.bar(x=s.values, y=s.index, orientation="h", title="Correlation with campaign success", color=np.where(s.values >= 0, "Positive", "Negative"),
                         color_discrete_map={"Positive": BLUE, "Negative": ORANGE})
            fig.update_layout(showlegend=False, xaxis_title="correlation", yaxis_title="")
            st.plotly_chart(style(fig, 640), width="stretch"); explain_box(e)
        safe(_drv)
    l, r = st.columns(2)
    with l:
        def _up():
            df, e = A.discount_uplift(c)
            fig = px.scatter(df, x="discount_pct", y="units_per_day", color="target_segment", log_y=True, opacity=0.6,
                             title="Discount depth vs demand per day", category_orders={"target_segment": A.SEG_ORDER})
            b1, b0 = np.polyfit(df["discount_pct"], np.log(df["units_per_day"]), 1)   # log-linear trend line
            xs = np.linspace(df["discount_pct"].min(), df["discount_pct"].max(), 50)
            fig.add_scatter(x=xs, y=np.exp(b0 + b1 * xs), mode="lines", name="Overall trend", line=dict(color="#222", dash="dash"))
            fig.update_xaxes(tickformat=".0%")
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_up)
    with r:
        def _sc():
            df, e = A.stock_vs_stockout(c)
            fig = px.scatter(df, x="stock_cover_ratio", y="stockout_rate", color="campaign_success", opacity=0.6, color_discrete_map=SUCCESS_COLORS, title="Stock cover ratio vs stockout rate", range_x=[0, 2.5])
            fig.add_vline(1.0, line_dash="dash", line_color=RED, annotation_text="CIAP gate BRL-003 = 1.0")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_sc)
    l, r = st.columns(2)
    with l:
        def _rid():
            df, e = A.rider_vs_ontime(c)
            fig = px.scatter(df, x="peak_rider_utilisation", y="on_time_delivery_rate", color="region_scope", opacity=0.6, title="Peak rider utilisation vs on-time delivery")
            fig.add_vline(1.0, line_dash="dash", line_color=RED, annotation_text="capacity"); fig.add_vline(0.9, line_dash="dot", annotation_text="buffer")
            fig.update_xaxes(tickformat=".0%"); fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_rid)
    with r:
        def _exp():
            t, e = A.experience_vs_loyalty(c)
            fig = go.Figure()
            fig.add_bar(x=t["stockout_band"], y=t["repeat"] * 100, name="Repeat rate 90d (%)", marker_color=BLUE)
            fig.add_bar(x=t["stockout_band"], y=t["cltv"], name="CLTV uplift (%)", marker_color=ORANGE)
            fig.add_scatter(x=t["stockout_band"], y=t["csat"], name="CSAT (1-5)", yaxis="y2", line=dict(color=GREEN, width=2), mode="lines+markers")
            fig.update_layout(title="Stockouts vs customer outcomes", barmode="group", xaxis_title="Stockout rate band", yaxis2=dict(overlaying="y", side="right", range=[1, 5], title="CSAT"))
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_exp)

# ================================================================== 5. DIAGNOSTIC
with tabs[4]:
    l, r = st.columns(2)
    with l:
        def _par():
            f, e = A.failure_pareto(c)
            fig = go.Figure()
            fig.add_bar(x=f["reason"], y=f["campaigns"], name="Failed campaigns", marker_color=ORANGE)
            fig.add_scatter(x=f["reason"], y=f["cum_share"] * 100, name="Cumulative %", yaxis="y2", line=dict(color=BLUE, width=2), mode="lines+markers")
            fig.update_layout(title="Why campaigns fail (Pareto)", yaxis2=dict(overlaying="y", side="right", range=[0, 105], title="Cumulative %"))
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_par)
    with r:
        def _cov():
            t, e = A.success_by_cover(c)
            fig = go.Figure()
            fig.add_bar(x=t["stock_cover_band"], y=t["success_rate"] * 100, name="Success rate %", marker_color=BLUE, text=t["n"].map(lambda n: f"n={n}"), textposition="outside")
            fig.add_scatter(x=t["stock_cover_band"], y=t["stockout"] * 100, name="Avg stockout %", line=dict(color=ORANGE, width=2), mode="lines+markers")
            fig.update_layout(title="Success and stockouts by stock cover band", xaxis_title="Stock ÷ upper-bound forecast", yaxis_title="%")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_cov)
    l, r = st.columns(2)
    with l:
        def _hm():
            (p, n), e = A.segment_discount_heatmap(c)
            fig = px.imshow(p * 100, text_auto=".0f", color_continuous_scale="Blues", zmin=0, zmax=100, aspect="auto", title="Success rate % by segment × discount band")
            fig.update_traces(customdata=n.values, hovertemplate="%{y} · %{x}<br>success %{z:.0f}%<br>n=%{customdata}<extra></extra>")
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_hm)
    with r:
        def _fc():
            df, e = A.forecast_accuracy(c)
            fig = px.box(df, x="source", y="error", points=False, title="Forecast error by forecaster", category_orders={"source": ["CIAP model (AI-005)", "Inventory", "Finance", "Marketing", "Unknown"]})
            fig.add_hline(0, line_dash="dash"); fig.update_traces(marker_color=BLUE, line_color=BLUE); fig.update_yaxes(tickformat=".0%", range=[-0.8, 1.2])
            st.plotly_chart(style(fig, 420), width="stretch"); explain_box(e)
        safe(_fc)
    def _sign():
        (t, tc), e = A.signoffs_effect(c)
        l2, r2 = st.columns(2)
        f1 = px.bar(t, x="signoffs_count", y="success_rate", text=t["success_rate"].map(A.pct), title="Success rate by departments signed off", hover_data=["n", "stockout"])
        f1.update_traces(marker_color=BLUE); f1.update_yaxes(tickformat=".0%"); f1.update_xaxes(dtick=1)
        f2 = px.bar(tc.reset_index(), x="cycle_time_band", y="success_rate", text=tc["success_rate"].map(A.pct).values, title="Success rate by approval cycle time", hover_data=["signoffs"])
        f2.update_traces(marker_color=AQUA); f2.update_yaxes(tickformat=".0%")
        l2.plotly_chart(style(f1), width="stretch"); r2.plotly_chart(style(f2), width="stretch")
        explain_box(e)
    safe(_sign)
    l, r = st.columns(2)
    with l:
        def _ov():
            t, e = A.overrides(c)
            fig = px.bar(t, x="override_flag", y="success_rate", text=t["success_rate"].map(A.pct), title="Success rate: overridden vs normal launches", hover_data=["n", "cm"])
            fig.update_traces(marker_color=[ORANGE if x == "Yes" else BLUE for x in t["override_flag"]]); fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_ov)
    with r:
        def _daily():
            t, e = A.daily_stockout_curve(d, c)
            fig = px.line(t, x="campaign_day", y="fill_rate", color="group", markers=True, title="Fill rate by campaign day", color_discrete_sequence=[BLUE, ORANGE])
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_daily)

# ================================================================== 6. CUSTOMERS
with tabs[5]:
    if len(u) < 50:
        st.warning("Too few customers for the selected campaigns.")
    else:
        l, r = st.columns(2)
        with l:
            def _dep():
                _, e = A.customer_cltv_by_dependency(u)
                fig = px.box(u, x="discount_dependency", y="predicted_cltv", points=False, log_y=True, title="Predicted CLTV by discount dependency",
                             category_orders={"discount_dependency": ["Low (<30%)", "Medium (30-60%)", "High (>60%)"]})
                fig.update_traces(marker_color=BLUE, line_color=BLUE)
                st.plotly_chart(style(fig), width="stretch"); explain_box(e)
            safe(_dep)
        with r:
            def _fx():
                t, e = A.first_experience(u)
                fig = go.Figure()
                fig.add_bar(x=t["band"], y=t["orders"], name="Orders in 12 months", marker_color=BLUE)
                fig.add_scatter(x=t["band"], y=t["churn"] * 100, name="Churn %", yaxis="y2", line=dict(color=ORANGE, width=2), mode="lines+markers")
                fig.update_layout(title="First campaign experience vs loyalty", xaxis_title="Stockout rate of acquiring campaign", yaxis2=dict(overlaying="y", side="right", title="Churn %", range=[0, 100]))
                st.plotly_chart(style(fig), width="stretch"); explain_box(e)
            safe(_fx)
        def _seg():
            t, e = A.cltv_by_segment(u)
            fig = px.bar(t, x="segment", y="cltv", text=t["cltv"].map(A.money), title="Median predicted CLTV by segment", hover_data=["orders", "customers", "disc"])
            fig.update_traces(marker_color=BLUE)
            st.plotly_chart(style(fig), width="stretch"); explain_box(e)
        safe(_seg)
        st.markdown("**Correlation among customer variables**")
        cm = u[["orders_12m", "avg_order_value", "revenue_12m", "discount_order_share", "returns_12m", "days_since_last_order", "predicted_cltv", "acq_discount_pct", "acq_stockout_rate"]].corr()
        st.plotly_chart(style(px.imshow(cm, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto"), 480), width="stretch")
        explain_box(A.explain("Pearson correlation among customer-level variables.",
                              f"Discount share of orders correlates {cm.loc['discount_order_share', 'predicted_cltv']:+.2f} with predicted CLTV, and the stockout rate of the acquiring campaign correlates {cm.loc['acq_stockout_rate', 'orders_12m']:+.2f} with later orders.",
                              "Both levers CIAP controls (discount depth and operational feasibility) are visible in customer value a year later."))

# ================================================================== 7. CIAP BACK-TEST
with tabs[6]:
    (t, conf), e = A.ciap_backtest(c)
    st.markdown("Each historical campaign was re-evaluated with the CIAP rules **using only data available before launch** (CIAP demand model, stock, rider capacity, budget, price and cost).")
    g = c[["gate_inventory_BRL003", "gate_logistics_BRL009", "gate_finance_BRL012", "gate_budget_BRL011", "gate_discount_BRL015"]].melt(var_name="gate", value_name="result")
    fig = px.histogram(g, y="gate", color="result", barmode="stack", title="Gate results across all campaigns",
                       color_discrete_map={"Pass": BLUE, "Condition": YELLOW, "Escalate": PINK, "Hard fail": ORANGE})
    st.plotly_chart(style(fig, 320), width="stretch")
    l, r = st.columns([3, 2])
    with l:
        fig = go.Figure()
        fig.add_bar(x=t["ciap_verdict"], y=t["success_rate"] * 100, name="Success rate %", marker_color=BLUE, text=t["campaigns"].map(lambda n: f"{n} campaigns"), textposition="outside")
        fig.add_bar(x=t["ciap_verdict"], y=t["stockout"] * 100, name="Avg stockout %", marker_color=ORANGE)
        fig.update_layout(title="Actual outcomes by CIAP verdict", barmode="group", yaxis_title="%")
        st.plotly_chart(style(fig), width="stretch")
    with r:
        st.markdown("**Confusion matrix: CIAP verdict vs actual outcome**")
        st.dataframe(conf, width="stretch")
        tp, fp, fn = conf.iloc[0, 0], conf.iloc[0, 1], conf.iloc[1, 0]
        st.metric("Recall (failures caught before launch)", A.pct(tp / (tp + fn)))
        st.metric("Precision (blocks that were right)", A.pct(tp / (tp + fp)))
    explain_box(e)
    st.markdown("#### Strategy recommendations")
    st.markdown(f"""
1. **Make inventory cover a hard launch gate (BRL-003).** {A.pct((c['stock_cover_ratio'] < 1).mean())} of campaigns launched below the forecast upper bound, and stockouts are the #1 failure cause.
2. **Replace departmental forecasts with one model and a prediction range.** Marketing's forecasts are biased upward; the model's median error is about a third lower.
3. **Cap discounts by category and stop discount-led targeting of Discount Seekers.** These campaigns erode CLTV.
4. **Gate rider capacity with a 10% buffer (BRL-009/010).** Deliveries collapse above 100% utilisation.
5. **Run all five evaluations in parallel and auto-approve only the low-risk tier**, after a shadow-mode period, to remove the speed vs thoroughness trade-off.
6. **Record every override with a reason and track its outcome.** Overridden campaigns underperform today.
""")

# ================================================================== 8. EXPLORER
with tabs[7]:
    st.markdown("Filtered clean campaign data. Download it for your own analysis.")
    st.dataframe(c, width="stretch", height=480)
    st.download_button("Download filtered campaigns (CSV)", c.to_csv(index=False).encode(), "campaigns_filtered.csv", "text/csv")
