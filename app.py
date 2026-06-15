# -*- coding: utf-8 -*-
"""世界マネーフロー可視化アプリ

29資産の時系列データと本日のリスクオン/オフ判定を表示する1ページ構成。
- リスクオン/オフメーター(ステップ4再設計)
- 資産別リターン ヒートマップ(ステップ5 タスクA)
- カテゴリ別相対パフォーマンス折れ線(ステップ5 タスクB)
- 期間リターンランキング横棒(ステップ5 タスクC)
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------
# 確定29資産(カテゴリ, ティッカー, 表示名)
# ---------------------------------------------------------------
ASSETS = [
    ("株式", "^GSPC", "米国株"),
    ("株式", "^N225", "日本株"),
    ("株式", "^KS11", "韓国株"),
    ("株式", "^HSI", "香港株"),
    ("株式", "^TWII", "台湾株"),
    ("株式", "EEM", "新興国株"),
    ("株式", "^GDAXI", "ドイツ株"),
    ("株式", "^FCHI", "フランス株"),
    ("株式", "^FTSE", "イギリス株"),
    ("通貨", "DX-Y.NYB", "ドル"),
    ("通貨", "JPY=X", "円"),
    ("通貨", "CNY=X", "人民元"),
    ("通貨", "EURUSD=X", "ユーロ"),
    ("通貨", "GBPUSD=X", "ポンド"),
    ("暗号資産", "BTC-USD", "BTC"),
    ("暗号資産", "ETH-USD", "ETH"),
    ("コモディティ", "GC=F", "金"),
    ("コモディティ", "SI=F", "銀"),
    ("コモディティ", "HG=F", "銅"),
    ("コモディティ", "CL=F", "原油"),
    ("コモディティ", "NG=F", "天然ガス"),
    ("コモディティ", "ZW=F", "小麦"),
    ("コモディティ", "ZS=F", "大豆"),
    ("コモディティ", "ZC=F", "とうもろこし"),
    ("国債", "IEF", "米国債"),
    ("国債", "2510.T", "日本国債"),
    ("国債", "IGLT.L", "イギリス国債"),
    ("国債", "CBON", "中国国債"),
    ("国債", "IEGA.AS", "ユーロ圏国債"),
]

# 符号反転対象: USD/XXX形式の通貨(上昇=その通貨から資金流出のため)
INVERT_TICKERS = {"JPY=X", "CNY=X"}

# 全グラフ共通のplotly設定(モードバー非表示)
PLOTLY_CONFIG = {"displayModeBar": False}

# ---------------------------------------------------------------
# リスクオン/オフ スコア計算の係数(調整可能な定数)
# 運用しながら調整すること。変更はこのブロックのみでよい。
# ---------------------------------------------------------------
WEIGHT_STOCK  = 1.0   # 株式(リスク資産・主役)
WEIGHT_CRYPTO = 0.3   # 暗号資産(リスク資産・補助)
WEIGHT_BOND   = 0.5   # 国債(安全資産。プラス=リスクオフ方向のため符号反転して加算)
WEIGHT_GOLD   = 0.5   # 金(安全資産。同上)
WEIGHT_DXY    = 0.3   # ドル指数(安全資産逃避。同上)


# ===============================================================
# データ取得
# ===============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history():
    """29資産 + ^TNX の過去3年の日次終値を一括取得する(1時間キャッシュ)。

    ^TNX はパフォーマンスグラフ専用。ASSETSには含まれないが同じdownload呼び出しに
    同梱することで追加の通信なしに取得する。
    戻り値: 列=ティッカー、行=日付 の終値DataFrame。
    """
    tickers = [t for _, t, _ in ASSETS] + ["^TNX"]
    data = yf.download(tickers, period="3y", interval="1d", progress=False)
    close = data["Close"]
    # ASSETSの定義順 + ^TNX で列を並べる(取得できなかった列は除外)
    ordered = [t for t in tickers if t in close.columns]
    return close[ordered]


def compute_returns(close, freq):
    """終値からリターン(%)を計算する。

    freq="D": 日次リターン。freq="W": 週次リターン(各週の最終取引日終値ベース)。
    週末(土日)の行は除外する。暗号資産の土日の値動きは月曜のリターンに合算される。
    符号は「買われる=プラス」に統一(INVERT_TICKERSは反転)。
    """
    weekday = close[close.index.dayofweek < 5]
    if freq == "D":
        returns = weekday.pct_change() * 100
    else:
        weekly_close = weekday.resample("W-FRI").last()
        returns = weekly_close.pct_change() * 100
    for ticker in INVERT_TICKERS:
        if ticker in returns.columns:
            returns[ticker] = -returns[ticker]
    return returns


# ===============================================================
# ステップ4再設計: リスクオン/オフメーター
# ===============================================================
def render_risk_meter(close):
    """リスクオン/オフスコアのゲージと内訳横棒を表示する。"""
    st.subheader("リスクオン/オフ メーター")

    returns = compute_returns(close, "D")
    # 最新営業日の前日比を使う(最終行)
    latest = returns.iloc[-1] if not returns.empty else pd.Series(dtype=float)

    def avg(tickers_list):
        """指定ティッカーのうち取得できたものの平均リターンを返す。NaN のみなら 0。"""
        vals = [latest[t] for t in tickers_list
                if t in latest.index and pd.notna(latest[t])]
        return sum(vals) / len(vals) if vals else 0.0

    stock_avg  = avg([t for c, t, _ in ASSETS if c == "株式"])
    bond_avg   = avg([t for c, t, _ in ASSETS if c == "国債"])
    crypto_avg = avg([t for c, t, _ in ASSETS if c == "暗号資産"])
    gold_ret   = avg(["GC=F"])
    dxy_ret    = avg(["DX-Y.NYB"])

    # 総合スコア計算(安全資産は符号反転して加算)
    score = (
        stock_avg   * WEIGHT_STOCK
        + crypto_avg  * WEIGHT_CRYPTO
        + bond_avg    * WEIGHT_BOND   * -1
        + gold_ret    * WEIGHT_GOLD   * -1
        + dxy_ret     * WEIGHT_DXY    * -1
    )
    score = max(-3.0, min(3.0, score))  # 頭打ち処理

    # 判定ラベルとスコア色(ゲージのstepsと対応)
    if score >= 1.5:
        label      = "強いリスクオン"
        score_color = "#2ca02c"
    elif score >= 0.5:
        label      = "リスクオン"
        score_color = "#2ca02c"
    elif score >= -0.5:
        label      = "中立"
        score_color = "#888888"
    elif score >= -1.5:
        label      = "リスクオフ"
        score_color = "#d62728"
    else:
        label      = "強いリスクオフ"
        score_color = "#d62728"

    # 判定ラベルをゲージの外(Streamlit側)に表示し、go.Indicatorのtitleとの重なりを回避
    st.markdown(
        f"<div style='text-align:center; font-size:1.4rem; font-weight:bold;"
        f" color:{score_color}'>{label}</div>",
        unsafe_allow_html=True,
    )

    # --- ゲージ ---
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(valueformat=".2f", font=dict(size=36, color=score_color)),
        gauge=dict(
            axis=dict(range=[-3, 3], tickvals=[-3, -1.5, -0.5, 0.5, 1.5, 3]),
            bar=dict(color="black", thickness=0.25),
            steps=[
                dict(range=[-3.0, -1.5], color="#d62728"),   # 強いリスクオフ: 濃い赤
                dict(range=[-1.5, -0.5], color="#f4a582"),   # リスクオフ: 薄い赤
                dict(range=[-0.5,  0.5], color="#cccccc"),   # 中立: グレー
                dict(range=[ 0.5,  1.5], color="#92c992"),   # リスクオン: 薄い緑
                dict(range=[ 1.5,  3.0], color="#2ca02c"),   # 強いリスクオン: 濃い緑
            ],
        ),
    ))
    fig_gauge.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=40, b=10),
    )
    st.plotly_chart(fig_gauge, use_container_width=True, config=PLOTLY_CONFIG)

    # --- 内訳横棒グラフ(個別資産別) ---
    # スコアに使う各資産の (表示名, 前日比%, 寄与度, カテゴリ) を列挙する。
    # 寄与度 = 前日比% × (グループ重み / グループ資産数) × 方向符号
    stock_tickers  = [t for c, t, _ in ASSETS if c == "株式"]
    bond_tickers   = [t for c, t, _ in ASSETS if c == "国債"]
    crypto_tickers = [t for c, t, _ in ASSETS if c == "暗号資産"]
    n_stock  = max(len(stock_tickers),  1)
    n_bond   = max(len(bond_tickers),   1)
    n_crypto = max(len(crypto_tickers), 1)

    detail_rows = []
    # 株式
    for _, t, n in ASSETS:
        if t in stock_tickers and t in latest.index and pd.notna(latest[t]):
            ret = float(latest[t])
            detail_rows.append((n, "株式", ret,
                                 ret * WEIGHT_STOCK / n_stock))
    # 暗号資産
    for _, t, n in ASSETS:
        if t in crypto_tickers and t in latest.index and pd.notna(latest[t]):
            ret = float(latest[t])
            detail_rows.append((n, "暗号資産", ret,
                                 ret * WEIGHT_CRYPTO / n_crypto))
    # 国債(安全資産: 寄与度の符号を反転)
    for _, t, n in ASSETS:
        if t in bond_tickers and t in latest.index and pd.notna(latest[t]):
            ret = float(latest[t])
            detail_rows.append((n, "国債", ret,
                                 ret * WEIGHT_BOND / n_bond * -1))
    # 金
    if "GC=F" in latest.index and pd.notna(latest["GC=F"]):
        ret = float(latest["GC=F"])
        detail_rows.append(("金", "コモディティ", ret,
                             ret * WEIGHT_GOLD * -1))
    # ドル指数
    if "DX-Y.NYB" in latest.index and pd.notna(latest["DX-Y.NYB"]):
        ret = float(latest["DX-Y.NYB"])
        detail_rows.append(("ドル指数", "通貨", ret,
                             ret * WEIGHT_DXY * -1))
    # 寄与度の大きい順に並べる(横棒は下から描画されるため昇順で渡す)
    detail_rows.sort(key=lambda x: x[3])
    d_names   = [r[0] for r in detail_rows]
    d_cats    = [r[1] for r in detail_rows]
    d_rets    = [r[2] for r in detail_rows]
    d_contribs = [r[3] for r in detail_rows]
    d_colors  = ["#2ca02c" if v >= 0 else "#d62728" for v in d_contribs]

    fig_bar = go.Figure(go.Bar(
        x=d_contribs, y=d_names, orientation="h",
        marker_color=d_colors,
        # バー外に「前日比%」を表示(寄与度はhoverで確認)
        text=[f"{r:+.2f}%" for r in d_rets],
        textposition="outside",
        customdata=list(zip(d_cats, d_rets, d_contribs)),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "カテゴリ: %{customdata[0]}<br>"
            "前日比: %{customdata[1]:+.2f}%<br>"
            "寄与度: %{customdata[2]:+.3f}"
            "<extra></extra>"
        ),
    ))
    fig_bar.update_layout(
        title=dict(text="本日のスコア内訳(個別資産別)", font=dict(size=14)),
        height=520,
        margin=dict(l=10, r=60, t=40, b=30),
        xaxis=dict(
            range=[-2.0, 2.0],
            title="リスクオフ方向 ← 0 → リスクオン方向(寄与度)",
            fixedrange=True,
        ),
        yaxis=dict(fixedrange=True),
        dragmode=False,
    )
    st.caption("バー長さ=スコアへの寄与度 / バー右のラベル=前日比% / "
               "タップで詳細(前日比・寄与度)")
    st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)

    # スコアの基準日を表示
    if not returns.empty:
        st.caption(f"基準: {returns.index[-1].strftime('%Y/%m/%d')} の前日比リターン")

    st.caption("※ このスコアは価格変動からの推定であり、"
               "実際の資金フロー統計(ファンドフロー)ではありません。")


# ===============================================================
# ステップ5 タスクA: ヒートマップ
# ===============================================================
def make_heatmap(z_df, zrange, show_text, width, height):
    """リターンDataFrame(行=日付/週, 列=ティッカー)からヒートマップを作る。

    欠損(NaN)セルは描画されず、背景色(グレー)が見える。
    """
    tickers = [t for _, t, _ in ASSETS]
    names   = [n for _, _, n in ASSETS]
    z = z_df[[t for t in tickers if t in z_df.columns]].T.values
    x_labels = [d.strftime("%m/%d") for d in z_df.index]

    heatmap = go.Heatmap(
        z=z, x=x_labels, y=names,
        colorscale="RdYlGn", zmid=0, zmin=-zrange, zmax=zrange,
        colorbar=dict(title="%", thickness=12),
        hovertemplate="%{y}<br>%{x}<br>%{z:.2f}%<extra></extra>",
        hoverongaps=False,
    )
    if show_text:
        heatmap.texttemplate = "%{z:.1f}"
        heatmap.textfont = dict(size=9)

    fig = go.Figure(heatmap)
    fig.update_layout(
        width=width, height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#cccccc",
        yaxis=dict(autorange="reversed", tickfont=dict(size=11), fixedrange=True),
        xaxis=dict(tickfont=dict(size=10), fixedrange=True),
        dragmode=False,
    )
    return fig


def render_heatmap(close):
    """資産別リターン ヒートマップを表示する。"""
    st.subheader("資産別リターン ヒートマップ")

    mode = st.radio(
        "表示モード", ["日次", "週次"], horizontal=True, key="hm_mode",
        label_visibility="collapsed",
    )

    if mode == "日次":
        returns = compute_returns(close, "D")
        if "day_week_offset" not in st.session_state:
            st.session_state.day_week_offset = 0
        offset = st.session_state.day_week_offset

        today = pd.Timestamp.today().normalize()
        week_start = (today - pd.Timedelta(days=today.dayofweek)
                      - pd.Timedelta(weeks=offset))
        week_end = week_start + pd.Timedelta(days=5)
        data_start = returns.index.min()

        prev_disabled = (week_start <= data_start)
        next_disabled = (offset == 0)

        col1, col2, col3 = st.columns(3)
        if col1.button("← 前週", disabled=prev_disabled):
            st.session_state.day_week_offset += 1
            st.rerun()
        if col2.button("今週に戻る", disabled=next_disabled):
            st.session_state.day_week_offset = 0
            st.rerun()
        if col3.button("翌週 →", disabled=next_disabled):
            st.session_state.day_week_offset -= 1
            st.rerun()

        mask = (returns.index >= week_start) & (returns.index < week_end)
        period = returns[mask]
        label = (f"{week_start.strftime('%Y/%m/%d')} 〜 "
                 f"{(week_end - pd.Timedelta(days=1)).strftime('%m/%d')}")
        st.caption(f"表示期間: {label}(日次リターン%)")
        if period.empty:
            st.warning("この週のデータがありません。")
        else:
            fig = make_heatmap(period, zrange=3, show_text=True,
                               width=600, height=620)
            st.plotly_chart(fig, use_container_width=False, config=PLOTLY_CONFIG)

    else:
        returns = compute_returns(close, "W")
        returns = returns.dropna(how="all")
        n_weeks = len(returns)
        if "week_offset" not in st.session_state:
            st.session_state.week_offset = 0
        offset = st.session_state.week_offset

        end   = n_weeks - 13 * offset
        start = max(0, end - 13)
        prev_disabled = (start == 0)
        next_disabled = (offset == 0)

        col1, col2, col3 = st.columns(3)
        if col1.button("← 前へ", disabled=prev_disabled):
            st.session_state.week_offset += 1
            st.rerun()
        if col2.button("最新に戻る", disabled=next_disabled):
            st.session_state.week_offset = 0
            st.rerun()
        if col3.button("次へ →", disabled=next_disabled):
            st.session_state.week_offset -= 1
            st.rerun()

        period = returns.iloc[start:end]
        if period.empty:
            st.warning("この期間のデータがありません。")
        else:
            label = (f"{period.index[0].strftime('%Y/%m/%d')} 〜 "
                     f"{period.index[-1].strftime('%Y/%m/%d')}")
            st.caption(f"表示期間: {label}(週次リターン%・各週の最終取引日終値ベース)")
            fig = make_heatmap(period, zrange=5, show_text=True,
                               width=760, height=620)
            st.plotly_chart(fig, use_container_width=False, config=PLOTLY_CONFIG)


# ===============================================================
# ステップ5 タスクB: カテゴリ別相対パフォーマンス折れ線
# ===============================================================
def render_performance_chart(close):
    """カテゴリ別相対パフォーマンス折れ線(起点=100)を表示する。"""
    st.subheader("カテゴリ別相対パフォーマンス")

    period_label = st.radio(
        "期間", ["1ヶ月", "3ヶ月", "6ヶ月", "1年"], horizontal=True,
        key="perf_period", index=1, label_visibility="collapsed",
    )
    months = {"1ヶ月": 1, "3ヶ月": 3, "6ヶ月": 6, "1年": 12}[period_label]
    start = pd.Timestamp.today().normalize() - pd.DateOffset(months=months)

    returns = compute_returns(close, "D")
    period = returns[returns.index >= start].dropna(how="all")
    if period.empty:
        st.warning("この期間のデータがありません。")
        return

    before = returns.index[returns.index < period.index[0]]
    base_date = before[-1] if len(before) > 0 else (
        period.index[0] - pd.tseries.offsets.BDay(1))

    categories = []
    for category, _, _ in ASSETS:
        if category not in categories:
            categories.append(category)

    target = st.selectbox("表示対象", ["全体(カテゴリ平均)"] + categories,
                          key="perf_target")

    def to_cumulative(daily_return):
        cumulative = (1 + daily_return.fillna(0) / 100).cumprod() * 100
        base_point = pd.Series([100.0], index=[base_date])
        return pd.concat([base_point, cumulative])

    lines = []
    if target == "全体(カテゴリ平均)":
        for category in categories:
            tickers = [t for c, t, _ in ASSETS
                       if c == category and t in period.columns]
            lines.append((category, period[tickers].mean(axis=1, skipna=True)))
    else:
        for category, ticker, name in ASSETS:
            if category == target and ticker in period.columns:
                lines.append((name, period[ticker]))

    # すべての表示対象に共通で米10年債利回りを追加する
    # ^TNX は利回り(%水準)。pct_changeで「利回り自体の変化率」を累積し起点=100で表示
    tnx_available = "^TNX" in period.columns
    if tnx_available:
        lines.append(("米10年債利回り", period["^TNX"]))

    fig = go.Figure()
    for name, daily_return in lines:
        cumulative = to_cumulative(daily_return)
        # 米10年債利回りは破線で区別する
        line_style = dict(dash="dash") if name == "米10年債利回り" else {}
        fig.add_trace(go.Scatter(
            x=cumulative.index, y=cumulative.values,
            mode="lines", name=name, line=line_style,
            hovertemplate="%{x|%Y/%m/%d}<br>" + name + ": %{y:.1f}<extra></extra>",
        ))

    # x軸の月名を日本語で設定(plotlyのデフォルトは英語)
    # 月初日のtickvalを生成し、1月のみ「yyyy年m月」、それ以外は「m月」と表示
    tick_start = (base_date + pd.offsets.MonthBegin(1))
    tick_end   = period.index[-1] if not period.empty else pd.Timestamp.today()
    tick_vals  = pd.date_range(start=tick_start, end=tick_end, freq="MS")
    tick_text  = [
        f"{d.year}年{d.month}月" if d.month == 1 else f"{d.month}月"
        for d in tick_vals
    ]

    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis=dict(title="起点=100", fixedrange=True),
        xaxis=dict(
            tickvals=tick_vals, ticktext=tick_text, fixedrange=True,
        ),
        dragmode=False,
    )
    if target == "全体(カテゴリ平均)":
        st.caption(f"表示期間: 直近{period_label}(カテゴリ内平均リターンの累積、起点=100)")
    else:
        st.caption(f"表示期間: 直近{period_label}({target}の個別資産、起点=100)"
                   " ※凡例をタップすると線の表示/非表示を切り替えられます")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


# ===============================================================
# ステップ5 タスクC: 期間リターンランキング横棒
# ===============================================================
def render_ranking_chart(close):
    """期間リターンランキング横棒グラフを表示する。

    期間はタスクBの選択(perf_period)と連動する。
    """
    st.subheader("期間リターンランキング")

    period_label = st.session_state.get("perf_period", "3ヶ月")
    months = {"1ヶ月": 1, "3ヶ月": 3, "6ヶ月": 6, "1年": 12}[period_label]
    start = pd.Timestamp.today().normalize() - pd.DateOffset(months=months)

    returns = compute_returns(close, "D")
    period = returns[returns.index >= start].dropna(how="all")
    if period.empty:
        st.warning("この期間のデータがありません。")
        return

    results = []
    for _, ticker, name in ASSETS:
        if ticker not in period.columns:
            continue
        total = ((1 + period[ticker].fillna(0) / 100).prod() - 1) * 100
        results.append((name, total))

    results.sort(key=lambda x: x[1])
    names  = [r[0] for r in results]
    values = [r[1] for r in results]
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=names, orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in values],
        textposition="outside",
        hovertemplate="%{y}: %{x:+.2f}%<extra></extra>",
    ))
    fig.update_layout(
        height=700,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="期間リターン(%)", fixedrange=True),
        yaxis=dict(tickfont=dict(size=11), fixedrange=True),
        dragmode=False,
    )
    st.caption(f"表示期間: 直近{period_label}(全29資産、上=資金流入/下=資金流出)")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


# ===============================================================
# ページ本体(シングルページ)
# ===============================================================
def main():
    """世界マネーフロー モニター 本体。"""
    st.set_page_config(page_title="世界マネーフロー", page_icon="🌏", layout="centered")
    st.title("🌏 世界マネーフロー モニター")

    with st.spinner("データ取得中(初回は時間がかかります)..."):
        close = fetch_history()

    if close.empty:
        st.error("データを取得できませんでした。時間をおいて再読み込みしてください。")
        return

    # --- ステップ4: リスクオン/オフメーター(最上部) ---
    render_risk_meter(close)

    # --- ステップ5 タスクA: ヒートマップ ---
    st.divider()
    render_heatmap(close)

    # --- ステップ5 タスクB: カテゴリ別相対パフォーマンス ---
    st.divider()
    render_performance_chart(close)

    # --- ステップ5 タスクC: 期間リターンランキング ---
    st.divider()
    render_ranking_chart(close)

    # --- 共通注記 ---
    st.caption(
        "※ 国債ETFは各国の現地通貨建て価格のリターンであり、為替変動は含みません。\n\n"
        "※ 週末は表示しません。暗号資産の土日の値動きは月曜のリターンに合算されます。\n\n"
        "※ グレーのセルは市場休日などでデータが無い日です。"
    )


if __name__ == "__main__":
    main()
