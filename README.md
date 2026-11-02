# Crypto paper-trading bot

Real Binance prices, fake money. Three technical-analysis strategies each get a virtual **$50**
and trade BTC, ETH, SOL, XRP and DOGE on 15-minute candles for **48 hours**, with stop-losses,
take-profits, 0.1% fees and slippage. A buy-and-hold $50 benchmark runs alongside.

**Live results: open [REPORT.md](REPORT.md)** (updates every ~5-15 min).

## How it runs
GitHub Actions runs `bot.py` every ~5 minutes. Each run fetches closed candles, replays every
new candle in order (stops/targets are checked against the real high/low, stop first if both
were hit), looks for entries on candle closes, then commits `state.json`, `trades.csv`,
`equity.csv`, `REPORT.md` and `equity.png` back here. Late or skipped runs don't change results.

## Settings
Edit the top of `bot.py`, or set env vars `START_CAPITAL` / `DURATION_HOURS` in the workflow.
To restart the trial: delete `state.json`, `trades.csv`, `equity.csv`, then press **Run workflow**.
To stop it: Actions tab > paper-trade > "..." > **Disable workflow**.

## Optional Telegram alerts
Add repo secrets `TELEGRAM_TOKEN` (from @BotFather) and `TELEGRAM_CHAT_ID`
(Settings > Secrets and variables > Actions). You'll get a ping on every buy/sell.

## Test
`python tests/test_sim.py` runs a 48h simulation on synthetic candles and checks: results are
identical whether the bot runs every 5 min or every few hours, accounting balances, and hiding
future data doesn't change past trades.
