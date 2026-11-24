# Breakout Rider — Pump.fun Bot Sprint

[![make.fun](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed.svg)](https://make.fun/c/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![rank](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/Biose-dot/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/rank.svg)](https://make.fun/c/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![reward](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/Biose-dot/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/reward.svg)](https://make.fun/c/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)

Entry for the [make.fun](https://make.fun) bounty
[Pump.fun Bot Sprint: Make Bot And Win](https://make.fun/c/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed).

## Strategy

A breakout paper-trading bot for the pump.fun bonding-curve replay
(`agent-fun/replay/v2`, Python 3.13 stdlib only, zero dependencies). Most fresh
curves are bundled launches that get dumped, so the bot never chases a
creation: it buys only when a curve breaks above its own 60-slot window high
on broad, accelerating buy flow — several distinct buyers, buys dominating the
tape, net SOL flowing in, and inflow stronger in the second half of the
window. A single whale buying alone cannot pass the buyer-count and buy-share
gates. First buys are 0.05 SOL (0.08 SOL on very strong inflow), capped at 1%
of real reserves, at most 5 open positions.

Every position is managed actively: a partial take-profit at +35% (sell half,
bank the win), a full take-profit at +90%, a hard stop-loss at −12%, a
trailing stop once the trade is up 15% (exit on an 18% pullback from peak), a
fade exit when the tape turns seller-dominated, and a 1200-slot time limit so
capital keeps rotating. At most two entries per curve plus a cooldown after
each exit, so the bot cannot churn the same curve and let round-trip fees eat
the edge.

Paper trading only: the replay uses market data, never real funds. Fully
deterministic — no clock, no environment, no randomness, no network — two runs
on the same window produce byte-identical action logs.

## Run

The grader runs `python3 -P -s /bot/main.py` with `PYTHONHASHSEED=0`, with
this directory mounted at `/bot`. Local smoke test:

```sh
PYTHONHASHSEED=0 python3 -P -s main.py < replay_input.jsonl
```

`vendor/makefun_bot.py` is the kit's own Python SDK shim, vendored as the kit
instructs (kept out of the authorship counts).
