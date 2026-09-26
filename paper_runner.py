import argparse, time, os, json
import pandas as pd, yaml
from engine import build_features, make_decision, RegimeLedger

def main(path, symbol, interval):
    with open("config.yaml") as f: cfg=yaml.safe_load(f)
    ledger=RegimeLedger(cfg["risk"]["performance_lookback"], cfg["risk"]["min_strategy_trades"])
    equity=cfg["risk"]["initial_equity"]
    last=None
    os.makedirs("logs",exist_ok=True)
    df=pd.read_csv(path,parse_dates=["timestamp"]).set_index("timestamp")
    while True:
        x=build_features(df.iloc[:],cfg)
        row=x.iloc[-1]
        if last != row.name:
            d=make_decision(row,equity,ledger,cfg)
            event={"timestamp":str(row.name),"symbol":symbol,"regime":d.regime,
                   "regime_confidence":d.regime_confidence,"best_strategy":d.best_strategy,
                   "aggregate_score":d.aggregate_score,"side":d.side,"size":d.size,
                   "entry":d.entry,"stop":d.stop,"target":d.target,"reasons":d.reasons}
            print(json.dumps(event))
            with open("logs/paper_decisions.jsonl","a") as f: f.write(json.dumps(event)+"\n")
            last=row.name
        time.sleep(interval)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",required=True); ap.add_argument("--symbol",default="DEMO"); ap.add_argument("--interval",type=int,default=5)
    a=ap.parse_args(); main(a.csv,a.symbol,a.interval)
