from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests
import yaml

from engine import STRATEGIES, ShadowScorecard, build_features, make_decision

BASE_URL = os.getenv("BITGET_REST_URL", "https://api.bitget.com")


def fetch_candles(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    """Fetch public Bitget UTA/Reality market candles.

    Reality symbols are supported by Bitget's v3 market candle endpoint.
    The runner deliberately uses only closed candles for decisions.
    """
    url = f"{BASE_URL}/api/v3/market/candles"
    params = {
        "category": "SPOT",
        "symbol": symbol,
        "interval": interval,
        "limit": min(int(limit), 1000),
        "type": "market",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    payload = r.json()
    if payload.get("code") != "00000":
        raise RuntimeError(f"Bitget API error: {payload}")

    rows = payload.get("data", [])
    if not rows:
        raise RuntimeError(f"No candle data returned for {symbol}")

    # v3 returns [timestamp, open, high, low, close, base_volume, quote_turnover].
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume", "turnover"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"]).sort_values("timestamp")
    return df.set_index("timestamp")


def drop_open_candle(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Remove the currently forming candle so no future information leaks into a decision."""
    minutes = {"1m": 1, "5m": 5, "15m": 15, "1H": 60, "4H": 240, "1D": 1440}[interval]
    now = pd.Timestamp.now(tz="UTC")
    last_ts = df.index[-1]
    age_seconds = (now - last_ts).total_seconds()
    if age_seconds < minutes * 60:
        return df.iloc[:-1].copy()
    return df.copy()


def append_jsonl(path: str, event: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def main(symbol: str, interval: str, poll_seconds: int, limit: int):
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # ShadowScorecard lets all three strategies be evaluated in parallel.
    ledger = ShadowScorecard(
        cfg["risk"]["performance_lookback"],
        cfg["risk"]["min_strategy_trades"],
    )
    equity = float(cfg["risk"]["initial_equity"])
    last_closed_bar = None
    previous_signals = None
    previous_regime = None

    print(f"TriadFlux R9 live-paper runner: {symbol} {interval}")
    print(f"Public Bitget market data: {BASE_URL}")
    print("Execution mode: PAPER DECISIONS ONLY")

    while True:
        try:
            raw = fetch_candles(symbol, interval, limit)
            df = drop_open_candle(raw, interval)
            if len(df) < 80:
                raise RuntimeError(f"Need more history; only {len(df)} closed candles available")

            x = build_features(df, cfg).dropna().copy()
            if x.empty:
                raise RuntimeError("Feature frame is empty after warm-up")

            row = x.iloc[-1]
            closed_bar = x.index[-1]

            if closed_bar != last_closed_bar:
                # Score the previous bar's signals using this bar's close.
                if previous_signals is not None:
                    for sig in previous_signals:
                        ledger.record(sig.strategy, previous_regime, sig.side, sig.entry, float(row["close"]))

                decision = make_decision(row, equity, ledger, cfg)
                signals = [fn(row) for fn in STRATEGIES]
                table = ledger.table()

                event = {
                    "timestamp": str(closed_bar),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "interval": interval,
                    "mode": "PAPER",
                    "regime": decision.regime,
                    "regime_confidence": decision.regime_confidence,
                    "best_strategy": decision.best_strategy,
                    "aggregate_score": decision.aggregate_score,
                    "side": decision.side,
                    "size": decision.size,
                    "entry": decision.entry,
                    "stop": decision.stop,
                    "target": decision.target,
                    "close": float(row["close"]),
                    "reasons": decision.reasons,
                    "strategy_signals": [
                        {"strategy": s.strategy, "side": s.side, "score": s.score, "reason": s.reason}
                        for s in signals
                    ],
                    "scorecard": table.to_dict(orient="records"),
                }
                print(json.dumps(event, default=str))
                append_jsonl("logs/paper_decisions.jsonl", event)

                previous_signals = signals
                previous_regime = decision.regime
                last_closed_bar = closed_bar

            time.sleep(max(5, poll_seconds))

        except KeyboardInterrupt:
            print("Stopping TriadFlux R9 paper runner.")
            return
        except Exception as exc:
            error = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "PAPER",
                "error": type(exc).__name__,
                "message": str(exc),
            }
            print(json.dumps(error))
            append_jsonl("logs/errors.jsonl", error)
            time.sleep(max(10, poll_seconds))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="rAAPLUSDT")
    ap.add_argument("--interval", default="15m", choices=["1m", "5m", "15m", "1H", "4H", "1D"])
    ap.add_argument("--poll", type=int, default=20)
    ap.add_argument("--limit", type=int, default=300)
    args = ap.parse_args()
    main(args.symbol, args.interval, args.poll, args.limit)
