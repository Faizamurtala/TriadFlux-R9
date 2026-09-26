# TriadFlux R9

**Regime-aware parallel trading engine for the Bitget AI Base Camp Hackathon S2.**

TriadFlux R9 runs three deterministic strategies in parallel:

1. Momentum Breakout
2. Mean-Reversion Fade
3. Trend-Following

A regime engine continuously classifies the market as **TRENDING**, **RANGING**, or **VOLATILE**. Every strategy is evaluated independently, while a regime-performance ledger tracks realized strategy outcomes by regime. The allocator then gives more weight to strategies that have demonstrated stronger risk-adjusted performance in the *current* regime, subject to minimum sample and drawdown guards.

The core signal is deterministic. An optional Qwen module can explain the decision, but it does not create the trade signal. This keeps the alpha testable and auditable.

> Important: no strategy can guarantee profit. The repository is paper-trading-first and defaults to `PAPER=true`.

## Hackathon fit

This project is designed for **Track 1 — Alpha Factory / Open Theme** because the handbook explicitly lists **market regime / adaptive portfolio systems that adjust signals, positions, and risk budgets across market regimes** as an example Open Theme direction. The track requires runnable strategy code and a verifiable backtest with total period >=60 days and out-of-sample >=30 days.

The architecture can also be demonstrated as a paper-trading service using Bitget Agent Hub, but the LLM is not the primary decision-maker, so it should not be presented as an Agentic Trading-track submission unless the system is extended so an LLM autonomously senses, decides, and executes.

## Architecture

```text
                 ┌───────────────────────┐
                 │  OHLCV / Market Feed  │
                 └───────────┬───────────┘
                             │
                  ┌──────────▼──────────┐
                  │ Feature + Regime     │
                  │ TREND / RANGE / VOL  │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
   │ Breakout    │    │ Mean Fade   │    │ Trend       │
   │ Momentum    │    │ Reversion   │    │ Following   │
   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                 ┌───────────▼────────────┐
                 │ Regime Performance     │
                 │ Ledger + Risk Gate     │
                 └───────────┬────────────┘
                             │
                    ┌────────▼────────┐
                    │ BUY / SELL /    │
                    │ FLAT + size     │
                    └────────┬────────┘
                             │
                ┌────────────▼────────────┐
                │ Paper Executor + Audit  │
                └─────────────────────────┘
```

## What makes it different

The novelty is not "three indicators." It is the **closed-loop regime attribution**:

- all three strategies continue to generate independent signals;
- the system records which strategy actually made money/lost money in each regime;
- performance is evaluated only on information available before the trade;
- the current regime controls the allocation weights;
- a minimum-trade shrinkage rule prevents a strategy from becoming "winner" after one lucky trade;
- the system can enter **NO TRADE** when the regime is uncertain, volatility is extreme, or all strategies disagree;
- every decision is written to JSONL for auditability.

This is intentionally different from event/news/LLM-first projects in the supplied handbook examples.

## Quick start

### 1. Python

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Generate a reproducible sample dataset

```bash
python generate_sample_data.py
```

### 3. Run the backtest

```bash
python backtest.py --csv data/sample_ohlcv.csv --symbol DEMO
```

The engine automatically creates an in-sample / out-of-sample split. For the hackathon, replace the sample data with at least 60 calendar/trading days of real historical data and keep >=30 days untouched as out-of-sample validation.

### 4. Run the live paper loop

```bash
python paper_runner.py --csv data/sample_ohlcv.csv --symbol DEMO --interval 5
```

The CSV runner simulates new bars arriving every `interval` seconds. In production, replace the feed adapter with your Bitget/Agent Hub market-data adapter.

### 5. Dashboard

```bash
streamlit run dashboard.py
```

## Live deployment

Recommended first deployment:

- Docker container
- `PAPER=true`
- isolated Bitget demo/Agentic account if using Agent Hub
- no withdrawal permissions
- dry-run/order-preview before any write
- persistent volume for `logs/`

The supplied handbook specifically recommends Bitget Agent Hub safe mode, including `--read-only`, `--paper-trading`, and `dryRun` before write operations.

## Files

- `engine.py` — indicators, regime classifier, strategies, allocator, risk engine.
- `backtest.py` — reproducible backtest + OOS report.
- `paper_runner.py` — continuously evaluates bars and logs paper decisions.
- `dashboard.py` — simple Streamlit monitoring UI.
- `generate_sample_data.py` — synthetic test data only.
- `config.yaml` — parameters and risk controls.
- `Dockerfile` — container deployment.
- `docker-compose.yml` — persistent paper-trading service.
- `requirements.txt` — Python dependencies.

## Safety defaults

- Paper trading only.
- No private key is stored in source code.
- No live order function is implemented in the core engine.
- Max risk per trade and max portfolio exposure are enforced.
- Stop-loss and take-profit are attached to every non-flat paper position.
- The engine can output `NO_TRADE`.
- Kill switch: set `ENABLED=false` or stop the container.

## Backtest protocol

For a credible submission:

1. Select a fixed universe of tokenized US equities supported by your market-data venue.
2. Use a fixed bar interval (e.g. 5m or 15m).
3. Build the feature set without future information.
4. Split chronologically, never randomly.
5. Keep >=60 days total and >=30 days OOS, matching the handbook.
6. Include fees and slippage.
7. Report total return, Sharpe, Sortino, max drawdown, win rate, turnover, and rolling 30-day Sharpe.
8. Report regime-specific performance and strategy attribution.
9. Do not optimize thresholds on the OOS window.
10. If OOS Sharpe is <0.5× IS Sharpe, treat it as an overfit warning and explain it.

## Submission checklist

The handbook requires the form to contain:

- complete Project Description;
- Role of the LLM;
- Submission Materials Link;
- compliant X promotional post;
- Track → Sub-theme;
- optionally University Name;
- optionally Apply for Demo Day;
- optionally K3 subsidy.

For Alpha Factory specifically:

- alpha source / signal logic;
- strategy code;
- backtest record >=60 days total and >=30 days OOS;
- compliant X post.

Do not claim observed returns until the system has produced the corresponding logs.

## Disclaimer

This is software for research and paper trading. It is not investment advice. Real-money trading can lose capital.
