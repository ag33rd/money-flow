# -*- coding: utf-8 -*-
"""ステップ5 タスク0: 候補ティッカーの取得可否チェック

候補ティッカーすべてについて「過去3年の日次データが取得できるか・
最終データ日付・データ件数」を一覧表示する。
国債カテゴリの「要確認」銘柄は候補ETFを入れて検証する。
"""

import yfinance as yf

# 候補ティッカー(カテゴリ, 資産, ティッカー, 備考)
CANDIDATES = [
    ("株式", "米国株", "^GSPC", "S&P500"),
    ("株式", "日本株", "^N225", "日経225"),
    ("株式", "韓国株", "^KS11", "KOSPI"),
    ("株式", "香港株", "^HSI", "ハンセン"),
    ("株式", "台湾株", "^TWII", "加権指数"),
    ("株式", "新興国株", "EEM", "米上場ETFで代替"),
    ("株式", "ドイツ株", "^GDAXI", "DAX"),
    ("株式", "フランス株", "^FCHI", "CAC40"),
    ("株式", "イギリス株", "^FTSE", "FTSE100"),
    ("通貨", "ドル", "DX-Y.NYB", "ドル指数"),
    ("通貨", "円", "JPY=X", "USD/JPY 符号反転対象"),
    ("通貨", "人民元", "CNY=X", "USD/CNY 符号反転対象"),
    ("通貨", "ユーロ", "EURUSD=X", "そのまま"),
    ("通貨", "ポンド", "GBPUSD=X", "そのまま"),
    ("暗号資産", "BTC", "BTC-USD", ""),
    ("暗号資産", "ETH", "ETH-USD", ""),
    ("コモディティ", "金", "GC=F", ""),
    ("コモディティ", "銀", "SI=F", ""),
    ("コモディティ", "銅", "HG=F", ""),
    ("コモディティ", "原油", "CL=F", "WTI"),
    ("コモディティ", "天然ガス", "NG=F", ""),
    ("コモディティ", "小麦", "ZW=F", ""),
    ("コモディティ", "大豆", "ZS=F", ""),
    ("コモディティ", "とうもろこし", "ZC=F", ""),
    ("国債", "米国債", "IEF", "7-10年ETF(価格ベース)"),
    ("国債", "日本国債(候補)", "2510.T", "NEXT FUNDS 国内債券ETF(東証)"),
    ("国債", "イギリス国債(候補)", "IGLT.L", "ロンドン上場ギルトETF"),
    ("国債", "中国国債(候補)", "CBON", "米上場中国債ETF"),
    ("国債", "ユーロ圏国債(候補)", "IEGA.AS", "iShares ユーロ圏国債ETF(仏国債の代替)"),
]

# 3年日次でこの件数を下回ったら「データ不足」と判定する目安
MIN_ROWS = 500


def check_ticker(ticker):
    """過去3年の日次データを取得し、(件数, 最初の日付, 最後の日付) を返す。

    取得失敗・データなしの場合は (0, None, None)。
    """
    try:
        data = yf.Ticker(ticker).history(period="3y", interval="1d")
        close = data["Close"].dropna()
        if len(close) == 0:
            return 0, None, None
        first = close.index[0].strftime("%Y-%m-%d")
        last = close.index[-1].strftime("%Y-%m-%d")
        return len(close), first, last
    except Exception as e:
        print(f"  [エラー] {ticker}: {e}")
        return 0, None, None


def main():
    """全候補ティッカーをチェックして一覧表示する。"""
    print("=" * 78)
    print(" ティッカー取得可否チェック(過去3年・日次)")
    print("=" * 78)
    print(f"{'判定':<4} {'カテゴリ':<8} {'資産':<14} {'ティッカー':<10} "
          f"{'件数':>5}  {'開始日':<11} {'最終日':<11}")
    print("-" * 78)

    ng_list = []
    for category, asset, ticker, note in CANDIDATES:
        rows, first, last = check_ticker(ticker)
        if rows == 0:
            mark = "×"
            ng_list.append((asset, ticker, "取得不可"))
            print(f"{mark:<4} {category:<8} {asset:<14} {ticker:<10} "
                  f"{'-':>5}  {'-':<11} {'-':<11}")
        elif rows < MIN_ROWS:
            mark = "△"
            ng_list.append((asset, ticker, f"データ不足({rows}件)"))
            print(f"{mark:<4} {category:<8} {asset:<14} {ticker:<10} "
                  f"{rows:>5}  {first:<11} {last:<11}")
        else:
            mark = "○"
            print(f"{mark:<4} {category:<8} {asset:<14} {ticker:<10} "
                  f"{rows:>5}  {first:<11} {last:<11}")

    print("-" * 78)
    if ng_list:
        print("\n【要対応】以下は取得不可またはデータ不足です:")
        for asset, ticker, reason in ng_list:
            print(f"  - {asset} ({ticker}): {reason}")
    else:
        print("\n全銘柄が取得可能です。")
    print(f"\n判定基準: ○=取得可({MIN_ROWS}件以上) △=データ不足 ×=取得不可")
    print("※暗号資産は365日取引のため件数が多くなります(約1,095件)")


if __name__ == "__main__":
    main()
