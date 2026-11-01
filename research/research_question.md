# Research Question

Status: Day 2 draft (2026-11-01). Hypotheses are listed for testing only. They will be finalized on Day 3 (see `hypotheses.md`, not yet written).

## Central question

How do tokenized settlement mechanisms affect liquidity requirements, principal settlement risk, and operational performance in USD/JPY foreign exchange transactions?

## What we do

We build a simplified simulator. It runs the same synthetic USD/JPY transactions through three settlement models and compares them.

- Model A: Sequential. The USD leg and the JPY leg are processed separately, with a time gap.
- Model B: Prefunded Tokenized. Each currency is reserved before settlement, then the model processes tokenized assets.
- Model C: Atomic PvP. Both legs are checked, then committed together: both settle or neither settles.

Prefunding and atomic PvP are different ideas. Prefunding is about securing funds in advance. Atomic PvP is about making two legs indivisible. A balance check alone does not make a settlement atomic.

Settlement states: a transaction is `settled` (both legs completed), `partial` (only one leg completed), or `failed` (neither leg completed). Success rate counts only `settled`; `partial` is not included.

Metrics (defined in the methodology): principal exposure, success rate, partial settlement rate, failure rate, gross prefunding, peak liquidity (a proxy in the MVP), average settlement time, liquidity utilization, operational delay.

## Hypotheses to be tested (not conclusions)

- H1 (to be tested): When the same synthetic transactions and the same injected second-leg failures are run through all three models, do principal exposure and partial-settlement counts differ between Model C and Models A and B, and by how much?
- H2 (to be tested): How much gross prefunding and peak-liquidity proxy do Models B and C need compared with Model A, and how does this change as initial liquidity changes?
- H3: Changes in transaction count, number of banks, and arrival pattern change the relation between funding demand and success rate.
- H4: Stress conditions (liquidity shortage, delay) affect the three models differently.

These statements are open questions. No experiment has been run. Each will be recorded as supported, not supported, or inconclusive, using only numbers from `results/*.csv`.

## Out of scope

- Connecting to Ethereum, Solidity, wallets, bank APIs, or real funds.
- Reproducing CLS algorithms, legal settlement finality, real RTGS behaviour (for example BOJ-NET), or BIS Project Agorá.
- Real bank liquidity levels or real failure probabilities. All parameters are synthetic.
- Claims about real markets. Findings apply only to the simplified model and its stated assumptions.
- Currency pairs other than USD/JPY, legal analysis, and netting or credit lines in the MVP.
- Any link to the author's other projects (SimpleDigitalYen / JPYT).

Interesting items outside scope go to "Future research" and are not added to the project.

## Positioning

This is an independent research prototype using synthetic data. It is not affiliated with, reviewed by, approved by, or endorsed by the BIS, the Bank of Japan, the Bank of Canada, CLS, OSFI, or any other institution. Their public documents are cited only as background, and we describe what each source says separately from what our model does and from our own interpretation.
