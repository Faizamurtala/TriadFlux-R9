# TriadFlux R9 — Deployment Guide

## Important distinction

The original CSV runner is a local simulation. This version adds `bitget_live_runner.py`, which reads closed Bitget Reality candles from the public v3 market-data API and writes paper decisions to `logs/paper_decisions.jsonl`.

It does **not** place real orders. Keep it paper-only for the hackathon demo until the strategy has been validated on real historical data and Bitget demo trading.

## 1. Local verification

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python generate_sample_data.py
python backtest.py --csv data/sample_ohlcv.csv --symbol DEMO
streamlit run dashboard.py
```

In a second terminal:

```bash
python bitget_live_runner.py --symbol rAAPLUSDT --interval 15m --poll 20
```

Use `rAAPLUSDT` only if that symbol is available to your Bitget account/market at runtime. The Bitget API documentation uses rAAPLUSDT as a Reality example.

## 2. Recommended hosting: DigitalOcean Docker Droplet

For this project, use one small Linux VM rather than a serverless platform. A persistent VM is easier for a continuously running market-data worker and local JSONL logs.

Recommended setup:

- Ubuntu/Docker Droplet
- 2 vCPU / 2–4 GB RAM is sufficient for this lightweight paper engine
- SSH key authentication
- firewall: allow SSH (22) and dashboard (8501) only while testing
- keep Bitget credentials out of the repository

DigitalOcean provides a Docker 1-Click image with Docker Engine and Docker Compose preinstalled. Their production setup recommends SSH-key authentication and restricting firewall access. urlDigitalOcean Docker imagehttps://docs.digitalocean.com/products/marketplace/catalog/docker/

## 3. Create the server

In DigitalOcean:

1. Create → Droplet.
2. Choose the Docker 1-Click image.
3. Choose a nearby region.
4. Add your SSH public key.
5. Enable monitoring/backups if desired.
6. Create the Droplet.

Then connect:

```bash
ssh root@YOUR_SERVER_IP
```

Create a non-root user before normal operation if you are keeping the server beyond the demo.

## 4. Install the project

On your PC, upload the project or clone your Git repository.

Example with Git:

```bash
git clone YOUR_REPOSITORY_URL
cd TriadFlux_R9
```

If you are uploading the ZIP instead, copy it to the server and run:

```bash
unzip TriadFlux_R9.zip
cd regimeforge
```

## 5. Configure the symbol

```bash
cp .env.example .env
nano .env
```

Set:

```env
BITGET_SYMBOL=rAAPLUSDT
BITGET_INTERVAL=15m
BITGET_POLL_SECONDS=20
```

Do not put API secrets in `.env` because this paper runner does not need them.

## 6. Start TriadFlux

```bash
docker compose build
docker compose up -d
```

Check both services:

```bash
docker compose ps
docker compose logs -f triadflux
```

You should see JSON events containing:

- regime
- regime confidence
- three strategy signals
- best strategy
- aggregate score
- BUY / SELL / NO_TRADE side
- entry / stop / target
- regime scorecard

## 7. Open the dashboard

Find the server IP and open:

```text
http://YOUR_SERVER_IP:8501
```

For a temporary hackathon demo, this is enough. For a public production-style URL, put Caddy or Nginx in front of Streamlit and use HTTPS.

## 8. Verify persistence

The compose file mounts `./logs` into the containers. Check:

```bash
ls -lah logs

tail -f logs/paper_decisions.jsonl
```

If the container restarts, the log files remain on the host.

## 9. Health checks

Every few minutes verify:

```bash
docker compose ps
docker compose logs --tail=100 triadflux
docker compose logs --tail=100 dashboard
```

A normal decision event should contain a current UTC timestamp and a closed candle timestamp.

If Bitget returns an API error, the worker writes it to:

```text
logs/errors.jsonl
```

## 10. Before any real-money execution

Do **not** connect real trading credentials yet.

First:

1. Download at least 60 days of real rToken historical data.
2. Keep at least 30 days completely out-of-sample.
3. Include realistic fees and slippage.
4. Report total return, Sharpe, Sortino, max drawdown, win rate, turnover and rolling 30-day Sharpe.
5. Report strategy attribution by TRENDING/RANGING/VOLATILE regime.
6. Check for overfitting: if OOS Sharpe is less than half IS Sharpe, treat it as a warning.
7. Run the live-paper worker continuously.
8. Then test Bitget Demo Trading with a Demo API key.

Bitget's current documentation provides a Demo Trading environment using a Demo API key and the `paptrading: 1` REST header; demo WebSocket endpoints are separate from the production endpoints. urlBitget Demo Trading APIhttps://www.bitget.com/docs/uta/demo-trading/rest-api

## 11. Bitget API facts used by this build

Bitget's current v3 market-data API supports Reality/rToken symbols and candlesticks. Reality examples use `rAAPLUSDT`; Reality candles support `1m`, `5m`, `15m`, `1H`, `4H`, and `1D`. urlBitget Reality trading guidehttps://www.bitget.com/docs/uta/reality-trading-guide

Bitget also documents `/api/v3/market/candles` and `/api/v3/market/history-candles` for market candles. urlBitget market-data documentationhttps://www.bitget.com/docs/catalog/market/market-data

For a future execution adapter, Bitget currently documents Reality order placement at `/api/v3/trade/place-reality-order` and says Reality pairs are also supported by the regular UTA order endpoint. urlBitget Reality trading APIhttps://www.bitget.com/docs/catalog/reality/trading

## 12. Do not confuse paper mode with live mode

The safest hackathon demonstration is:

`Bitget market data → TriadFlux R9 → BUY/SELL/NO_TRADE → JSONL audit → dashboard`

Only after validation should you add:

`→ Bitget Demo Trading → fill/order monitoring → reconciliation`

Real-money execution is a separate deployment stage.
