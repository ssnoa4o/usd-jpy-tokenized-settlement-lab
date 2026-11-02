# Methodology (draft)

Status: Day 4 draft, 2026-11-02. The engine skeleton exists, but settlement logic is not implemented and no experiment has been run. This file is the single place for definitions, so code, tests, report and slides use the same words. If code and this file disagree, fix one and record the change.

This is an independent research prototype on synthetic data. No institution (BIS, BoJ, CLS, OSFI or any other) has reviewed, approved or endorsed it.

Tag: **(DV)** = design value (synthetic, not real-world). Numbers marked (DV) are choices for the design, not estimates of any real bank or market.

## 1. Purpose and scope

We compare three simplified settlement models on the same synthetic USD/JPY transactions. We measure principal exposure, liquidity demand, settlement time and behaviour under stress. We test hypotheses H1 to H4 (see `hypotheses.md`). Findings will apply only to this simplified model and its stated assumptions, not to real markets.

## 2. Model definitions

All models: banks hold separate USD and JPY balances. Every transaction has a USD payer and a JPY payer. FX rate is fixed at 150.00 (DV) in the base case; this is an illustration, not a market claim. What the models are not is listed in sec. 10.

| | A: Sequential | B: Prefunded Tokenized | C: Atomic PvP |
|---|---|---|---|
| Idea | Two legs processed independently with a time gap | Funds for both legs reserved first, then legs processed as tokenized (virtual) assets | Validate both legs, then commit both together |
| Funds check | At the moment each leg executes | At reservation, before any leg moves | At validation, for both legs |
| Reservation | None | Yes, made at arrival. Each leg's reservation is used when that leg completes; if the second leg fails, its reservation is released at that moment | None held across time; validate and commit in one step |
| Legs executed | USD leg at arrival, then JPY leg after the delay | Same order as A, after reservation | Both in one commit at arrival + delay. The delay is applied as processing time so that C is not given a speed advantage by assumption |
| Can one leg settle alone? | Yes (`partial`) | Yes, if an injected failure hits the second leg (`partial`) | No |
| Typical failure | Second leg short of funds or failed (`insufficient_funds`, `technical_failure`) | Reservation not possible (`insufficient_funds`); second-leg `technical_failure` | Validation fails (`insufficient_funds`) or `technical_failure` at commit; nothing moves |

Key distinction: **Prefunding and Atomic PvP are different concepts.** Prefunding is about securing funds in advance. Atomic PvP is about making two legs indivisible. A balance check alone does not make Model C atomic. Model C is implemented as: check both legs on a copy of the state, then apply both changes in one step. On any failure no leg is applied.

## 3. Transaction record and settlement states

Input record (as in the HANDOFF generator): `transaction_id`, `usd_amount`, `jpy_amount` (= usd_amount x fx_rate), `direction`, `fx_rate`. Additions confirmed for Day 5: `arrival_time` (simulation seconds), `usd_payer`/`jpy_payer` bank IDs, which replace `direction`, and `failure_draw` (sec. 7). Amounts, bank pairs, arrival and failure draws use separate random streams, so changing the number of banks does not change the amounts.

Result record per transaction: `transaction_id`, `model`, `status`, `failure_reason`, `usd_leg_done`, `jpy_leg_done`, `arrival_time`, `start_time`, `end_time`, `principal_exposure_usd`.

The engine's ledger stores money as integers in hundredths of a currency unit, so exact-boundary balance checks and "identical in every seed" verdicts are not affected by floating-point noise.

| State | Meaning |
|---|---|
| `settled` | Both legs completed |
| `partial` | Exactly one leg completed |
| `failed` | Neither leg completed |

Failure reasons: `insufficient_funds`, `technical_failure`, `timeout`. A `partial` or `failed` transaction always has one reason; a `settled` transaction has none. `timeout` is a reserved value and is not triggered in the main experiments, because no experiment varies a timeout.

## 4. Input variables (design values, synthetic)

Ranges follow HANDOFF 5.1.

| Variable | Range / levels (DV) | Base case (DV) | Note |
|---|---|---|---|
| FX Rate | 150.00 | 150.00 | Sensitivity optional |
| Transaction Size | USD 100,000 to 1,000,000, uniform | same | Continuous uniform; not real FX size distribution |
| Number of Banks | 2 to 10 | 2 | Per transaction, an ordered pair of two different banks (USD payer, JPY payer) is drawn uniformly at random |
| Initial Liquidity (per bank, per currency) | placeholder reference USD 100,000,000 and JPY 15,000,000,000; placeholder multipliers 100%, 75%, 50%, 25%, 10% | 100% | Replaced by the calibration in sec. 6 |
| Settlement Delay (gap between legs / processing time) | 0, 60, 300 seconds | 60 | Simulation time |
| Transaction Arrival | sequential (one transaction every 10 s), burst (10 transactions at the same time, every 100 s) | sequential | Same average arrival rate. The 10 s spacing makes transactions overlap at 60 s and 300 s delay |
| Failure Probability (second-leg / technical) | 0%, 1%, 5% | 1% | Sec. 7 |
| Transaction Volume | 100 to 1,000 | 500 | |
| Random Seed | 1 to 30 | per run | Sec. 6, 8 |

## 5. Metric definitions

N = number of transactions in a run. n_settled, n_partial, n_failed count the states. If N = 0, counts are 0. Any ratio with a zero denominator is NaN (empty in CSV), never 0, so that "no data" is not shown as "0% success". This differs from the HANDOFF sketch, which returns 0.

| Metric | Numerator / definition | Denominator | Notes |
|---|---|---|---|
| Success Rate | n_settled | N | `partial` NOT included |
| Partial Settlement Rate | n_partial | N | |
| Failure Rate | n_failed (also counted by reason) | N | |
| Principal Exposure (USD), amount-based, **required** | Sum of `usd_amount` over `partial` transactions (the JPY leg is `jpy_amount` / fx_rate, the same value) | none (amount) | No partial gives 0. Ignores delay |
| Principal Exposure, duration-weighted (USD-seconds), **required** | Sum over transactions whose first leg completed of `usd_amount` x window length. Window: from completion of the first leg to completion of the second leg; for a `partial`, to first-leg completion + W, with W = 3,600 s cut-off (DV). W only closes the window; no loss is booked and no balance changes. The models have no repair step, so every `partial` is unrepaired | none | Model C has no window (one commit): 0. Delay enters only through `settled` transactions; a `partial` contributes W regardless of delay, so W can dominate the total. Descriptive only, always reported with W stated |
| Gross Prefunding (B, C) | Per transaction `usd_amount` + `jpy_amount` / `fx_rate` (both legs, USD-equivalent). B: amount reserved at reservation. C: amount that must be available at the single validate-and-commit step and passes validation. Summed over the run; counted even if the transaction later fails | none | Not applicable (not 0) for A. Not Peak Liquidity. B holds it over time; C needs it at one instant, so the B and C sums are close by construction |
| Peak Liquidity Proxy (all models) | For each bank and currency, max over time of (initial balance - available balance), where available balance = balance - reserved funds. Summed over banks and currencies in USD (JPY at the fx rate) | none | **Proxy**: no netting, no credit lines, receipts within the run can be reused. Partly definitional (reserved funds count as unavailable). The ledger updates the maximum on every debit and reservation, so no balance time series is stored. At ample liquidity and constant delay, every USD payment in C happens the same delay later than in A and JPY payments are at the same times, so payment order within each currency is unchanged. Their proxies can then differ only through transactions hit by an injected failure. Labelled "proxy" everywhere |
| Liquidity Utilization (B, C) | USD-equivalent value of legs that actually completed | Gross Prefunding | Not applicable for A. Close to a success ratio, so descriptive only |
| Average Settlement Time | Mean of (`end_time` - `arrival_time`) over **`settled` transactions only** | n_settled | Failures and partials are excluded; their count is reported beside it. Answers "how long does a successful settlement take"; without this rule, models that fail early would look fast. Every `settled` transaction takes exactly the delay in all three models, so this metric is equal across models by construction and is not evidence |
| Operational Delay | Mean extra time caused by injected delay, in seconds, over all transactions that reached a leg or a commit attempt | those transactions | Separate from settlement finality. There is no waiting queue, so this equals the injected delay and is descriptive only |
| L\* (minimum liquidity level) | Per model and seed: the lowest multiplier on the Exp3 grid at which Success Rate >= **95% (DV)**, at that level and every higher level | none | If none qualifies: "not reached", ranked above all levels. A coarse grid makes ties likely |

## 6. Experiment design

**Common to all main runs.** Seeds 1 to 30 (DV, adjustable; if changed, change for all hypotheses and log it in `results/experiment_log.csv`). All three models get the same transactions within a seed. Unlisted settings keep the base case from sec. 4. Outputs in `results/`: `run_metrics.csv` (one row per run with every metric; the source for paired differences and per-seed L\*), `summary.csv` (per-condition mean, min, max across seeds), `experiment_log.csv` (one row per run: experiment, model, seed, all parameters, code version), figures in `results/figures/`. File names for separate per-experiment CSVs may be added; they must stay in `results/`.

| Exp | Varied (DV) | Fixed (DV) |
|---|---|---|
| 1 Baseline | none (3 models; plus 0% failure sanity run) | 500 transactions, 2 banks, ample liquidity, delay 60 s, failure 1% |
| 2 Volume Stress | One factor at a time, others at baseline: Volume {100, 500, 1000}; Banks {2, 5, 10}; Arrival {sequential, burst}. Used with Exp3's liquidity grid for H3 | ample liquidity (H3: grid), delay 60 s, failure 1% |
| 3 Liquidity Stress | Liquidity multiplier grid. Combined with each Exp2 factor level (one at a time) to get L\* for H3 | 500 transactions, 2 banks, delay 60 s, failure 1% |
| 4 Delay / Failure Stress | One at a time: Failure {0, 1, 5}% at delay 60 s; Delay {0, 60, 300} s at failure 1%. H4b cells: delay {0, 60, 300} s at failure 1% and a grid level where shortages occur (placeholder 50%) | 500 transactions, 2 banks, ample liquidity (except H4b cells) |

The 0% failure run is a sensitivity check (no `partial`, no failure expected at ample liquidity). `timeout` is not triggered (sec. 3), so it cannot produce states in this run.

**Liquidity calibration (before the main runs, once the engine exists).** The placeholder reference and multipliers may leave too few levels with any shortage, which would make H1b and H4b untestable. So the levels are set by a separate calibration, fixed before any main run:
- Seeds 101 to 110 (DV), separate from the main seeds. Models A, B and C, failure 0%. Only `insufficient_funds` counts are read; no metric used in a decision is inspected.
- The reference starts at the placeholder in sec. 4 and doubles until it is ample, at most 5 times (DV). "Ample" = the reference level at which there is no `insufficient_funds` in any model and calibration seed, in every condition that Exp1, 2 and 4 run at ample liquidity (this includes the largest volume, 10 banks, burst arrival and the 300 s delay).
- The grid has 5 levels (DV): the reference plus 4 lower levels, starting at multipliers 75%, 50%, 25%, 10%. Under Exp3's fixed settings, at least 2 lower levels (DV) must have a `partial` with reason `insufficient_funds` in Model A in every calibration seed (the condition H1b needs). If not, all 4 lower multipliers are halved and the check is repeated, at most 3 times (DV). The grid is then fixed and not refined. If a limit is reached without meeting its condition, no main run starts: the failed condition is recorded in `results/experiment_log.csv` and `findings.md`, and H1b and H4b are reported as untestable unless the design is revised and recorded before any main run.
- The H4b level is the highest grid level at which Model A has a `partial` with reason `insufficient_funds` in at least half of the calibration seeds (DV), at each of the delays 0, 60 and 300 s. If no level qualifies, H4b is recorded as untestable before any main run.
- The chosen values are saved in `results/calibration.csv`.
- If "ample" does not hold in a main run (for example in B, which reserves both legs first), the design is not silently changed: raise the reference, repeat the calibration and rerun the main runs, before any verdict is computed. The change and its reason are recorded in `results/experiment_log.csv` and `findings.md`.

## 7. Failure injection and required tests

For each transaction one uniform draw `failure_draw` in [0, 1) is taken once from the seed and reused by all three models and at all failure levels. A hit means the draw is below the Failure Probability, so hits at a lower probability are also hits at a higher one (nested levels). In A and B a hit means the second leg fails (`technical_failure`), leaving `partial`. In C it means the commit fails (`technical_failure`), leaving `failed`. This keeps the injected events identical across models.

**Processing rules.**
- Events run in the order (time, event type, `transaction_id`). At the same time, second legs and commits run before new arrivals.
- There is no waiting queue and no retry. A transaction short of funds immediately becomes `failed`, or `partial` if its first leg has completed.
- A: first leg short of funds gives `failed`. At the second leg the failure draw is checked first, then funds, so a transaction hit by both is recorded as `technical_failure`.
- B: a reservation that is not possible at arrival gives `failed`. A failure-draw hit at the second leg gives `partial` with `technical_failure`.
- C: funds are validated first, then the failure draw is checked. Either failure leaves every balance unchanged.

**Required tests** (in `tests/`; guaranteed by design, so correctness checks and not evidence):
- In every seed and condition: C partial count = 0 and C Principal Exposure = 0.
- After a failed C transaction, every balance equals its value before the attempt.
- When no `insufficient_funds` occurs in A or B, they have identical amount-based Principal Exposure.
- In A and B, at ample liquidity with no `insufficient_funds`, Principal Exposure does not fall as Failure Probability rises (with nested draws), and with 500 transactions (DV) it is higher at 5% than at 0%. Otherwise there is a bug. Under liquidity stress this need not hold, because a hit changes later balances.
- `settled` iff both legs done; `partial` iff exactly one; `failed` iff none.
- Success + Partial + Failure rates sum to 1 (N > 0).
- Total USD and total JPY across banks are unchanged by any run.

## 8. Reproducibility

- Seeds are arguments, never hidden. Data and failure draws derive deterministically from the run seed.
- Every parameter is saved with its results (`experiment_log.csv`), plus the git commit hash and run date.
- `python -m src.experiments` regenerates all CSVs and figures.
- **`results/*.csv` is the only source of numbers** in findings, report, brief and slides. Illustrative numbers must be labelled Illustrative / Synthetic and never used as results. The dashboard calls the real engine.

## 9. Threats to validity

- Synthetic parameters: uniform sizes, random direction, fixed rate. Results do not describe real flows.
- No netting, credit, or fund reuse beyond in-run receipts, so liquidity needs are likely to differ from real arrangements (proxy only).
- Model choices drive outcomes: some H1 results follow from definitions. Required tests keep these separate from evidence.
- Failure probability is a single independent draw; real failures are correlated.
- The decision rules in `hypotheses.md` (paired rule for model comparisons, range rule for H3) depend on the number of seeds and are not statistical tests.
- Grid choices (liquidity levels, target 95%) can change L\*. The calibration reduces but does not remove this.
- W drives the size of duration-weighted exposure, so that metric is not a delay effect. It is descriptive only.
- Amount-based Principal Exposure ignores delay directly, so delay can change it only through balances (second-leg shortages). H4b may therefore show little or no difference.
- Liquidity is set per bank, so adding banks raises total liquidity and spreads flows. The bank-count effect on L\* is not a pure effect of participant numbers.
- Average Settlement Time and Operational Delay follow from the injected delay, so they do not compare the models' operational performance. That comparison rests on success, partial and failure rates under stress.

## 10. Exclusions / out of scope

What the models are NOT:
- Not CLS. No CLS algorithm, no multilateral netting, no CLS pay-in schedule (CLS is a real PvP service; see CLS-3 for its own description).
- Not a real large-value payment system and no real central bank money.
- Not BIS Project Agorá, and not a reproduction of any tested scenario (BIS-1, BIS-3).
- Not real tokenized deposits. No legal structure, no smart contracts, no settlement finality in the legal sense.
- Model A is an abstraction ("time-gapped independent legs"), not a correspondent banking model.
- The link between our models and real-world arrangements (A like non-PvP, B like prefunding, C like PvP) is our interpretation only; no source states it (see `literature_review.md` sec. 4).

Also excluded: netting of any kind; credit lines and intraday credit; replacement cost and market price risk; real liquidity levels and real failure rates; other currency pairs; Ethereum, Solidity, wallets, bank APIs, real funds; any link to the author's other projects. Ideas that arise go to "Future research" in `literature_review.md`.

## 11. Decisions and open questions

Decided on Day 4, before any experiment (all values DV):
1. Ratios with a zero denominator are NaN, not 0 (sec. 5).
2. `timeout` is a reserved reason and is not triggered in the main experiments (sec. 3).
3. Sequential arrival is one transaction every 10 s; burst is 10 transactions every 100 s (sec. 4). `arrival_time` is added to the generator on Day 5.
4. Model B reservations are used at leg completion and released at failure. Model C validates and commits once, at arrival + delay (sec. 2).
5. W = 3,600 s cut-off, used for every `partial` (sec. 5). Duration-weighted exposure is descriptive only.
6. The Peak Liquidity Proxy is implementable as a running maximum in the ledger (sec. 5).
7. With more than 2 banks, the two banks are drawn uniformly at random per transaction (sec. 4).
8. H2's primary comparison is the B minus A proxy gap at 300 s vs 0 s delay; C vs A becomes exploratory. H4b's primary metric is amount-based Principal Exposure. Both changed after the Day 4 review, before any experiment (`hypotheses.md`).

Still to do after the engine exists (Day 6 to 7): run the liquidity calibration (sec. 6) under the rules fixed there.
