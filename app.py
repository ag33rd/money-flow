# -*- coding: utf-8 -*-
"""世界マネーフロー可視化アプリ

タブ1「本日」: 主要12指標の最新値・前日比をカード表示(ステップ2)
タブ2「時系列」: 29資産の時系列ヒートマップ(ステップ5 タスクA)
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------
# タブ1「本日」用: 監視対象ティッカー(カテゴリ, ティッカー, 表示名)
# ---------------------------------------------------------------
TICKERS = [
    ("株価指数", "^GSPC", "S&P500(米)"),
    ("株価指数", "^IXIC", "NASDAQ(米)"),
    ("株価指数", "^N225", "日経225"),
    ("株価指数", "^GDAXI", "DAX(独)"),
    ("為替", "DX-Y.NYB", "ドル指数(DXY)"),
    ("為替", "JPY=X", "ドル円(USD/JPY)"),
    ("為替", "AUDNZD=X", "豪ドル/NZドル"),
    ("債券・VIX", "^TNX", "米10年債利回り(%)"),
    ("債券・VIX", "^VIX", "VIX(恐怖指数)"),
    ("暗号資産・金", "BTC-USD", "ビットコイン(USD)"),
    ("暗号資産・金", "ETH-USD", "イーサリアム(USD)"),
    ("暗号資産・金", "GC=F", "金先物(USD)"),
]

# ---------------------------------------------------------------
# タブ2「時系列」用: 確定29資産(カテゴリ, ティッカー, 表示名)
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

# 時系列タブの全グラフ共通のplotly設定(モードバー非表示。タスクB・Cでも使う)
PLOTLY_CONFIG = {"displayModeBar": False}


# ===============================================================
# タブ1「本日」のロジック(ステップ2と同じ)
# ===============================================================
@st.cache_data(ttl=600)
def fetch_quote(ticker):
    """指定ティッカーの最新終値と前日比(%)を取得する。

    結果は10分間キャッシュし、再読み込み時のAPIアクセスを減らす。
    戻り値: (最新値, 前日比%) のタプル。取得失敗時は (None, None)。
    """
    try:
        data = yf.Ticker(ticker).history(period="5d")
        close = data["Close"].dropna()
        if len(close) < 2:
            return None, None
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2])
        change_pct = (latest - previous) / previous * 100
        return latest, change_pct
    except Exception:
        return None, None


def render_today_tab():
    """「本日」タブ: カテゴリ別に2カラムでメトリクスを表示する。"""
    st.caption("データ: yfinance(株・指数は15〜20分遅延、暗号資産はほぼリアルタイム)")

    current_category = None
    columns = None
    position = 0

    for category, ticker, name in TICKERS:
        if category != current_category:
            st.subheader(category)
            columns = st.columns(2)
            current_category = category
            position = 0

        latest, change_pct = fetch_quote(ticker)
        with columns[position % 2]:
            if latest is None:
                st.metric(label=name, value="取得失敗")
            else:
                st.metric(
                    label=name,
                    value=f"{latest:,.2f}",
                    delta=f"{change_pct:+.2f}%",
                )
        position += 1

    if st.button("🔄 最新データに更新"):
        fetch_quote.clear()
        st.rerun()


# ===============================================================
# タブ2「時系列」のロジック(ステップ5 タスクA)
# ===============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history():
    """29資産の過去3年の日次終値を一括取得する(1時間キャッシュ)。

    戻り値: 列=ティッカー、行=日付 の終値DataFrame。
    """
    tickers = [t for _, t, _ in ASSETS]
    data = yf.download(tickers, period="3y", interval="1d", progress=False)
    close = data["Close"]
    # ASSETSの定義順に列を並べる(取得できなかった列は除外される)
    close = close[[t for t in tickers if t in close.columns]]
    return close


def compute_returns(close, freq):
    """終値からリターン(%)を計算する。

    freq="D": 日次リターン。freq="W": 週次リターン(各週の最終取引日終値ベース)。
    週末(土日)の行は除外する。暗号資産の土日の値動きは月曜のリターンに合算される。
    符号は「買われる=プラス」に統一(INVERT_TICKERSは反転)。
    """
    # 営業日(月〜金)のみ残す
    weekday = close[close.index.dayofweek < 5]
    if freq == "D":
        returns = weekday.pct_change() * 100
    else:
        # 週次: 金曜締めで各週の最終値を取り、週次変化率を計算する
        weekly_close = weekday.resample("W-FRI").last()
        returns = weekly_close.pct_change() * 100
    # 符号反転(USD/XXX形式の通貨)
    for ticker in INVERT_TICKERS:
        if ticker in returns.columns:
            returns[ticker] = -returns[ticker]
    return returns


def make_heatmap(z_df, zrange, show_text, width, height):
    """リターンDataFrame(行=日付/週, 列=ティッカー)からヒートマップを作る。

    欠損(NaN)セルは描画されず、背景色(グレー)が見える。
    """
    tickers = [t for _, t, _ in ASSETS]
    names = [n for _, _, n in ASSETS]
    # 行=資産、列=日付 に転置し、資産はASSETSの定義順に並べる
    z = z_df[[t for t in tickers if t in z_df.columns]].T.values
    x_labels = [d.strftime("%m/%d") for d in z_df.index]

    heatmap = go.Heatmap(
        z=z,
        x=x_labels,
        y=names,
        colorscale="RdYlGn",
        zmid=0,
        zmin=-zrange,
        zmax=zrange,
        colorbar=dict(title="%", thickness=12),
        hovertemplate="%{y}<br>%{x}<br>%{z:.2f}%<extra></extra>",
        hoverongaps=False,
    )
    if show_text:
        heatmap.texttemplate = "%{z:.1f}"
        heatmap.textfont = dict(size=9)

    fig = go.Figure(heatmap)
    fig.update_layout(
        width=width,
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#cccccc",  # 欠損セルはこの背景色(グレー)で見える
        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
        xaxis=dict(tickfont=dict(size=10)),
    )
    return fig


def render_performance_chart(close):
    """タスクB: カテゴリ別相対パフォーマンス折れ線(起点=100)を表示する。"""
    st.subheader("カテゴリ別相対パフォーマンス")

    # 期間切替(選択はsession_stateに保持し、タスクCでも同じ期間を使う)
    period_label = st.radio(
        "期間", ["1ヶ月", "3ヶ月", "6ヶ月", "1年"], horizontal=True,
        key="perf_period", index=1, label_visibility="collapsed",
    )
    months = {"1ヶ月": 1, "3ヶ月": 3, "6ヶ月": 6, "1年": 12}[period_label]
    start = pd.Timestamp.today().normalize() - pd.DateOffset(months=months)

    # 日次リターン(符号統一済み)を期間でスライスする
    returns = compute_returns(close, "D")
    period = returns[returns.index >= start].dropna(how="all")
    if period.empty:
        st.warning("この期間のデータがありません。")
        return

    # 基準日 = 全資産共通の直前営業日(リターン表の日付インデックスは
    # 全29資産の取引日の和集合なので、期間開始前の最後の日付を使う)。
    # データ先頭より前に営業日が無い場合のみ、期間初日の1営業日前で代用する
    before = returns.index[returns.index < period.index[0]]
    if len(before) > 0:
        base_date = before[-1]
    else:
        base_date = period.index[0] - pd.tseries.offsets.BDay(1)

    categories = []
    for category, _, _ in ASSETS:
        if category not in categories:
            categories.append(category)

    # 表示対象の選択(全体=カテゴリ平均5本 / カテゴリ名=個別資産の線)
    target = st.selectbox("表示対象", ["全体(カテゴリ平均)"] + categories,
                          key="perf_target")

    def to_cumulative(daily_return):
        """日次リターン(%)系列を累積し、先頭に基準日(=100)の点を付けて返す。"""
        cumulative = (1 + daily_return.fillna(0) / 100).cumprod() * 100
        base_point = pd.Series([100.0], index=[base_date])
        return pd.concat([base_point, cumulative])

    # (表示名, 日次リターン系列) のリストを作る
    lines = []
    if target == "全体(カテゴリ平均)":
        for category in categories:
            tickers = [t for c, t, _ in ASSETS
                       if c == category and t in period.columns]
            # 欠損(休場日)は0%として扱い、取引のあった資産の平均で代表させる
            lines.append((category, period[tickers].mean(axis=1, skipna=True)))
    else:
        for category, ticker, name in ASSETS:
            if category == target and ticker in period.columns:
                lines.append((name, period[ticker]))

    fig = go.Figure()
    for name, daily_return in lines:
        cumulative = to_cumulative(daily_return)
        fig.add_trace(go.Scatter(
            x=cumulative.index, y=cumulative.values,
            mode="lines", name=name,
            hovertemplate="%{x|%Y/%m/%d}<br>" + name
                          + ": %{y:.1f}<extra></extra>",
        ))

    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis=dict(title="起点=100"),
    )
    if target == "全体(カテゴリ平均)":
        st.caption(f"表示期間: 直近{period_label}"
                   f"(カテゴリ内平均リターンの累積、起点=100)")
    else:
        st.caption(f"表示期間: 直近{period_label}({target}の個別資産、起点=100)"
                   " ※凡例をタップすると線の表示/非表示を切り替えられます")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def render_timeseries_tab():
    """「時系列」タブ: 日次/週次切替付きヒートマップを表示する。"""
    with st.spinner("データ取得中(初回は時間がかかります)..."):
        close = fetch_history()

    if close.empty:
        st.error("データを取得できませんでした。時間をおいて再読み込みしてください。")
        return

    st.subheader("資産別リターン ヒートマップ")

    # --- 日次/週次の切替(選択状態はsession_stateで保持) ---
    mode = st.radio(
        "表示モード", ["日次", "週次"], horizontal=True, key="hm_mode",
        label_visibility="collapsed",
    )

    if mode == "日次":
        returns = compute_returns(close, "D")
        # --- 週単位ナビゲーション(0=今週、1=先週、...) ---
        if "day_week_offset" not in st.session_state:
            st.session_state.day_week_offset = 0
        offset = st.session_state.day_week_offset

        today = pd.Timestamp.today().normalize()
        # 今週の月曜日を起点とし、offset週ぶん過去へずらす
        week_start = today - pd.Timedelta(days=today.dayofweek) \
            - pd.Timedelta(weeks=offset)
        week_end = week_start + pd.Timedelta(days=5)  # 月〜金の5営業日
        data_start = returns.index.min()

        # 前週がデータ範囲外ならボタンを無効化する
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
        # --- 13週単位ナビゲーション(0=最新13週) ---
        if "week_offset" not in st.session_state:
            st.session_state.week_offset = 0
        offset = st.session_state.week_offset

        end = n_weeks - 13 * offset
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

    # --- タスクB: カテゴリ別相対パフォーマンス ---
    st.divider()
    render_performance_chart(close)

    # --- 注記 ---
    st.caption(
        "※ 本表示は価格変動からの推定であり、実際の資金フロー統計"
        "(ファンドフロー)ではありません。\n\n"
        "※ 国債ETFは各国の現地通貨建て価格のリターンであり、"
        "為替変動は含みません。\n\n"
        "※ 週末は表示しません。暗号資産の土日の値動きは月曜のリターンに"
        "合算されます。\n\n"
        "※ グレーのセルは市場休日などでデータが無い日です。"
    )


# ===============================================================
# ページ本体
# ===============================================================
def main():
    """2タブ構成のダッシュボード本体。"""
    st.set_page_config(page_title="世界マネーフロー", page_icon="🌏", layout="centered")
    st.title("🌏 世界マネーフロー モニター")

    tab_today, tab_series = st.tabs(["本日", "時系列"])
    with tab_today:
        render_today_tab()
    with tab_series:
        render_timeseries_tab()


if __name__ == "__main__":
    main()
