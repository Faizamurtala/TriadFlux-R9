# Project Description draft — TriadFlux R9

## 1 · Thesis
TriadFlux R9 is a runnable adaptive quantitative trading system for tokenized US equities. Its core hypothesis is that no single simple trading style should be trusted across all market conditions. The system therefore runs momentum breakout, mean-reversion fade, and trend-following signals in parallel while a deterministic regime engine classifies the current market as TRENDING, RANGING, or VOLATILE. A regime-specific performance ledger measures realized strategy outcomes and adjusts allocation only after enough evidence has accumulated. Risk controls can force NO TRADE when confidence, signal agreement, or exposure constraints are not satisfied.

The system is designed to be auditable: signals, regime labels, selected strategy, position size, stops/targets, and outcomes are logged. Fees and slippage are included in validation.

## 2 · Target user and product value
Target user: a retail/pro trader who trades tokenized US equities at intraday frequency and wants an automated research/paper-execution system rather than a black-box buy/sell bot. The product provides a live regime label, three transparent strategy signals, regime-specific strategy attribution, and a single risk-gated action: BUY, SELL, or NO TRADE.

## 3 · Validation data and key metrics
Validation protocol: at least 60 days total historical data with at least 30 days held out for out-of-sample validation. Metrics: total return, Sharpe, Sortino, maximum drawdown, win rate, turnover, fees/slippage, and rolling 30-day Sharpe. Regime-specific strategy returns and trade counts are also reported. Any results in the final submission will be labelled observed; before running the required data, figures are targets rather than claims.

## 4 · Progress
Built: three deterministic strategies, regime classifier, regime-specific performance ledger, adaptive allocator, risk engine, backtest runner, paper runner, audit logging, dashboard, Docker deployment. Next: connect a Bitget/Agent Hub market-data adapter, run the full OOS test on the selected tokenized-equity universe, run paper trading, and freeze the final parameter set before reporting results.

## 5 · Deliverables
GitHub repository; reproducible backtest; OOS report; paper-trading JSONL logs; dashboard; Docker configuration; short demo video.

## 6 · AI role
LLM use is optional and non-core. If Qwen credits are used, Qwen can be used to generate code, summarize logged decisions, or explain why a deterministic signal was triggered. The model does not alter the core signal calculations or bypass the risk engine. This keeps the alpha source deterministic and verifiable.
