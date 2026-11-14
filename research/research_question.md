# Research Question

Status: Day 4 update (2026-11-02). Hypotheses are things to test, not conclusions. Decision rules (supported / not supported / inconclusive) are fixed in `hypotheses.md` before any experiment.

## Central question

How do tokenized settlement mechanisms affect liquidity requirements, principal settlement risk, and operational performance in USD/JPY foreign exchange transactions?

## What we do

We build a simplified simulator. It runs the same synthetic USD/JPY transactions through three settlement models and compares them.

- Model A: Sequential. The USD leg and the JPY leg are processed separately, with a time gap.
- Model B: Prefunded Tokenized. Each currency is reserved before settlement, then the model processes tokenized assets.
- Model C: Atomic PvP. Both legs are checked, then committed together: both settle or neither settles.

Prefunding and atomic PvP are different ideas. Prefunding is about securing funds in advance. Atomic PvP is about making two legs indivisible. A balance check alone does not make a settlement atomic.

Settlement states: a transaction is `settled` (both legs completed), `partial` (only one leg completed), or `failed` (neither leg completed). Success rate counts only `settled`; `partial` is not included.

Metrics (defined in the methodology): principal exposure, success rate, partial settlement rate, failure rate, gross prefunding, peak liquidity (a proxy in the MVP), average settlement time, liquidity utilization, operational delay. In this model average settlement time and operational delay follow directly from the injected delay, so operational performance is compared mainly through success, partial and failure rates under stress.

## Hypotheses to be tested (not conclusions)

- H1 (to be tested): Model C commits both legs or neither, so its partial count and principal exposure are zero by design (a correctness test, not evidence). The open questions are how principal exposure in Models A and B responds to injected second-leg failures, and under which conditions B differs from A.
- H2 (to be tested): Does the gap in the peak-liquidity proxy between Models B and A change with settlement delay? Separately, as descriptive questions: how does gross prefunding compare between Models B and C (it is not applicable to Model A), and how do these measures change as initial liquidity changes? Part of the answer follows from the metric definitions, and C versus A is expected to be close to equal at ample liquidity.
- H3 (to be tested): Do transaction volume, number of banks, and arrival pattern change the lowest initial-liquidity level at which the success rate reaches a stated target?
- H4 (to be tested): Do liquidity stress and delay change success rate and amount-based principal exposure differently across the models?

These statements are open questions. No experiment had been run when this section was written (Day 4). Each will be recorded as supported, not supported, or inconclusive, using only numbers from `results/*.csv`.

Update, 2026-11-14: the experiments have since been run. The hypotheses were refined into H1a, H1b, H2, H3, H4a and H4b with fixed decision rules in `research/hypotheses.md` before the main runs. The recorded verdicts are in `research/findings.md`, `results/verdicts.csv` and `results/h3_verdicts.csv`. The text above is kept as written on Day 4.

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
