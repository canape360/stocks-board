# /home/naomi/update_latest.py
import json
import csv
import os
import urllib.request
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 出力
OUT_JSON = os.path.join(BASE_DIR, "latest.json")

# 履歴CSV（/signal がこれを読む）
HISTORY_DIR = os.path.join(BASE_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

JST = timezone(timedelta(hours=9))

# ★ Stooq: 東証は .JP
TICKERS = {
    "ホンダ": "7267.JP",
    "日本製鉄": "5401.JP",
    "日立製作所": "6501.JP",
}

def fetch_daily_csv_stooq(symbol: str) -> str:
    """
    Stooqから日足CSV（文字列）を取得する
    例: https://stooq.com/q/d/l/?s=7267.jp&i=d
    """
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}&i=d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_last_close(csv_text: str):
    rows = list(csv.DictReader(csv_text.splitlines()))
    if not rows:
        return None

    last = rows[-1]
    close = last.get("Close")
    if not close or close == "N/A":
        return None

    try:
        return float(close)
    except ValueError:
        return None

def save_history_csv(name: str, symbol: str, csv_text: str) -> str:
    """
    履歴CSVを保存（Date,Open,High,Low,Close,Volume 形式）
    保存先: history/<name>_<symbol>.csv
    """
    safe_name = name.replace(" ", "_")
    safe_symbol = symbol.replace(".", "_").lower()
    path = os.path.join(HISTORY_DIR, f"{safe_name}_{safe_symbol}.csv")

    # そのまま保存（StooqのCSV形式でOK）
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_text)

    return path

def main():
    now_iso = datetime.now(JST).isoformat()
    data = {"_meta": {"generated_at": now_iso}}

    for name, sym in TICKERS.items():
        price = None
        history_path = None
        error = None

        try:
            csv_text = fetch_daily_csv_stooq(sym)

            # 履歴CSV保存（/signal用）
            history_path = save_history_csv(name, sym, csv_text)

            # 最新終値
            price = parse_last_close(csv_text)

            if price is None:
                error = "Close not found in CSV (maybe N/A)"

        except Exception as e:
            error = f"fetch failed: {type(e).__name__}: {e}"

        payload = {"ticker": sym, "latest_price": price}
        if history_path:
            payload["history_csv"] = os.path.basename(history_path)
        if error:
            payload["error"] = error

        data[name] = payload

    # JSON保存（日本語そのまま）
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ログ
    print("updated:", data["_meta"]["generated_at"])
    for k, v in data.items():
        if k != "_meta":
            print(k, v.get("ticker"), v.get("latest_price"), v.get("history_csv"), v.get("error"))

if __name__ == "__main__":
    main()