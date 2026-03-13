from signal_detector import detect_signal_from_csv
from flask import Flask, Response, send_from_directory, request
import json
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "latest.json")


def json_response(payload, status=200):
    resp = Response(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json; charset=utf-8",
        status=status,
    )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


def load_latest_json():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError("latest.json がありません")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def available_signal_names(latest: dict):
    names = []
    for k, v in latest.items():
        if k == "_meta":
            continue
        if isinstance(v, dict):
            names.append(k)
    return names


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/stocks/latest")
def latest():
    try:
        data = load_latest_json()
        return json_response(data)
    except Exception as e:
        return json_response({"error": str(e)}, status=500)


@app.route("/signal")
def signal_one():
    """
    例:
      /signal?name=ホンダ
      /signal?name=日本製鉄
      /signal?name=日立製作所

    name省略時はホンダ
    """
    try:
        name = (request.args.get("name") or "ホンダ").strip()
        latest = load_latest_json()

        if name not in latest:
            return json_response(
                {
                    "error": f"unknown name: {name}",
                    "available": available_signal_names(latest),
                },
                status=400,
            )

        info = latest[name]

        if not isinstance(info, dict):
            return json_response(
                {"error": f"{name} はシグナル対象ではありません"},
                status=400,
            )

        csv_name = info.get("history_csv")
        ticker = info.get("ticker")

        if not csv_name:
            return json_response(
                {"error": f"{name} に history_csv がありません"},
                status=500,
            )

        data = detect_signal_from_csv(csv_name, ticker or name)
        if not isinstance(data, dict):
            return json_response(
                {"error": "signal_detector の返り値がdictではありません"},
                status=500,
            )

        data["name"] = name
        return json_response(data)

    except Exception as e:
        return json_response({"error": str(e)}, status=500)


@app.route("/signals")
def signals_all():
    """
    全銘柄のシグナルをまとめて返す
    """
    try:
        latest = load_latest_json()
        out = {"_meta": latest.get("_meta", {})}

        for name, info in latest.items():
            if name == "_meta":
                continue

            # dict以外（例: FXのlistなど）は対象外
            if not isinstance(info, dict):
                continue

            csv_name = info.get("history_csv")
            ticker = info.get("ticker")

            if not csv_name:
                out[name] = {
                    "ticker": ticker,
                    "signal": "NO_CSV",
                    "error": "history_csv missing",
                }
                continue

            s = detect_signal_from_csv(csv_name, ticker or name)

            if not isinstance(s, dict):
                out[name] = {
                    "ticker": ticker,
                    "signal": "ERROR",
                    "error": "signal_detector returned non-dict",
                }
                continue

            s["name"] = name
            out[name] = s

        return json_response(out)

    except Exception as e:
        return json_response({"error": str(e)}, status=500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)