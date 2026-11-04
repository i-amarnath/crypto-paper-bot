# Crypto paper-trading trial (🟢 RUNNING - 7.8h left)

Fake money, real binance_vision prices. Started **02 Nov 16:03 IST**, ends **04 Nov 16:03 IST**. Each strategy started with **$50**. Coins: BTC, ETH, SOL, XRP, DOGE on 15m candles. Fees 0.1%/side + 0.05% slippage included. Last update 04 Nov 08:15 IST (run #7).

| Account | Equity | P&L | Return | Trades | Win rate | Open |
|---|---:|---:|---:|---:|---:|---:|
| **trend** | $49.28 | $-0.72 | -1.44% | 8 | 12% | 0 |
| **meanrev** | $49.77 | $-0.23 | -0.45% | 2 | 0% | 0 |
| **breakout** | $49.17 | $-0.83 | -1.66% | 8 | 0% | 0 |
| *buy & hold (benchmark)* | $49.19 | $-0.81 | -1.62% | - | - | - |

![equity](equity.png)

## Strategies

- **trend**: Trend - EMA 9/21 crossover above EMA 200. SL 2xATR, TP 4xATR, exits on cross-down
- **meanrev**: Mean reversion - RSI(14) bounces back over 35 in an uptrend. SL 1.5xATR, TP 2xATR, 6h time stop
- **breakout**: Breakout - close above 20-candle high on 1.5x volume. SL 1.5xATR, trailing stop 2xATR

## Open positions

None.

## Last 25 closed trades

| Strategy | Coin | In | Out | Entry | Exit | P&L | Why |
|---|---|---|---|---:|---:|---:|---|
| trend | DOGE | 04 Nov 02:15 | 04 Nov 06:00 | 0.0752476 | 0.0747678 | $-0.138 (-0.84%) | stop-loss |
| trend | XRP | 04 Nov 02:30 | 04 Nov 05:45 | 1.28024 | 1.27346 | $-0.121 (-0.73%) | EMA cross-down |
| meanrev | ETH | 04 Nov 06:30 | 04 Nov 06:45 | 2275.82 | 2262.86 | $-0.128 (-0.77%) | stop-loss |
| trend | ETH | 04 Nov 02:45 | 04 Nov 05:15 | 2295.67 | 2284.14 | $-0.116 (-0.70%) | EMA cross-down |
| breakout | DOGE | 03 Nov 18:00 | 03 Nov 19:00 | 0.0752876 | 0.0748684 | $-0.124 (-0.76%) | stop-loss |
| breakout | XRP | 03 Nov 18:00 | 03 Nov 20:45 | 1.28214 | 1.27453 | $-0.131 (-0.79%) | stop-loss |
| trend | XRP | 03 Nov 13:00 | 03 Nov 18:00 | 1.25633 | 1.26921 | $+0.136 (+0.82%) | take-profit |
| breakout | XRP | 03 Nov 16:45 | 03 Nov 17:15 | 1.26053 | 1.25555 | $-0.098 (-0.59%) | stop-loss |
| breakout | SOL | 03 Nov 18:00 | 03 Nov 19:00 | 93.2366 | 92.6959 | $-0.129 (-0.78%) | stop-loss |
| breakout | ETH | 03 Nov 18:00 | 03 Nov 19:45 | 2284.47 | 2277.7 | $-0.082 (-0.50%) | stop-loss |
| breakout | BTC | 03 Nov 16:45 | 03 Nov 19:45 | 77232.2 | 77269.6 | $-0.025 (-0.15%) | trailing stop |
| trend | XRP | 03 Nov 09:30 | 03 Nov 12:15 | 1.25243 | 1.24977 | $-0.068 (-0.41%) | EMA cross-down |
| breakout | XRP | 03 Nov 10:00 | 03 Nov 10:45 | 1.25813 | 1.25201 | $-0.114 (-0.69%) | stop-loss |
| trend | XRP | 02 Nov 19:15 | 02 Nov 19:45 | 1.26163 | 1.25246 | $-0.154 (-0.93%) | stop-loss |
| breakout | XRP | 02 Nov 19:15 | 02 Nov 19:30 | 1.26163 | 1.25459 | $-0.126 (-0.76%) | stop-loss |
| trend | XRP | 02 Nov 18:00 | 02 Nov 18:45 | 1.25423 | 1.24957 | $-0.095 (-0.57%) | EMA cross-down |
| trend | ETH | 02 Nov 20:30 | 02 Nov 21:30 | 2292.94 | 2274.69 | $-0.166 (-0.99%) | stop-loss |
| meanrev | BTC | 02 Nov 19:15 | 02 Nov 19:30 | 78203.1 | 77898.2 | $-0.098 (-0.59%) | stop-loss |

_Two days is a tiny sample: treat this as a smoke test, not proof a strategy works._
