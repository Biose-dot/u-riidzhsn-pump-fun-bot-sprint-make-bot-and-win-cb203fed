"""Breakout Rider — a paper-trading bot for the pump.fun replay (agent-fun/replay/v2).

Strategy in one paragraph: most fresh pump.fun curves are bundled launches that
get dumped within minutes, so this bot never chases a creation. It watches every
curve's tape and only buys a *breakout*: the price just pushed above its own
60-slot window high on broad, accelerating buy flow (several distinct buyers,
buys dominating the tape, net SOL flowing in, inflow stronger in the second half
of the window). Size scales with the strength of the inflow. Every position is
managed actively: a partial take-profit at +35% (sell half, bank the win), a full
take-profit at +90%, a hard stop-loss at -12%, a trailing stop once the trade is
up 15% (exit on an 18% pullback from the peak), a fade exit when the tape turns
seller-dominated, and a 1200-slot time limit so capital keeps rotating. At most
two entries per curve and a cooldown after each exit, so the bot cannot churn
the same curve and let round-trip fees eat the edge.

Guardrail awareness: the competition needs a round trip of at least 0.01 SOL on
each of at least 20 distinct coins and a maximum drawdown of 50% or less. The
bot therefore sizes every first buy at 0.05 SOL (well above the 0.01 SOL floor),
caps open positions at 5, and rotates quickly through many coins instead of
parking in a few. Paper trading only: the replay uses market data, never real
funds.

Fully deterministic: no clock, no environment, no randomness, no network —
only the harness's own replay stream. Two runs on the same window produce
byte-identical action logs. Python 3.13 standard library only, plus the kit's
own shim vendored under vendor/ (kept out of the authorship counts, as the
kit's Python SDK instructs). The grader runs ``python3 -P -s /bot/main.py``
with ``PYTHONHASHSEED=0``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script directory off sys.path)

SOL = makefun_bot.LAMPORTS_PER_SOL

# --- tape window -----------------------------------------------------------
WINDOW = 60            # slots of tape examined for a breakout signal
KEEP = WINDOW + 10     # slots of tape kept per curve before pruning
MIN_TRADES = 8         # trades a curve needs before it can be bought
MIN_BUYERS = 3         # distinct buyers inside the window
MIN_NET_SOL = 0.3      # net SOL inflow (buys minus sells) over the window
MIN_BUY_SHARE = 0.60   # buys as a share of all tape SOL in the window
MIN_PRICE_UP = 0.02    # price must be up at least 2% across the window
MIN_RAISED_SOL = 5.0   # real SOL raised before a coin is considered
MIN_AGE = 60           # slots a curve must exist before entry

# --- sizing ----------------------------------------------------------------
FIRST_BUY_SOL = 0.05   # base first buy (5x the 0.01 SOL round-trip floor)
STRONG_BUY_SOL = 0.08  # first buy when inflow is very strong
STRONG_NET_SOL = 2.0   # net inflow that counts as "very strong"
MAX_PER_COIN_SOL = 0.08
BUY_SLIPPAGE_BPS = 500
SELL_SLIPPAGE_BPS = 10_000

# --- exits -----------------------------------------------------------------
PARTIAL_TP = 0.35      # sell half the position at +35%
FULL_TP = 0.90         # sell the rest at +90%
STOP_LOSS = 0.12       # hard stop at -12% vs cost
TRAIL_ARM = 0.15       # trailing stop arms once up 15%
TRAIL_DROP = 0.18      # exit on an 18% pullback from the peak value
MAX_HOLD = 1200        # slots before a time-based exit
COOLDOWN = 150         # slots after an exit before re-entering the same curve
MAX_ENTRIES_PER_CURVE = 3
MAX_POSITIONS = 5

CURVE_FEE = 0.0125     # pump.fun curve fee (1.25%) charged on sells


class TapeTrade:
    """One trade on a curve's tape, reduced to what the signal needs."""

    __slots__ = ("slot", "buy", "sol", "user", "price")

    def __init__(self, slot, buy, sol, user, price):
        self.slot = slot
        self.buy = buy
        self.sol = sol
        self.user = user
        self.price = price


class Tape:
    """Per-curve tape: creation slot, recent trades, exit bookkeeping."""

    __slots__ = ("created", "trades", "last_exit", "entries")

    def __init__(self):
        self.created = None
        self.trades = []
        self.last_exit = -10**12
        self.entries = 0


class Held:
    """A live position plus the state its exit rules need."""

    __slots__ = ("opened", "peak", "cost_sol", "partial_done", "exiting", "filled")

    def __init__(self, opened, cost_sol):
        self.opened = opened
        self.peak = 0.0
        self.cost_sol = cost_sol
        self.partial_done = False
        self.exiting = False
        self.filled = False


# Insertion-ordered dicts only (deterministic iteration under PYTHONHASHSEED=0).
tapes = {}
held = {}


def tape_of(mint):
    t = tapes.get(mint)
    if t is None:
        t = Tape()
        tapes[mint] = t
    return t


def price_of(vq, vt):
    """SOL per token from virtual reserves (ints); 0 when there is no supply."""
    if vt <= 0:
        return 0.0
    return vq / vt


def sell_value_sol(tokens, vq, vt, tx_sol):
    """SOL received for selling `tokens` against these reserves, curve fee and tx fee off."""
    if vt + tokens <= 0:
        return 0.0
    return (tokens * vq) / (vt + tokens) / SOL * (1 - CURVE_FEE) - tx_sol


def window_stats(t, now):
    """Aggregate the tape over the last WINDOW slots.

    Returns (net_sol, buy_sol, sell_sol, buyers, start_price, high, last_price,
    net_first_half, net_second_half, trades_seen). Trades are stored in slot
    order, so the scan stops at the window edge.
    """
    from_slot = now - WINDOW
    mid = now - WINDOW // 2
    net = 0.0
    buy_sol = 0.0
    sell_sol = 0.0
    net_old = 0.0
    net_new = 0.0
    buyers = set()
    start_price = -1.0
    high = 0.0
    last_price = 0.0
    seen = 0
    for tr in t.trades:
        if tr.slot <= from_slot:
            start_price = tr.price
            continue
        seen += 1
        if start_price < 0:
            start_price = tr.price
        signed = tr.sol if tr.buy else -tr.sol
        if tr.slot <= mid:
            net_old += signed
        else:
            net_new += signed
        net += signed
        if tr.buy:
            buy_sol += tr.sol
            buyers.add(tr.user)
        else:
            sell_sol += tr.sol
        if tr.price > high:
            high = tr.price
        last_price = tr.price
    return (net, buy_sol, sell_sol, buyers, start_price, high, last_price,
            net_old, net_new, seen)


def net_flow(t, now, w):
    """Net SOL (buys minus sells) on the tape over the last `w` slots."""
    net = 0.0
    for i in range(len(t.trades) - 1, -1, -1):
        tr = t.trades[i]
        if tr.slot <= now - w:
            break
        net += tr.sol if tr.buy else -tr.sol
    return net


def breakout_signal(t, now, curve):
    """True when the curve just broke above its window high on broad buy flow.

    Every condition must hold: the curve is old enough, has enough trades, the
    tape shows real net inflow with buys dominating, several distinct buyers,
    the price up across the window and sitting at (not below) its window high,
    inflow accelerating into the second half, and the most recent trade a buy.
    A single whale buying alone cannot pass: the buyer-count and buy-share
    gates filter bundled launches and one-wallet pumps.
    """
    if t.created is None or now - t.created < MIN_AGE:
        return False
    if len(t.trades) < MIN_TRADES:
        return False
    if not t.trades or not t.trades[-1].buy:
        return False
    (net, buy_sol, sell_sol, buyers, start_price, high, last_price,
     net_old, net_new, seen) = window_stats(t, now)
    if seen < MIN_TRADES:
        return False
    if len(buyers) < MIN_BUYERS:
        return False
    if net < MIN_NET_SOL:
        return False
    total = buy_sol + sell_sol
    if total <= 0 or buy_sol / total < MIN_BUY_SHARE:
        return False
    if start_price <= 0 or last_price <= 0:
        return False
    if last_price / start_price - 1 < MIN_PRICE_UP:
        return False
    if high <= 0 or last_price < high:
        return False
    # Inflow must still be coming, not fading: the second half of the window
    # carries at least half the net inflow of the first.
    if net_new <= 0 or net_new < 0.5 * net_old:
        return False
    # No single buyer may dominate the tape (anti-bundle / anti-whale).
    top = 0.0
    by_user = {}
    for tr in t.trades:
        if tr.slot <= now - WINDOW or not tr.buy:
            continue
        by_user[tr.user] = by_user.get(tr.user, 0.0) + tr.sol
    for v in by_user.values():
        if v > top:
            top = v
    if buy_sol > 0 and top > 0.6 * buy_sol:
        return False
    # The curve must already have raised real SOL: a breakout on an empty
    # curve is noise, not demand.
    if curve is not None and curve.real_quote_reserves < MIN_RAISED_SOL * SOL:
        return False
    return True


def decide_exits(state, batch, orders, tx_sol):
    """Append sell orders for positions whose exit rules fired. Exits first,
    so freed slots and cash are visible to the entry pass in the same batch."""
    now = batch["slot"]
    cap = state.hello["caps"]["max_orders_per_batch"]
    pending_sell = set()
    for po in state.pending.values():
        if po.order["side"] == "sell":
            pending_sell.add(po.order["mint"])
    for mint, h in list(held.items()):
        if len(orders) >= cap:
            break
        pos = state.positions.get(mint)
        curve = state.curves.get(mint)
        if pos is None:
            if mint not in pending_sell:
                held.pop(mint, None)
                if h.filled:
                    tape_of(mint).last_exit = now
            continue
        h.filled = True
        if curve is None or curve.complete:
            continue
        vq = curve.virtual_quote_reserves
        vt = curve.virtual_token_reserves
        tokens = pos.token_amount
        cost = pos.cost_lamports / SOL
        value = sell_value_sol(tokens, vq, vt, tx_sol)
        if value > h.peak:
            h.peak = value
        t = tape_of(mint)
        # Partial take-profit: bank half at +35%, keep the rest running.
        if not h.partial_done and value >= cost * (1 + PARTIAL_TP):
            if mint not in pending_sell:
                h.partial_done = True
                orders.append({
                    "side": "sell", "mint": mint,
                    "token_amount": tokens // 2,
                    "max_slippage_bps": SELL_SLIPPAGE_BPS,
                })
                continue
        exit_now = h.exiting
        if not exit_now and value < cost * (1 - STOP_LOSS):
            exit_now = True
        if (not exit_now and h.peak >= cost * (1 + TRAIL_ARM)
                and value < h.peak * (1 - TRAIL_DROP)):
            exit_now = True
        if not exit_now and value >= cost * (1 + FULL_TP):
            exit_now = True
        if not exit_now and net_flow(t, now, WINDOW) < 0:
            exit_now = True
        if not exit_now and now - h.opened >= MAX_HOLD:
            exit_now = True
        if not exit_now:
            continue
        h.exiting = True
        if mint in pending_sell:
            continue
        orders.append({
            "side": "sell", "mint": mint,
            "token_amount": tokens,
            "max_slippage_bps": SELL_SLIPPAGE_BPS,
        })


def on_batch(state, batch):
    """One batch of replay: fold its events into the tapes, exit first, then
    buy fresh breakouts while slots, cash and the per-batch order cap allow."""
    now = batch["slot"]
    tx_sol = state.tx_fee_lamports() / SOL
    traded = []
    traded_seen = set()
    for e in batch["events"]:
        mint = e["mint"]
        if e["event"] == "CreateEvent":
            tape_of(mint).created = e["slot"]
        elif e["event"] == "TradeEvent":
            t = tape_of(mint)
            t.trades.append(TapeTrade(
                e["slot"], bool(e["is_buy"]),
                int(e["sol_amount"]) / SOL, e["user"],
                price_of(int(e["virtual_quote_reserves"]),
                         int(e["virtual_token_reserves"])),
            ))
        if mint not in traded_seen:
            traded_seen.add(mint)
            traded.append(mint)
    # Prune tapes that moved this batch so memory stays bounded.
    for mint in traded:
        t = tapes[mint]
        cut = 0
        while cut < len(t.trades) and t.trades[cut].slot <= now - KEEP:
            cut += 1
        if cut:
            del t.trades[:cut]

    orders = []
    decide_exits(state, batch, orders, tx_sol)

    cap = state.hello["caps"]["max_orders_per_batch"]
    pending_buy = set()
    for po in state.pending.values():
        if po.order["side"] == "buy":
            pending_buy.add(po.order["mint"])
    free = state.free_cash_lamports()
    open_slots = MAX_POSITIONS - state.committed_position_count()
    tx = state.tx_fee_lamports()

    for mint in traded:
        if len(orders) >= cap or open_slots <= 0:
            break
        if mint in pending_buy or mint in held:
            continue
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            continue
        t = tapes[mint]
        if now - t.last_exit < COOLDOWN:
            continue
        if t.entries >= MAX_ENTRIES_PER_CURVE:
            continue
        if not breakout_signal(t, now, curve):
            continue
        # Stronger inflow earns the larger first buy; either way the buy is
        # capped by the harness's per-mint size cap (1% of real reserves).
        net, _, _, _, _, _, _, _, _, _ = window_stats(t, now)
        size_sol = STRONG_BUY_SOL if net >= STRONG_NET_SOL else FIRST_BUY_SOL
        amount = int(size_sol * SOL)
        cap_buy = state.max_buy_lamports(mint)
        if amount > cap_buy:
            amount = cap_buy
        if amount < int(0.01 * SOL):
            continue
        if free < amount + tx:
            continue
        orders.append({
            "side": "buy", "mint": mint,
            "quote_lamports": amount,
            "max_slippage_bps": BUY_SLIPPAGE_BPS,
        })
        free -= amount + tx
        open_slots -= 1
        t.entries += 1
        held[mint] = Held(now, amount / SOL)
    return orders


def on_done(state, done):
    """Final account, diagnostics only — stdout carries replies, so stderr."""
    cash_sol = state.cash / SOL
    print(f"[breakout-rider] done after {state.seq} batches: "
          f"cash {cash_sol:.4f} SOL, open positions {len(state.positions)}, "
          f"curves seen {len(state.curves)}", file=sys.stderr)


if __name__ == "__main__":
    makefun_bot.run(on_batch, on_done=on_done)
