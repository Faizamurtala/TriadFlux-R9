from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd
import yaml
from engine import build_features, make_decision, ShadowScorecard, STRATEGIES, classify_regime


def load_cfg():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def metrics(equity: pd.Series):
    r = equity.pct_change().fillna(0)
    ann = np.sqrt(252*24*4)  # assumes 15m bars; adjust if using another interval
    sharpe = ann*r.mean()/r.std() if r.std() else 0
    downside = r[r<0].std()
    sortino = ann*r.mean()/downside if downside else 0
    peak = equity.cummax()
    dd = equity/peak-1
    return {
        "total_return": float(equity.iloc[-1]/equity.iloc[0]-1),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(dd.min()),
        "win_rate": float((r>0).mean()),
    }


def run(csv_path):
    cfg = load_cfg()
    df = pd.read_csv(csv_path, parse_dates=["timestamp"]).set_index("timestamp")
    required = {"open","high","low","close","volume"}
    missing = required - set(df.columns)
    if missing: raise ValueError(f"Missing columns: {missing}")
    x = build_features(df, cfg).dropna().copy()
    split = max(1, len(x)-int(30*24*4))
    equity = cfg["risk"]["initial_equity"]
    ledger = ShadowScorecard(cfg["risk"]["performance_lookback"], cfg["risk"]["min_strategy_trades"])
    position = None
    rows = []

    prev_signals = None
    prev_regime = None
    for ts, row in x.iterrows():
        # Score every strategy in parallel using only the next bar's close.
        # This is the regime-performance feedback loop.
        if prev_signals is not None:
            for sig in prev_signals:
                ledger.record(sig.strategy, prev_regime, sig.side, sig.entry, row["close"])

        if position:
            # Conservative bar execution: stop first if both stop and target are touched.
            hit_stop = (row.low <= position["stop"]) if position["side"] == 1 else (row.high >= position["stop"])
            hit_target = (row.high >= position["target"]) if position["side"] == 1 else (row.low <= position["target"])
            exit_px = None
            why = None
            if hit_stop:
                exit_px, why = position["stop"], "stop"
            elif hit_target:
                exit_px, why = position["target"], "target"
            if exit_px is not None:
                gross = position["side"] * (exit_px-position["entry"]) * position["units"]
                fees = (position["entry"]+exit_px)*position["units"]*cfg["risk"]["fee_bps"]/10000
                slip = (position["entry"]+exit_px)*position["units"]*cfg["risk"]["slippage_bps"]/10000
                pnl = gross-fees-slip
                equity += pnl
                rows.append({"timestamp":ts,"type":"EXIT","strategy":position["strategy"],"regime":position["regime"],"pnl":pnl,"equity":equity,"why":why})
                position = None

        d = make_decision(row, equity, ledger, cfg)
        regime_now, _ = classify_regime(row, cfg)
        prev_signals = [fn(row) for fn in STRATEGIES]
        prev_regime = regime_now.value

        if position is None and d.side != 0 and d.size > 0:
            position = {"strategy":d.best_strategy,"regime":d.regime,"side":d.side,
                        "entry":d.entry,"stop":d.stop,"target":d.target,"units":d.size}
            rows.append({"timestamp":ts,"type":"ENTRY","strategy":d.best_strategy,
                         "regime":d.regime,"pnl":0,"equity":equity})

    out = pd.DataFrame(rows)
    os.makedirs("logs", exist_ok=True)
    out.to_csv("logs/backtest_trades.csv", index=False)
    with open("logs/regime_ledger.csv","w") as f:
        ledger.table().to_csv(f,index=False)
    report = {
        "bars": len(x),
        "in_sample_bars": split,
        "out_of_sample_bars": max(0,len(x)-split),
        "final_equity": equity,
        "trade_count": int((out.type=="EXIT").sum()) if not out.empty else 0,
        "regime_strategy_table": ledger.table().to_dict(orient="records"),
    }
    with open("logs/backtest_summary.json","w") as f: json.dump(report,f,indent=2,default=str)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--symbol", default="DEMO")
    args=ap.parse_args()
    run(args.csv)
