# Methodology (draft)

Status: Day 11 draft, 2026-11-10 (grid revised to lower JPY only; calibration attempt 2 met its conditions). The transaction generator, Models A, B and C, and every metric in sec. 5 except L\* (computed from the Exp3 runs) exist. No main experiment has been run. This file is the single place for definitions, so code, tests, report and slides use the same words. If code and this file disagree, fix one and record the change.

This is an independent research prototype on synthetic data. No institution (BIS, BoJ, CLS, OSFI or any other) has reviewed, approved or endorsed it.

Tag: **(DV)** = design value (synthetic, not real-world). Numbers marked (DV) are choices for the design, not estimates of any real bank or market.

## 1. Purpose and scope

We compare three simplified settlement models on the same synthetic USD/JPY transactions. We measure principal exposure, liquidity demand, settlement time and behaviour under stress. We test hypotheses H1 to H4 (see `hypotheses.md`). Findings will apply only to this simplified model and its stated assumptions, not to real markets.

## 2. Model definitions

All models: banks hold separate USD and JPY balances. Every transaction has a USD payer and a JPY payer. FX rate is fixed at 150.00 (DV) in the base case; this is an illustration, not a market claim. What the models are not is listed in sec. 10. In code and in result files, the `model` column uses the values `sequential` (A), `prefunded` (B) and `atomic` (C).

| | A: Sequential | B: Prefunded Tokenized | C: Atomic PvP |
|---|---|---|---|
| Idea | Two legs processed independently with a time gap | Funds for both legs reserved first, then legs processed as tokenized (virtual) assets | Validate both legs, then commit both together |
| Funds check | At the moment each leg executes | At reservation, before any leg moves | At validation, for both legs |
| Reservation | None | Yes, made at arrival. Each leg's reservation is used when that leg completes; if the second leg fails, its reservation is released at that moment | None held across time; validate and commit in one step |
| Legs executed | USD leg at arrival, then JPY leg after the delay | Same order as A, after reservation | Both in one commit at arrival + delay. The delay is applied as processing time so that C is not given a speed advantage by assumption |
| Can one leg settle alone? | Yes (`partial`) | Yes, if an injected failure hits the second leg (`partial`) | No |
| Typical failure | Second leg short of funds or failed (`insufficient_funds`, `technical_failure`) | Reservation not possible (`insufficient_funds`); second-leg `technical_failure` | Validation fails (`insufficient_funds`) or `technical_failure` at commit; nothing moves |

Key distinction: **Prefunding and Atomic PvP are different concepts.** Prefunding is about securing funds in advance. Atomic PvP is about making two legs indivisible. A balance check alone does not make Model C atomic. Model C is implemented as: check both legs on the current state without changing it, then apply both changes in one step. On any failure no leg is applied.

## 3. Transaction record and settlement states

Input record (`src/transactions.py`): `transaction_id`, `arrival_time` (simulation seconds), `usd_payer`, `jpy_payer` (bank names A to J), `usd_amount`, `jpy_amount` (= usd_amount x fx_rate, rounded to 2 decimals), `fx_rate`, `failure_draw` (sec. 7). Amounts, bank pairs and failure draws use separate random streams, so changing the number of banks does not change the amounts or failure draws. Arrival times are deterministic and use no random stream (sec. 4). Within a seed, a larger volume keeps the earlier rows unchanged.

Result record per transaction: `transaction_id`, `model`, `status`, `failure_reason`, `usd_leg_done`, `jpy_leg_done`, `arrival_time`, `start_time`, `end_time`, `principal_exposure_usd`. In all three models, `start_time` equals `arrival_time` (there is no queue). In Model A, `end_time` is `arrival_time` for a transaction that `failed` at its first leg, and the time of the second-leg attempt (arrival + delay) for `partial` and `settled`. Model B uses the same rule: `end_time` is `arrival_time` if the reservation fails, and arrival + delay otherwise. In Model C, `end_time` is arrival + delay for every outcome, because validation and commit happen once at that time.

The engine's ledger stores money as integers in hundredths of a currency unit, so exact-boundary balance checks and "identical in every seed" verdicts are not affected by floating-point noise.

Input rows are checked before any event runs, so a run never stops halfway: an unknown bank raises `KeyError`; the same bank as USD payer and JPY payer, a non-finite amount, time or failure draw, or an amount that is zero or negative after rounding to hundredths raises `ValueError`. The generated data never contains such rows.

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
| Initial Liquidity (per bank, per currency) | placeholder reference USD 100,000,000 and JPY 15,000,000,000; placeholder multipliers 100%, 75%, 50%, 25%, 10% | 100% | Replaced by the calibration in sec. 6. From Day 11 the grid lowers JPY only (JPY = reference JPY x multiplier; USD stays at the reference). Attempt 1 (both currencies scaled) did not meet its grid condition. Attempt 2 fixed the grid at JPY multipliers 1, 0.09375, 0.0625, 0.03125, 0.0125 and the H4b level at 0.09375 (`results/calibration.csv`, `findings.md` sec. 2) |
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
| Gross Prefunding (B, C) | Per transaction `usd_amount` + `jpy_amount` / `fx_rate` (both legs, USD-equivalent, each row's own rate). B: amount reserved at reservation, so `settled` and `partial` count and `failed` (reservation not possible) does not. C: amount that must be available at the single validate-and-commit step and passes validation, so `settled` and `failed` with `technical_failure` count and `failed` with `insufficient_funds` does not. Summed over the run; counted even if the transaction later fails | none | Not applicable for A: NaN (empty in CSV), not 0. NaN with no transactions. Not Peak Liquidity. B holds it over time; C needs it at one instant, so the B and C sums are close by construction |
| Peak Liquidity Proxy (all models) | For each bank and currency, max over time of (initial balance - available balance), where available balance = balance - reserved funds. Summed over every bank of the run (`n_banks`, including banks with no transaction) and both currencies, in USD (JPY at the run's single fx rate; more than one rate in the input is an error) | none | NaN with no transactions. **Proxy**: no netting, no credit lines, receipts within the run can be reused. Partly definitional (reserved funds count as unavailable). The ledger updates the maximum on every debit and reservation, so no balance time series is stored. At ample liquidity and constant delay, every USD payment in C happens the same delay later than in A and JPY payments are at the same times, so payment order within each currency is unchanged. Their proxies can then differ only through transactions hit by an injected failure. Labelled "proxy" everywhere |
| Liquidity Utilization (B, C) | USD-equivalent value of legs that actually completed (B `partial`: the USD leg only; C `failed`: nothing) | Gross Prefunding | Not applicable for A: NaN. A zero denominator gives NaN. Close to a success ratio, so descriptive only |
| Average Settlement Time | Mean of (`end_time` - `arrival_time`) over **`settled` transactions only** | n_settled | NaN if n_settled = 0. Failures and partials are excluded; their count is reported beside it. Answers "how long does a successful settlement take"; without this rule, models that fail early would look fast. Every `settled` transaction takes exactly the delay in all three models, so this metric is equal across models by construction and is not evidence |
| Operational Delay | Mean extra time caused by injected delay, in seconds, over all transactions that reached a leg or a commit attempt | those transactions | Separate from settlement finality. There is no waiting queue, and every transaction reaches a leg or a commit attempt, so this equals the injected delay (NaN if N = 0) and is descriptive only |
| L\* (minimum liquidity level) | Per model and seed: the lowest multiplier on the Exp3 grid at which Success Rate >= **95% (DV)**, at that level and every higher level | none | If none qualifies: "not reached", ranked above all levels. A coarse grid makes ties likely |

## 6. Experiment design

**Common to all main runs.** Seeds 1 to 30 (DV, adjustable; if changed, change for all hypotheses and log it in `results/experiment_log.csv`). All three models get the same transactions within a seed. Unlisted settings keep the base case from sec. 4. Outputs in `results/`: `run_metrics.csv` (one row per run with every metric; the source for paired differences and per-seed L\*), `summary.csv` (per-condition mean, min, max across seeds), `experiment_log.csv` (one row per run: experiment, model, seed, all parameters, code version), figures in `results/figures/`. File names for separate per-experiment CSVs may be added; they must stay in `results/`.

| Exp | Varied (DV) | Fixed (DV) |
|---|---|---|
| 1 Baseline | none (3 models; plus 0% failure sanity run) | 500 transactions, 2 banks, ample liquidity, delay 60 s, failure 1% |
| 2 Volume Stress | One factor at a time, others at baseline: Volume {100, 500, 1000}; Banks {2, 5, 10}; Arrival {sequential, burst}. Used with Exp3's liquidity grid for H3 | ample liquidity (H3: grid), delay 60 s, failure 1% |
| 3 Liquidity Stress | Liquidity multiplier grid. Combined with each Exp2 factor level (one at a time) to get L\* for H3 | 500 transactions, 2 banks, delay 60 s, failure 1% |
| 4 Delay / Failure Stress | One at a time: Failure {0, 1, 5}% at delay 60 s; Delay {0, 60, 300} s at failure 1%. H4b cells: delay {0, 60, 300} s at failure 1% and the H4b level from the calibration (JPY multiplier 0.09375, attempt 2; USD at the reference) | 500 transactions, 2 banks, ample liquidity (except H4b cells) |

The 0% failure run is a sensitivity check (no `partial`, no failure expected at ample liquidity). `timeout` is not triggered (sec. 3), so it cannot produce states in this run.

**Liquidity calibration (before the main runs, once the engine exists).** The placeholder reference and multipliers may leave too few levels with any shortage, which would make H1b and H4b untestable. So the levels are set by a separate calibration, fixed before any main run:
- Seeds 101 to 110 (DV), separate from the main seeds. Models A, B and C, failure 0%. Only `insufficient_funds` counts are read; no metric used in a decision is inspected.
- The reference starts at the placeholder in sec. 4 and doubles (both currencies together) until it is ample, at most 5 times (DV). "Ample" = the reference level at which there is no `insufficient_funds` in any model and calibration seed, in every condition that Exp1, 2 and 4 run at ample liquidity (this includes the largest volume, 10 banks, burst arrival and the 300 s delay).
- **Attempt 2 (from Day 11, decided before any main run).** In the grid and H4b stages only JPY is scaled: JPY = reference JPY x 2^d x multiplier, USD fixed at reference USD x 2^d (d = doublings in the ample stage). Reason: with 2 banks and both currencies scaled together, no Model A second-leg shortage occurred in attempt 1 or in test runs, and the proposed explanation points to the grid construction (`findings.md` sec. 2). All other rules below are unchanged.
- The grid has 5 levels (DV): the reference plus 4 lower levels, starting at multipliers 75%, 50%, 25%, 10% (applied to JPY only in attempt 2). Under Exp3's fixed settings, at least 2 lower levels (DV) must have a `partial` with reason `insufficient_funds` in Model A in every calibration seed (the condition H1b needs). If not, all 4 lower multipliers are halved and the check is repeated, at most 3 times (DV). The grid is then fixed and not refined. If a limit is reached without meeting its condition, no main run starts: the failed condition is recorded in `results/experiment_log.csv` and `findings.md`, and H1b and H4b are reported as untestable unless the design is revised and recorded before any main run.
- The H4b level is the highest grid level at which Model A has a `partial` with reason `insufficient_funds` in at least half of the calibration seeds (DV), at each of the delays 0, 60 and 300 s. If no level qualifies, H4b is recorded as untestable before any main run.
- The chosen values are saved in a calibration CSV in `results/` (if a limit is reached, the file records the failed condition instead). The calibration is logged as one summary row in `results/experiment_log.csv`; the per-run column layout of that file is fixed when the main runs start. Attempt-1 files: `results/calibration_attempt1.csv`, `results/calibration_checks_attempt1.csv` (renamed on Day 11; contents unchanged). Attempt-2 file names are set when it is run.
- Run record, attempt 1 (Day 10, 2026-11-09, commit `151fe7a`, both currencies scaled): ample was reached at the placeholder reference with 0 doublings; the grid condition was not met after 3 halvings (no Model A `partial` with `insufficient_funds` at any level). The H4b level was not computed. See `findings.md` sec. 1 and 2.
- **Fallback, fixed before attempt 2.** If attempt 2 also fails, there is no third revision. H1b and H4b are recorded Inconclusive (untestable); the Exp3 grid is fixed at the original multipliers 100, 75, 50, 25 and 10% (JPY only); Exp1 proceeds at the ample reference.
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

- Synthetic parameters: uniform sizes, random bank pairs, fixed rate. Results do not describe real flows.
- No netting, credit, or fund reuse beyond in-run receipts, so liquidity needs are likely to differ from real arrangements (proxy only).
- Model choices drive outcomes: some H1 results follow from definitions. Required tests keep these separate from evidence.
- Failure probability is a single independent draw; real failures are correlated.
- The decision rules in `hypotheses.md` (paired rule for model comparisons, range rule for H3) depend on the number of seeds and are not statistical tests.
- Grid choices (liquidity levels, target 95%) can change L\*. The calibration reduces but does not remove this.
- From Day 11 the liquidity grid lowers JPY only; USD stays at the reference. Exp3 "liquidity stress" is therefore JPY liquidity stress, and a first-leg USD shortage is not expected there. L\* (H3) and the success-rate change (H4a) measure sensitivity to JPY liquidity only and may not carry over to a stress on both currencies or on USD. The second leg is JPY in every model, so this choice also shapes which shortages can appear.
- W drives the size of duration-weighted exposure, so that metric is not a delay effect. It is descriptive only.
- Amount-based Principal Exposure ignores delay directly, so delay can change it only through balances (second-leg shortages). H4b may therefore show little or no difference.
- Liquidity is set per bank, so adding banks raises total liquidity and spreads flows. The bank-count effect on L\* is not a pure effect of participant numbers.
- Average Settlement Time and Operational Delay follow from the injected delay, so they do not compare the models' operational performance. That comparison rests on success, partial and failure rates under stress.
- Gross Prefunding and Liquidity Utilization convert JPY as `jpy_amount` / `fx_rate` in floating point, while the ledger moves JPY rounded to hundredths. At rates other than 150.00 the two can differ by a rounding error. Every experiment uses 150.00.
- Fractional delays (for example 0.1 s) can break the same-time ordering rule in sec. 7 through floating-point error in arrival + delay. The experiment levels (0, 60, 300 s with integer arrival times) are not affected.

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
3. Sequential arrival is one transaction every 10 s; burst is 10 transactions every 100 s (sec. 4). `arrival_time` was added to the generator on Day 5.
4. Model B reservations are used at leg completion and released at failure. Model C validates and commits once, at arrival + delay (sec. 2).
5. W = 3,600 s cut-off, used for every `partial` (sec. 5). Duration-weighted exposure is descriptive only.
6. The Peak Liquidity Proxy is implementable as a running maximum in the ledger (sec. 5).
7. With more than 2 banks, the two banks are drawn uniformly at random per transaction (sec. 4).
8. H2's primary comparison is the B minus A proxy gap at 300 s vs 0 s delay; C vs A becomes exploratory. H4b's primary metric is amount-based Principal Exposure. Both changed after the Day 4 review, before any experiment (`hypotheses.md`).

Decided on Day 6, before any experiment: the number of banks is a run parameter (`n_banks`), and the ledger's bank list comes from it, not from the transaction rows, so a bank with no transactions still counts in total liquidity. In Model A a second leg moves only JPY and an arrival moves only USD, so their same-time order in sec. 7 cannot change a Model A result; it matters from Model B onward. This was confirmed on Day 7 by behaviour tests in Model B: reversing the order made those tests fail in a manual check on Day 7 (sec. 7, processing rules).

Decided on Day 7, before any experiment: Model B checks that both reservations fit before making either. If one does not fit, nothing is reserved, so a failed reservation changes no balance, no reserved amount and no peak drawdown (the same validate-then-apply shape as Model C). Without this rule, a USD reservation made and then released in the same step would raise the Peak Liquidity Proxy of B for a transaction that moved nothing.

Decided on Day 9, before any experiment: the metric functions in `src/metrics.py` take the results of one run of one model and reject mixed models. Counts by failure reason list every reason, including `timeout` as 0. Duration-weighted Principal Exposure takes `usd_amount` from the input rows by `transaction_id`, so the result record is unchanged. In A and B the first leg (USD) completes at arrival, so a `settled` transaction's window is `end_time` - `arrival_time`.

Decided on Day 10, before any experiment: the liquidity and time metrics follow the rows in sec. 5. The fx rate for the Peak Liquidity Proxy is taken from the input `fx_rate` column, which must hold one value (`SimulationParams` has no rate). Metrics that do not apply to a model, or that have no data, are NaN, never 0. `calculate_metrics` also takes the run's ledger, because the proxy reads its peak drawdowns; the simulator is unchanged.

Decided on Day 11, before any main run: after the attempt-1 calibration did not meet its grid condition, the grid is rebuilt by scaling JPY only (USD fixed at the reference; the ample stage still doubles both currencies) and the calibration is repeated once (attempt 2). If attempt 2 also fails there is no third revision: H1b and H4b are recorded Inconclusive (untestable) and the Exp3 grid is fixed at 100, 75, 50, 25 and 10% (JPY only). The attempt-1 files were renamed with the suffix `_attempt1`. Decision rules in `hypotheses.md` are unchanged. The JPY-only consequence is listed in sec. 9. Details and reasons: `findings.md` sec. 2.
