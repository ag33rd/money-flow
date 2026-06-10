# -*- coding: utf-8 -*-
"""世界マネーフロー可視化アプリ ステップ2: Streamlitダッシュボード

yfinance で監視対象ティッカーの最新値と前日比を取得し、
カテゴリ別にカード形式(st.metric)で表示する。
スマホ閲覧前提のため、2カラムのシンプルなレイアウトとする。
"""

import streamlit as st
import yfinance as yf

# 監視対象ティッカー(カテゴリ, ティッカー, 表示名)※ステップ1と同じ
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


@st.cache_data(ttl=600)
def fetch_quote(ticker):
    """指定ティッカーの最新終値と前日比(%)を取得する。

    結果は10分間キャッシュし、再読み込み時のAPIアクセスを減らす。
    戻り値: (最新値, 前日比%) のタプル。取得失敗時は (None, None)。
    """
    try:
        # 直近5日分の日足を取得(休場日があっても2営業日分を確保するため)
        data = yf.Ticker(ticker).history(period="5d")
        close = data["Close"].dropna()
        if len(close) < 2:
            return None, None
        latest = float(close.iloc[-1])    # 最新値
        previous = float(close.iloc[-2])  # 前日値
        change_pct = (latest - previous) / previous * 100  # 前日比(%)
        return latest, change_pct
    except Exception:
        # 通信エラーやティッカー不正は「取得失敗」として表示側で処理する
        return None, None


def main():
    """ダッシュボード本体。カテゴリ別に2カラムでメトリクスを表示する。"""
    st.set_page_config(page_title="世界マネーフロー", page_icon="🌏", layout="centered")
    st.title("🌏 世界マネーフロー モニター")
    st.caption("データ: yfinance(株・指数は15〜20分遅延、暗号資産はほぼリアルタイム)")

    current_category = None
    columns = None
    position = 0  # カテゴリ内の表示位置(2カラム振り分け用)

    for category, ticker, name in TICKERS:
        # カテゴリが変わったら見出しと新しい2カラムを作る
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

    # 手動更新ボタン(キャッシュを破棄して再取得する)
    if st.button("🔄 最新データに更新"):
        fetch_quote.clear()
        st.rerun()


if __name__ == "__main__":
    main()
