"""
Crypto paper-trading bot: real market data, fake money.

Every run it:
  1. pulls the latest *closed* 15m candles for each coin,
  2. replays every new candle in order (so a delayed run never misses a stop-loss),
  3. checks stops / targets against each candle's real high & low,
  4. looks for new entry signals on the candle close,
  5. saves state + trade log + equity curve + REPORT.md.

Run it as often as you like (GitHub Actions does it every ~5 min). It is safe to
run late or miss runs: it catches up candle by candle.
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

# ----------------------------------------------------------------- settings --
SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
INTERVAL_MIN = 15
START_CAPITAL = float(os.getenv("START_CAPITAL", "50"))
DURATION_HOURS = float(os.getenv("DURATION_HOURS", "48"))
FEE = 0.001          # 0.1% per side (Binance spot taker)
SLIPPAGE = 0.0005    # 0.05% worse fill on market orders / stop-outs
RISK_PER_TRADE = 0.02  # risk 2% of account per trade
MAX_POSITIONS = 3      # per strategy account -> max 1/3 of equity in one coin
MIN_NOTIONAL = 5.0     # Binance minimum order size in USDT

DATA_DIR = os.getenv("BOT_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.csv")
EQUITY_FILE = os.path.join(DATA_DIR, "equity.csv")
REPORT_FILE = os.path.join(DATA_DIR, "REPORT.md")
CHART_FILE = os.path.join(DATA_DIR, "equity.png")
IST = timezone(timedelta(hours=5, minutes=30))

STRATEGIES = {
    "trend": "Trend - EMA 9/21 crossover above EMA 200. SL 2xATR, TP 4xATR, exits on cross-down",
    "meanrev": "Mean reversion - RSI(14) bounces back over 35 in an uptrend. SL 1.5xATR, TP 2xATR, 6h time stop",
    "breakout": "Breakout - close above 20-candle high on 1.5x volume. SL 1.5xATR, trailing stop 2xATR",
}


def now_ms():
    return int(os.getenv("BOT_NOW_MS") or time.time() * 1000)


# --------------------------------------------------------------------- data --
def _binance(base, sym, limit=500):
    r = requests.get(f"{base}/api/v3/klines",
                     params={"symbol": f"{sym}USDT", "interval": f"{INTERVAL_MIN}m", "limit": limit},
                     timeout=15)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume",
                                     "ct", "qv", "n", "tb", "tq", "ig"])
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    return df.astype({"open_time": "int64", "open": float, "high": float, "low": float,
                      "close": float, "volume": float})


def _coinbase(sym, limit=300):
    r = requests.get(f"https://api.exchange.coinbase.com/products/{sym}-USD/candles",
                     params={"granularity": INTERVAL_MIN * 60}, timeout=15,
                     headers={"User-Agent": "paper-bot"})
    r.raise_for_status()
    df = pd.DataFrame(r.json(), columns=["t", "low", "high", "open", "close", "volume"])
    df["open_time"] = df["t"].astype("int64") * 1000
    df = df.sort_values("open_time")[["open_time", "open", "high", "low", "close", "volume"]]
    return df.astype(float).astype({"open_time": "int64"}).tail(limit)


SOURCES = {
    "binance_vision": lambda s: _binance("https://data-api.binance.vision", s),
    "binance": lambda s: _binance("https://api.binance.com", s),
    "coinbase": _coinbase,
}


def fetch_candles(sym, preferred=None):
    """Returns (source_name, df of CLOSED candles). Tries the preferred source first."""
    order = ([preferred] if preferred else []) + [s for s in SOURCES if s != preferred]
    last_err = None
    for name in order:
        try:
            df = SOURCES[name](sym)
            closed = df[df["open_time"] + INTERVAL_MIN * 60_000 <= now_ms()]
            if len(closed) >= 210:
                return name, closed.reset_index(drop=True)
            last_err = f"{name}: only {len(closed)} candles"
        except Exception as e:  # noqa: BLE001
            last_err = f"{name}: {e}"
    raise RuntimeError(last_err)


# --------------------------------------------------------------- indicators --
def add_indicators(df):
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    for n in (9, 21, 50, 200):
        df[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    df["vol_sma"] = v.rolling(20).mean()
    df["dch"] = h.rolling(20).max().shift(1)  # highest high of the PREVIOUS 20 candles

    up = (df["ema9"] > df["ema21"]) & (df["ema9"].shift() <= df["ema21"].shift())
    down = (df["ema9"] < df["ema21"]) & (df["ema9"].shift() >= df["ema21"].shift())
    df["trend_entry"] = up & (c > df["ema200"])
    df["trend_exit"] = down
    df["meanrev_entry"] = (df["rsi"].shift() < 35) & (df["rsi"] >= 35) & (c > df["ema200"])
    df["breakout_entry"] = (c > df["dch"]) & (v > 1.5 * df["vol_sma"]) & (c > df["ema50"])
    # first 200 candles are warm-up; never trade on them
    df.loc[: 199, ["trend_entry", "meanrev_entry", "breakout_entry"]] = False
    return df


def entry_levels(strategy, price, atr):
    if strategy == "trend":
        return price - 2 * atr, price + 4 * atr
    if strategy == "meanrev":
        return price - 1.5 * atr, price + 2 * atr
    return price - 1.5 * atr, None  # breakout: trailing stop only


# -------------------------------------------------------------------- state --
def new_state():
    t = now_ms()
    return {
        "started_at": t,
        "ends_at": t + int(DURATION_HOURS * 3600_000),
        "finished": False,
        "capital": START_CAPITAL,
        "source": None,
        "last_ts": {},
        "start_price": {},
        "last_price": {},
        "accounts": {s: {"cash": START_CAPITAL, "positions": {}} for s in STRATEGIES},
        "runs": 0,
        "errors": [],
    }


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return new_state()


def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=1)


def append_csv(path, row, header):
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        w.writerow(row)


TRADE_COLS = ["strategy", "symbol", "entry_time", "entry_price", "exit_time", "exit_price",
              "qty", "cost", "pnl", "pnl_pct", "reason"]


def fmt_t(ms):
    return datetime.fromtimestamp(ms / 1000, IST).strftime("%d %b %H:%M")


# ----------------------------------------------------------------- telegram --
def notify(text):
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=10)
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------- broker --
def account_equity_cost(acct):
    return acct["cash"] + sum(p["cost"] for p in acct["positions"].values())


def open_position(st, strat, sym, row):
    acct = st["accounts"][strat]
    price = row["close"] * (1 + SLIPPAGE)
    sl, tp = entry_levels(strat, price, row["atr"])
    if not (sl > 0 and price > sl):
        return
    equity = account_equity_cost(acct)
    qty = equity * RISK_PER_TRADE / (price - sl)
    notional = min(qty * price, equity / MAX_POSITIONS, acct["cash"] / (1 + FEE))
    if notional < MIN_NOTIONAL:
        return
    qty = notional / price
    fee = notional * FEE
    acct["cash"] -= notional + fee
    acct["positions"][sym] = {
        "entry_time": int(row["open_time"]) + INTERVAL_MIN * 60_000,
        "entry": price, "qty": qty, "cost": notional + fee,
        "sl": sl, "tp": tp, "bars": 0, "high_close": row["close"],
    }
    notify(f"🟢 [{strat}] BUY {sym} @ {price:.6g}  size ${notional:.2f}  SL {sl:.6g}"
           + (f"  TP {tp:.6g}" if tp else ""))


def close_position(st, strat, sym, price, ts, reason):
    acct = st["accounts"][strat]
    p = acct["positions"].pop(sym)
    gross = p["qty"] * price
    proceeds = gross - gross * FEE
    acct["cash"] += proceeds
    pnl = proceeds - p["cost"]
    append_csv(TRADES_FILE, {
        "strategy": strat, "symbol": sym,
        "entry_time": fmt_t(p["entry_time"]), "entry_price": round(p["entry"], 8),
        "exit_time": fmt_t(ts), "exit_price": round(price, 8), "qty": round(p["qty"], 8),
        "cost": round(p["cost"], 4), "pnl": round(pnl, 4),
        "pnl_pct": round(100 * pnl / p["cost"], 3), "reason": reason,
    }, TRADE_COLS)
    notify(f"{'✅' if pnl > 0 else '🔴'} [{strat}] SELL {sym} @ {price:.6g}  {reason}  "
           f"P&L ${pnl:+.3f} ({100 * pnl / p['cost']:+.2f}%)")


def manage_position(st, strat, sym, row):
    """Check one candle against an open position. Returns True if it closed."""
    p = st["accounts"][strat]["positions"][sym]
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    close_ts = int(row["open_time"]) + INTERVAL_MIN * 60_000
    # Stop is checked BEFORE target: if one candle touched both, assume the worst.
    if o <= p["sl"]:
        close_position(st, strat, sym, o * (1 - SLIPPAGE), close_ts, "stop (gap)")
        return True
    if l <= p["sl"]:
        reason = "trailing stop" if p["sl"] > p["entry"] else "stop-loss"
        close_position(st, strat, sym, p["sl"] * (1 - SLIPPAGE), close_ts, reason)
        return True
    if p["tp"] and o >= p["tp"]:
        close_position(st, strat, sym, o, close_ts, "take-profit (gap)")
        return True
    if p["tp"] and h >= p["tp"]:
        close_position(st, strat, sym, p["tp"], close_ts, "take-profit")
        return True
    # close-based rules (decided on this candle's close)
    p["bars"] += 1
    if strat == "trend" and row["trend_exit"]:
        close_position(st, strat, sym, c * (1 - SLIPPAGE), close_ts, "EMA cross-down")
        return True
    if strat == "meanrev" and p["bars"] >= 24:
        close_position(st, strat, sym, c * (1 - SLIPPAGE), close_ts, "time stop 6h")
        return True
    if strat == "breakout":
        p["high_close"] = max(p["high_close"], c)
        p["sl"] = max(p["sl"], p["high_close"] - 2 * row["atr"])  # only ever moves up
    return False


# --------------------------------------------------------------------- main --
def process_symbol(st, sym, df):
    df = add_indicators(df)
    last = st["last_ts"].get(sym)
    if last is None:  # first sighting: start the clock from the latest closed candle
        st["last_ts"][sym] = int(df["open_time"].iloc[-1])
        st["start_price"][sym] = float(df["close"].iloc[-1])
        st["last_price"][sym] = float(df["close"].iloc[-1])
        return
    new = df[(df["open_time"] > last) & (df["open_time"] < st["ends_at"])]
    if len(new) and new["open_time"].iloc[0] - last > INTERVAL_MIN * 60_000:
        st["errors"].append(f"{fmt_t(now_ms())} {sym}: gap in data, some candles skipped")
    for _, row in new.iterrows():
        for strat in STRATEGIES:
            pos = st["accounts"][strat]["positions"]
            just_closed = manage_position(st, strat, sym, row) if sym in pos else False
            if sym not in pos and not just_closed and row[f"{strat}_entry"]:
                open_position(st, strat, sym, row)
        st["last_ts"][sym] = int(row["open_time"])
        st["last_price"][sym] = float(row["close"])


def finish(st):
    for strat, acct in st["accounts"].items():
        for sym in list(acct["positions"]):
            close_position(st, strat, sym, st["last_price"][sym] * (1 - SLIPPAGE),
                           st["ends_at"], "trial ended")
    st["finished"] = True
    lines = ["🏁 48h paper trial finished"] + [
        f"{s}: ${a['cash']:.2f} ({100 * (a['cash'] / st['capital'] - 1):+.2f}%)"
        for s, a in st["accounts"].items()]
    lines.append(f"buy & hold: ${buy_hold_value(st):.2f}")
    notify("\n".join(lines))


def buy_hold_value(st):
    syms = [s for s in st["start_price"] if s in st["last_price"]]
    if not syms:
        return st["capital"]
    each = st["capital"] / len(syms) * (1 - FEE)
    return sum(each / st["start_price"][s] * st["last_price"][s] for s in syms)


def mark_to_market(st, acct):
    return acct["cash"] + sum(p["qty"] * st["last_price"].get(s, p["entry"])
                              for s, p in acct["positions"].items())


def run():
    st = load_state()
    if st["finished"]:
        print("Trial already finished. Delete state.json to start a new one.")
        write_report(st)
        return
    st["runs"] += 1
    for sym in SYMBOLS:
        try:
            src, df = fetch_candles(sym, st["source"])
            st["source"] = st["source"] or src
            process_symbol(st, sym, df)
        except Exception as e:  # noqa: BLE001
            st["errors"].append(f"{fmt_t(now_ms())} {sym}: {e}")
            print(f"[warn] {sym}: {e}", file=sys.stderr)
    st["errors"] = st["errors"][-20:]

    caught_up = all(st["last_ts"].get(s, 0) + INTERVAL_MIN * 60_000 >= st["ends_at"] for s in st["last_ts"])
    done = now_ms() >= st["ends_at"] and (caught_up or now_ms() >= st["ends_at"] + 2 * 3600_000)
    if done:
        finish(st)

    row = {"time": fmt_t(now_ms()), "ts": now_ms()}
    for s, a in st["accounts"].items():
        row[s] = round(mark_to_market(st, a), 4)
    row["buy_hold"] = round(buy_hold_value(st), 4)
    append_csv(EQUITY_FILE, row, ["time", "ts", *STRATEGIES, "buy_hold"])
    save_state(st)
    write_report(st)
    print(json.dumps({k: row[k] for k in [*STRATEGIES, "buy_hold"]}))


# ------------------------------------------------------------------- report --
def write_report(st):
    trades = pd.read_csv(TRADES_FILE) if os.path.exists(TRADES_FILE) else pd.DataFrame(columns=TRADE_COLS)
    eq = pd.read_csv(EQUITY_FILE) if os.path.exists(EQUITY_FILE) else pd.DataFrame()
    cap = st["capital"]
    left = max(0, st["ends_at"] - now_ms()) / 3600_000
    status = "🏁 FINISHED" if st["finished"] else f"🟢 RUNNING - {left:.1f}h left"

    out = [f"# Crypto paper-trading trial ({status})", "",
           f"Fake money, real {st['source'] or '?'} prices. Started **{fmt_t(st['started_at'])} IST**, "
           f"ends **{fmt_t(st['ends_at'])} IST**. Each strategy started with **${cap:.0f}**. "
           f"Coins: {', '.join(SYMBOLS)} on {INTERVAL_MIN}m candles. Fees {FEE*100:.1f}%/side + "
           f"{SLIPPAGE*100:.2f}% slippage included. Last update {fmt_t(now_ms())} IST (run #{st['runs']}).", "",
           "| Account | Equity | P&L | Return | Trades | Win rate | Open |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for s, a in st["accounts"].items():
        e = mark_to_market(st, a)
        t = trades[trades["strategy"] == s]
        wr = f"{100 * (t['pnl'] > 0).mean():.0f}%" if len(t) else "-"
        out.append(f"| **{s}** | ${e:.2f} | ${e - cap:+.2f} | {100 * (e / cap - 1):+.2f}% | "
                   f"{len(t)} | {wr} | {len(a['positions'])} |")
    bh = buy_hold_value(st)
    out.append(f"| *buy & hold (benchmark)* | ${bh:.2f} | ${bh - cap:+.2f} | {100 * (bh / cap - 1):+.2f}% | - | - | - |")
    out += ["", "![equity](equity.png)", "", "## Strategies", ""]
    out += [f"- **{k}**: {v}" for k, v in STRATEGIES.items()]

    out += ["", "## Open positions", ""]
    opens = [(s, sym, p) for s, a in st["accounts"].items() for sym, p in a["positions"].items()]
    if opens:
        out += ["| Strategy | Coin | Entry | Now | Stop | Target | Unrealized |", "|---|---|---:|---:|---:|---:|---:|"]
        for s, sym, p in opens:
            nowp = st["last_price"].get(sym, p["entry"])
            u = p["qty"] * nowp - p["cost"]
            out.append(f"| {s} | {sym} | {p['entry']:.6g} | {nowp:.6g} | {p['sl']:.6g} | "
                       f"{format(p['tp'], '.6g') if p['tp'] else 'trailing'} | ${u:+.3f} |")
    else:
        out.append("None.")

    out += ["", "## Last 25 closed trades", ""]
    if len(trades):
        out += ["| Strategy | Coin | In | Out | Entry | Exit | P&L | Why |", "|---|---|---|---|---:|---:|---:|---|"]
        for _, t in trades.tail(25).iloc[::-1].iterrows():
            out.append(f"| {t['strategy']} | {t['symbol']} | {t['entry_time']} | {t['exit_time']} | "
                       f"{t['entry_price']:.6g} | {t['exit_price']:.6g} | ${t['pnl']:+.3f} ({t['pnl_pct']:+.2f}%) | {t['reason']} |")
    else:
        out.append("No closed trades yet.")
    if st["errors"]:
        out += ["", "<details><summary>Recent warnings</summary>", "", *[f"- {e}" for e in st["errors"][-8:]], "", "</details>"]
    out += ["", "_Two days is a tiny sample: treat this as a smoke test, not proof a strategy works._"]
    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(out) + "\n")

    if len(eq) > 1 and not os.getenv("BOT_NO_CHART"):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            x = pd.to_datetime(eq["ts"], unit="ms", utc=True).dt.tz_convert(IST)
            fig, ax = plt.subplots(figsize=(10, 4.5), dpi=110)
            for col in [*STRATEGIES, "buy_hold"]:
                ax.plot(x, eq[col], label=col, lw=1.8, ls="--" if col == "buy_hold" else "-")
            ax.axhline(cap, color="grey", lw=0.8)
            ax.set_ylabel("Equity ($)")
            ax.set_title("Paper equity - each account started at $%g" % cap)
            ax.legend(loc="upper left", frameon=False, ncol=4)
            ax.grid(alpha=0.25)
            fig.autofmt_xdate()
            fig.tight_layout()
            fig.savefig(CHART_FILE)
            plt.close(fig)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] chart: {e}", file=sys.stderr)


if __name__ == "__main__":
    run()
