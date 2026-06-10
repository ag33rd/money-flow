# -*- coding: utf-8 -*-
"""世界マネーフロー可視化アプリ ステップ1: コンソール表示版

yfinance で監視対象ティッカーの最新値と前日比を取得し、
カテゴリ別にコンソールへ表示する。
"""

import yfinance as yf

# 監視対象ティッカー(カテゴリ, ティッカー, 表示名)
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


def fetch_quote(ticker):
    """指定ティッカーの最新終値と前日比(%)を取得する。

    戻り値: (最新値, 前日比%) のタプル。取得失敗時は (None, None)。
    """
    try:
        # 直近5日分の日足を取得(休場日があっても2営業日分を確保するため)
        data = yf.Ticker(ticker).history(period="5d")
        close = data["Close"].dropna()
        if len(close) < 2:
            return None, None
        latest = close.iloc[-1]      # 最新値
        previous = close.iloc[-2]    # 前日値
        change_pct = (latest - previous) / previous * 100  # 前日比(%)
        return latest, change_pct
    except Exception as e:
        # 通信エラーやティッカー不正などはここで捕捉して続行する
        print(f"  [エラー] {ticker}: {e}")
        return None, None


def main():
    """全ティッカーを取得してカテゴリ別に表示する。"""
    print("=" * 50)
    print(" 世界マネーフロー モニター(yfinance)")
    print("=" * 50)

    current_category = None
    for category, ticker, name in TICKERS:
        # カテゴリが変わったら見出しを表示する
        if category != current_category:
            print(f"\n--- {category} ---")
            current_category = category

        latest, change_pct = fetch_quote(ticker)
        if latest is None:
            print(f"  {name:<20} 取得失敗")
        else:
            sign = "+" if change_pct >= 0 else ""
            print(f"  {name:<20} {latest:>12,.2f}  ({sign}{change_pct:.2f}%)")

    print("\n※株・指数は15〜20分遅延。暗号資産はほぼリアルタイム。")


if __name__ == "__main__":
    main()
