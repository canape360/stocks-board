import os, csv
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _ema(values, span):
    alpha = 2.0 / (span + 1.0)
    ema = None
    out = []
    for v in values:
        if ema is None:
            ema = v
        else:
            ema = alpha * v + (1 - alpha) * ema
        out.append(ema)
    return out

def _rsi_wilder(closes, period=14):
    if len(closes) < period + 2:
        return []

    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsis = [None] * period

    rs = (avg_gain / avg_loss) if avg_loss != 0 else float("inf")
    rsis.append(100.0 - (100.0 / (1.0 + rs)))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = (avg_gain / avg_loss) if avg_loss != 0 else float("inf")
        rsis.append(100.0 - (100.0 / (1.0 + rs)))

    return rsis

def detect_signal_from_csv(csv_filename: str, ticker_label: str):
    csv_path = os.path.join(BASE_DIR, "history", csv_filename)

    if not os.path.exists(csv_path):
        return {
            "ticker": ticker_label,
            "signal": "NO_LOCAL_DATA",
            "error": f"missing file: history/{csv_filename}",
            "time": datetime.now(JST).isoformat(),
        }

    closes = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "Close" not in reader.fieldnames:
            return {
                "ticker": ticker_label,
                "signal": "BAD_CSV",
                "error": f"Close column not found. columns={reader.fieldnames}",
                "time": datetime.now(JST).isoformat(),
            }
        for row in reader:
            try:
                closes.append(float(row["Close"]))
            except Exception:
                continue

    if len(closes) < 60:
        return {
            "ticker": ticker_label,
            "signal": "INSUFFICIENT_DATA",
            "rows": len(closes),
            "time": datetime.now(JST).isoformat(),
        }

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    sig = _ema(macd, 9)
    hist = [m - s for m, s in zip(macd, sig)]
    rsi = _rsi_wilder(closes, 14)

    if len(hist) < 2 or len(rsi) < 2 or rsi[-1] is None or rsi[-2] is None:
        return {
            "ticker": ticker_label,
            "signal": "INSUFFICIENT_DATA",
            "time": datetime.now(JST).isoformat(),
        }

    latest_hist, prev_hist = hist[-1], hist[-2]
    latest_rsi, prev_rsi = rsi[-1], rsi[-2]
    latest_macd, latest_sig = macd[-1], sig[-1]

    signal = "NONE"
    if (latest_hist > prev_hist) and (latest_rsi > prev_rsi) and (latest_macd < latest_sig):
        signal = "BUY_SETUP"

    return {
        "ticker": ticker_label,
        "signal": signal,
        "close": closes[-1],
        "macd": latest_macd,
        "signal_line": latest_sig,
        "hist": latest_hist,
        "rsi": latest_rsi,
        "time": datetime.now(JST).isoformat(),
    }