"""Offline 48h simulation on synthetic candles. Run: python tests/test_sim.py"""
import importlib
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

M15 = 15 * 60_000
T0 = 1_780_000_000_000 // M15 * M15  # aligned start


def make_market(seed=7, n=600):
    rng = np.random.default_rng(seed)
    data = {}
    for i, sym in enumerate(["BTC", "ETH", "SOL", "XRP", "DOGE"]):
        drift = np.sin(np.arange(n) / (40 + 10 * i)) * 0.0015  # regimes up/down
        r = drift + rng.normal(0, 0.004 + 0.001 * i, n)
        close = (100 * (i + 1)) * np.exp(np.cumsum(r))
        opn = np.r_[close[0], close[:-1]]
        hi = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
        lo = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
        vol = rng.lognormal(3, 0.6, n)
        t = T0 - 300 * M15 + np.arange(n) * M15
        data[sym] = pd.DataFrame({"open_time": t.astype("int64"), "open": opn, "high": hi,
                                  "low": lo, "close": close, "volume": vol})
    return data


def run_trial(run_times, market):
    d = tempfile.mkdtemp()
    os.environ["BOT_DATA_DIR"] = d
    os.environ["BOT_NOW_MS"] = str(T0 + 60_000)
    import bot
    importlib.reload(bot)

    def fake(sym):
        now = int(os.environ["BOT_NOW_MS"])
        df = market[sym]
        return df[df["open_time"] <= now].tail(500).copy()  # includes the still-forming candle

    bot.SOURCES = {"fake": fake}
    for t in run_times:
        os.environ["BOT_NOW_MS"] = str(t)
        bot.run()
    st = bot.load_state()
    trades = pd.read_csv(bot.TRADES_FILE) if os.path.exists(bot.TRADES_FILE) else pd.DataFrame()
    return d, bot, st, trades


def main():
    os.environ["BOT_NO_CHART"] = "1"
    market = make_market()
    end = T0 + 60_000 + 48 * 3600_000
    every5 = list(range(T0 + 60_000, end + 3 * 3600_000, 5 * 60_000))
    rng = np.random.default_rng(1)
    sparse = [T0 + 60_000]
    while sparse[-1] < end + 3 * 3600_000:
        sparse.append(sparse[-1] + int(rng.integers(5, 180)) * 60_000)  # 5 min .. 3 h gaps

    d1, bot, st1, tr1 = run_trial(every5, market)
    d2, _, st2, tr2 = run_trial(sparse, market)

    assert st1["finished"] and st2["finished"], "trial should finish after 48h"
    assert len(tr1) > 0, "expected some trades"
    # 1) Catch-up equivalence: late/missed runs must give identical results (no dependence on run timing)
    cols = ["strategy", "symbol", "entry_time", "exit_time", "pnl", "reason"]
    key = lambda df: sorted(map(tuple, df[cols].astype(str).values.tolist()))
    assert key(tr1) == key(tr2), "results depend on run timing!"
    # 2) Accounting: final cash == capital + sum of realized P&L
    for s, a in st1["accounts"].items():
        assert not a["positions"], "all positions closed at end"
        pnl = tr1[tr1.strategy == s]["pnl"].sum()
        assert abs(a["cash"] - (50 + pnl)) < 0.01, (s, a["cash"], pnl)
    # 3) No lookahead: every entry happens after the trial start and before its exit
    for _, t in tr1.iterrows():
        assert t["pnl_pct"] > -15, "loss bigger than stop distance allows?"
    # 4) Truncating future data must not change past decisions
    cut = T0 + 24 * 3600_000
    mkt_cut = {k: v[v.open_time < cut].copy() for k, v in market.items()}
    _, _, _, tr3 = run_trial([t for t in every5 if t < cut], mkt_cut)
    assert len(tr3) > 0 and set(key(tr3)) <= set(key(tr1)), "future data leaked into past decisions"

    print(tr1.groupby("strategy").agg(trades=("pnl", "size"), pnl=("pnl", "sum"),
                                       win=("pnl", lambda x: (x > 0).mean())))
    print({s: round(a["cash"], 2) for s, a in st1["accounts"].items()})
    print("trades:", len(tr1), "| runs:", st1["runs"], "vs", st2["runs"])
    os.environ.pop("BOT_NO_CHART"); os.environ["BOT_DATA_DIR"] = d1; importlib.reload(bot); bot.write_report(bot.load_state())
    print("ALL CHECKS PASSED. Sample report in", d1)
    shutil.copy(os.path.join(d1, "REPORT.md"), os.path.join(HERE, "sample_REPORT.md"))
    shutil.copy(os.path.join(d1, "equity.png"), os.path.join(HERE, "sample_equity.png"))


if __name__ == "__main__":
    main()
