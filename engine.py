from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Tuple
import math
import numpy as np
import pandas as pd


class Regime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"


class Side(int, Enum):
    SHORT = -1
    FLAT = 0
    LONG = 1


@dataclass
class Signal:
    strategy: str
    score: float
    side: int
    entry: float
    stop: float | None
    target: float | None
    reason: str


@dataclass
class Decision:
    timestamp: str
    regime: str
    regime_confidence: float
    best_strategy: str
    aggregate_score: float
    side: int
    size: float
    entry: float
    stop: float | None
    target: float | None
    reasons: List[str]


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]).abs(),
         (df["high"] - prev).abs(),
         (df["low"] - prev).abs()],
        axis=1
    ).max(axis=1)
    return tr.rolling(n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    down = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False).mean()
    ad = down.ewm(alpha=1/n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    a = atr(df, n)
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / a.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / a.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.ewm(alpha=1/n, adjust=False).mean()


def efficiency_ratio(s: pd.Series, n: int = 20) -> pd.Series:
    direction = (s - s.shift(n)).abs()
    noise = s.diff().abs().rolling(n).sum()
    return direction / noise.replace(0, np.nan)


def zscore(s: pd.Series, n: int = 20) -> pd.Series:
    m = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return (s - m) / sd.replace(0, np.nan)


def build_features(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    x = df.copy().sort_index()
    f = cfg["features"]
    x["atr"] = atr(x, f["atr_window"])
    x["atr_pct"] = x["atr"] / x["close"]
    x["ema_fast"] = ema(x["close"], f["trend_fast"])
    x["ema_slow"] = ema(x["close"], f["trend_slow"])
    x["adx"] = adx(x, f["adx_window"])
    x["er"] = efficiency_ratio(x["close"], f["trend_slow"])
    x["rsi"] = rsi(x["close"], 14)
    x["vol_z"] = zscore(x["atr_pct"], f["volatility_window"])
    x["vol_ratio"] = x["volume"] / x["volume"].rolling(f["volume_window"]).mean()
    w = f["breakout_window"]
    x["donchian_hi"] = x["high"].rolling(w).max().shift(1)
    x["donchian_lo"] = x["low"].rolling(w).min().shift(1)
    m = f["mean_window"]
    x["mean"] = x["close"].rolling(m).mean()
    x["std"] = x["close"].rolling(m).std()
    x["z"] = (x["close"] - x["mean"]) / x["std"].replace(0, np.nan)
    return x


def classify_regime(row: pd.Series, cfg: dict) -> Tuple[Regime, float]:
    if pd.isna(row["adx"]) or pd.isna(row["vol_z"]) or pd.isna(row["er"]):
        return Regime.RANGING, 0.0

    # Volatility has priority because a high-volatility shock can invalidate
    # ordinary trend/range assumptions.
    if row["vol_z"] >= cfg["regime"]["volatility_z_volatile"]:
        conf = min(1.0, 0.55 + 0.15 * min(row["vol_z"], 3.0))
        return Regime.VOLATILE, conf

    if row["adx"] >= cfg["regime"]["adx_trending"] and row["er"] >= cfg["regime"]["efficiency_trending"]:
        conf = min(1.0, 0.55 + (row["adx"] - 25) / 50 + (row["er"] - 0.35))
        return Regime.TRENDING, max(0.55, conf)

    # Explicitly call low-ADX conditions ranging rather than forcing a trade.
    conf = min(1.0, 0.55 + max(0.0, cfg["regime"]["adx_ranging"] - row["adx"]) / 30)
    return Regime.RANGING, max(0.55, conf)


def momentum_breakout(row: pd.Series) -> Signal:
    p, a = row["close"], row["atr"]
    if not np.isfinite(a) or a <= 0:
        return Signal("momentum_breakout", 0, 0, p, None, None, "warmup")
    if p > row["donchian_hi"] and row["vol_ratio"] >= 1.10:
        score = min(1.0, 0.5 + 0.25 * min(row["vol_ratio"] - 1.10, 1.0))
        return Signal("momentum_breakout", score, 1, p, p-1.8*a, p+3*a, "upper breakout + volume")
    if p < row["donchian_lo"] and row["vol_ratio"] >= 1.10:
        score = min(1.0, 0.5 + 0.25 * min(row["vol_ratio"] - 1.10, 1.0))
        return Signal("momentum_breakout", score, -1, p, p+1.8*a, p-3*a, "lower breakout + volume")
    return Signal("momentum_breakout", 0, 0, p, None, None, "no breakout")


def mean_reversion_fade(row: pd.Series) -> Signal:
    p, a, z = row["close"], row["atr"], row["z"]
    if not np.isfinite(a) or not np.isfinite(z) or a <= 0:
        return Signal("mean_reversion_fade", 0, 0, p, None, None, "warmup")
    if z <= -2.0 and row["rsi"] < 35:
        return Signal("mean_reversion_fade", min(1.0, abs(z)/3), 1, p, p-1.5*a, row["mean"], "oversold deviation")
    if z >= 2.0 and row["rsi"] > 65:
        return Signal("mean_reversion_fade", min(1.0, abs(z)/3), -1, p, p+1.5*a, row["mean"], "overbought deviation")
    return Signal("mean_reversion_fade", 0, 0, p, None, None, "inside fade band")


def trend_following(row: pd.Series) -> Signal:
    p, a = row["close"], row["atr"]
    if not np.isfinite(a) or a <= 0:
        return Signal("trend_following", 0, 0, p, None, None, "warmup")
    spread = (row["ema_fast"] - row["ema_slow"]) / p
    if row["ema_fast"] > row["ema_slow"] and row["adx"] >= 20:
        return Signal("trend_following", min(1.0, 0.45 + 5*abs(spread)), 1, p, p-1.8*a, p+3*a, "EMA trend + ADX")
    if row["ema_fast"] < row["ema_slow"] and row["adx"] >= 20:
        return Signal("trend_following", min(1.0, 0.45 + 5*abs(spread)), -1, p, p+1.8*a, p-3*a, "EMA trend + ADX")
    return Signal("trend_following", 0, 0, p, None, None, "trend not confirmed")


STRATEGIES = [momentum_breakout, mean_reversion_fade, trend_following]


class RegimeLedger:
    """Tracks realized strategy returns separately for each regime."""

    def __init__(self, lookback=40, min_trades=8, prior=0.0):
        self.lookback = lookback
        self.min_trades = min_trades
        self.prior = prior
        self.rows: List[dict] = []

    def record(self, strategy: str, regime: str, pnl_return: float):
        self.rows.append({"strategy": strategy, "regime": regime, "ret": float(pnl_return)})
        self.rows = self.rows[-(self.lookback * 20):]

    def table(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(columns=["strategy","regime","n","mean_ret","sharpe"])
        d = pd.DataFrame(self.rows)
        out = []
        for (s, r), g in d.groupby(["strategy","regime"]):
            mu = g["ret"].mean()
            sd = g["ret"].std(ddof=1)
            shrunk = (len(g)*mu + self.min_trades*self.prior)/(len(g)+self.min_trades)
            sharpe = shrunk / sd * math.sqrt(max(1, len(g))) if sd and np.isfinite(sd) else 0.0
            out.append({"strategy":s,"regime":r,"n":len(g),"mean_ret":shrunk,"sharpe":sharpe})
        return pd.DataFrame(out)

    def scores(self, regime: str) -> Dict[str, float]:
        t = self.table()
        names = ["momentum_breakout","mean_reversion_fade","trend_following"]
        vals = {n: 0.0 for n in names}
        if t.empty:
            return vals
        q = t[t.regime == regime]
        for _, row in q.iterrows():
            # Conservative score: shrink small samples toward zero.
            vals[row.strategy] = float(row.sharpe) * min(1.0, row.n / self.min_trades)
        return vals

    def best(self, regime: str) -> str:
        s = self.scores(regime)
        return max(s, key=s.get)



class ShadowScorecard:
    """Online, leakage-safe one-bar attribution for every strategy.

    Every strategy is evaluated in parallel. When a bar closes, the previous
    bar's signal is scored against the new close. This lets the allocator learn
    which strategy has actually worked in the current regime without requiring
    that strategy to have been selected for the real/paper portfolio.
    """

    def __init__(self, lookback=80, min_trades=8, prior=0.0):
        self.lookback = lookback
        self.min_trades = min_trades
        self.prior = prior
        self.rows = []

    def record(self, strategy: str, regime: str, side: int, entry: float, exit_price: float):
        if side == 0 or not np.isfinite(entry) or entry <= 0:
            return
        ret = side * (exit_price - entry) / entry
        self.rows.append({"strategy": strategy, "regime": regime, "ret": float(ret)})
        self.rows = self.rows[-(self.lookback * 20):]

    def table(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(columns=["strategy","regime","n","mean_ret","sharpe"])
        d = pd.DataFrame(self.rows)
        out = []
        for (s,r),g in d.groupby(["strategy","regime"]):
            mu, sd = g.ret.mean(), g.ret.std(ddof=1)
            shrunk = (len(g)*mu + self.min_trades*self.prior)/(len(g)+self.min_trades)
            sharpe = (shrunk/sd)*np.sqrt(len(g)) if sd and np.isfinite(sd) else 0.0
            out.append({"strategy":s,"regime":r,"n":len(g),"mean_ret":shrunk,"sharpe":sharpe})
        return pd.DataFrame(out)

    def scores(self, regime: str) -> Dict[str,float]:
        t=self.table()
        vals={s:0.0 for s in ["momentum_breakout","mean_reversion_fade","trend_following"]}
        if t.empty: return vals
        for _,r in t[t.regime==regime].iterrows():
            vals[r.strategy]=float(r.sharpe)*min(1.0,r.n/self.min_trades)
        return vals

    def best(self, regime: str) -> str:
        return max(self.scores(regime), key=self.scores(regime).get)

class Allocator:
    def __init__(self, ledger: RegimeLedger, cfg: dict):
        self.ledger = ledger
        self.cfg = cfg

    def allocate(self, regime: str, signals: List[Signal]) -> Tuple[float, str, List[str]]:
        active = {s.strategy: s for s in signals if s.side != 0 and s.score > 0}
        if not active:
            return 0.0, "none", ["NO_TRADE: no strategy has a valid signal"]

        scores = self.ledger.scores(regime)
        ranked = sorted(active.keys(), key=lambda x: (scores.get(x,0), active[x].score), reverse=True)
        best = ranked[0]
        weights = {best: self.cfg["allocation"]["best_strategy_weight"]}
        if len(ranked) > 1:
            weights[ranked[1]] = self.cfg["allocation"]["second_strategy_weight"]
        if len(ranked) > 2:
            weights[ranked[2]] = self.cfg["allocation"]["third_strategy_weight"]

        signed = sum(weights[k] * active[k].side * active[k].score for k in ranked)
        reasons = [f"{k}: side={active[k].side:+d}, score={active[k].score:.2f}, regime_sharpe={scores.get(k,0):.2f}" for k in ranked]
        return float(signed), best, reasons


class RiskEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def size(self, equity: float, entry: float, stop: float, confidence: float) -> float:
        if confidence < self.cfg["risk"]["min_regime_confidence"]:
            return 0.0
        risk_cash = equity * self.cfg["risk"]["max_risk_per_trade"] * confidence
        unit_risk = abs(entry - stop)
        if unit_risk <= 0:
            return 0.0
        return max(0.0, risk_cash / unit_risk)

    def cap_notional(self, units: float, entry: float, equity: float) -> float:
        max_notional = equity * self.cfg["risk"]["max_gross_exposure"]
        return min(units, max_notional / entry)


def make_decision(row: pd.Series, equity: float, ledger, cfg: dict) -> Decision:
    regime, conf = classify_regime(row, cfg)
    signals = [fn(row) for fn in STRATEGIES]
    agg, best, reasons = Allocator(ledger, cfg).allocate(regime.value, signals)

    if conf < cfg["risk"]["min_regime_confidence"] or abs(agg) < cfg["risk"]["min_signal_score"]:
        return Decision(str(row.name), regime.value, conf, best, agg, 0, 0, row["close"], None, None,
                        reasons + ["NO_TRADE: confidence/signal gate"])

    chosen = next((s for s in signals if s.strategy == best and s.side != 0), None)
    if chosen is None:
        chosen = max(signals, key=lambda s: abs(s.score))
    side = 1 if agg > 0 else -1
    if chosen.side != side:
        # Disagreement is treated as a veto rather than forcing a reversal.
        return Decision(str(row.name), regime.value, conf, best, agg, 0, 0, row["close"], None, None,
                        reasons + ["NO_TRADE: strategy direction disagreement"])

    risk = RiskEngine(cfg)
    units = risk.size(equity, chosen.entry, chosen.stop, conf)
    units = risk.cap_notional(units, chosen.entry, equity)
    return Decision(str(row.name), regime.value, conf, best, agg, side, units,
                    chosen.entry, chosen.stop, chosen.target, reasons)


def update_ledger_after_trade(ledger: RegimeLedger, strategy: str, regime: str, entry: float, exit_price: float, side: int):
    ret = side * (exit_price - entry) / entry
    ledger.record(strategy, regime, ret)
