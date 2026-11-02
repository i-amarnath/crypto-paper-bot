# Crypto paper-trading trial (🟢 RUNNING - 48.0h left)

Fake money, real binance_vision prices. Started **02 Nov 16:03 IST**, ends **04 Nov 16:03 IST**. Each strategy started with **$50**. Coins: BTC, ETH, SOL, XRP, DOGE on 15m candles. Fees 0.1%/side + 0.05% slippage included. Last update 02 Nov 16:03 IST (run #1).

| Account | Equity | P&L | Return | Trades | Win rate | Open |
|---|---:|---:|---:|---:|---:|---:|
| **trend** | $50.00 | $+0.00 | +0.00% | 0 | - | 0 |
| **meanrev** | $50.00 | $+0.00 | +0.00% | 0 | - | 0 |
| **breakout** | $50.00 | $+0.00 | +0.00% | 0 | - | 0 |
| *buy & hold (benchmark)* | $49.95 | $-0.05 | -0.10% | - | - | - |

![equity](equity.png)

## Strategies

- **trend**: Trend - EMA 9/21 crossover above EMA 200. SL 2xATR, TP 4xATR, exits on cross-down
- **meanrev**: Mean reversion - RSI(14) bounces back over 35 in an uptrend. SL 1.5xATR, TP 2xATR, 6h time stop
- **breakout**: Breakout - close above 20-candle high on 1.5x volume. SL 1.5xATR, trailing stop 2xATR

## Open positions

None.

## Last 25 closed trades

No closed trades yet.

_Two days is a tiny sample: treat this as a smoke test, not proof a strategy works._
