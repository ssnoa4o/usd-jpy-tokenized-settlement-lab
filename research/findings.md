# Findings (draft)

Status: Day 11, 2026-11-10. **The Exp1 baseline was run on Day 11 (descriptive only; sec. 3). No hypothesis verdict has been recorded yet.** Exp2 to Exp4 have not been run. This file records outcomes in the order they happen. Hypotheses are recorded as supported / not supported / inconclusive only after the main runs, under the rules fixed in `hypotheses.md`.

This is an independent research prototype on synthetic data. No institution (BIS, BoJ, CLS, OSFI or any other) has reviewed, approved or endorsed it.

## 1. Liquidity calibration, attempt 1 (methodology sec. 6)

Run once on 2026-11-09 (UTC 22:35:19), code at commit `151fe7a`, seeds 101 to 110, failure probability 0%, models A, B and C. In this attempt both currencies were scaled together. Sources: `results/calibration_attempt1.csv`, `results/calibration_checks_attempt1.csv` (renamed on Day 11 from `calibration.csv` and `calibration_checks.csv`; contents unchanged), `results/experiment_log.csv` (the Day 10 row is unchanged).

| Step | Rule (sec. 6) | Outcome |
|---|---|---|
| Ample reference | No `insufficient_funds` in any model, seed and ample condition; double up to 5 times | Met at the placeholder reference (USD 100,000,000 and JPY 15,000,000,000 per bank), 0 doublings |
| Grid | At least 2 lower levels with a Model A `partial` / `insufficient_funds` in every seed; halve up to 3 times | **Not met.** After 3 halvings (final lower multipliers 0.09375, 0.0625, 0.03125, 0.0125) no level qualified. In all 16 lower levels tried, Model A had 0 `partial` with `insufficient_funds` in any of the 10 seeds; shortages occurred only as `failed` (first-leg) |
| H4b level | Depends on the grid | Not computed |

Under sec. 6 as written for attempt 1, no main run started. No verdict on H1b or H4b was recorded for attempt 1; the design was revised before any main run (sec. 2). The H4b level was not computed, and the H4b-cell check in `hypotheses.md` (delays 0, 60 and 300 s) was not run; the attempt-1 grid checked only the 60 s delay.

## 2. Decision recorded on Day 11, before any main run

**Cause check (test seeds 201 to 205; tests, not results).** Two tests in `tests/test_calibration.py` pass:
- `test_two_banks_symmetric_scaling_never_gives_second_leg_shortage`
- `test_lowering_jpy_only_can_give_second_leg_shortage`

Proposed explanation (a hypothesis, not a proof): with 2 banks, the bank that pays JPY at the second leg received the same USD value at the first leg (fx 150). With failure 0% and both currencies scaled together, its JPY tends to stay covered while the other bank runs short of USD first, at the first-leg funds check. This is not a strict invariant: legs of different transactions overlap (60 s delay, 10 s spacing), and USD held for an in-flight transaction can let the other bank pay more USD. The first test therefore records an observation only (no Model A second-leg shortage on test seeds 201 to 205 at multipliers 1 to 0.0125); shortages appeared only as first-leg `failed`. This is consistent with the attempt-1 grid condition not being reached. The second leg is JPY in every model, so lowering JPY alone allows second-leg shortages; the second test shows only that this is possible, not how often it happens.

An earlier diagnostic points the same way: `scripts/diagnose_two_bank_mirror.py`, output `results/diagnostic_two_bank_mirror.csv` (test seeds 201 to 205, Model A, 500 transactions, sequential, delay 60 s, failure 0%, multipliers 0.25, 0.1, 0.05, 0.0125). With 2 banks, bank A's JPY change equalled -150 times its USD change at the end of each run (`mirror_gap_jpy` = 0.0 in every row), with no second-leg shortage at any multiplier. With 5 banks the same diagnostic showed second-leg shortages at multipliers 0.1 and below. These are checks of the design, not findings about settlement models.

**Decision (user, Day 11, before any main run).** Revise how the grid is built and repeat the calibration (attempt 2):
- Ample stage: unchanged (both currencies doubled together from the placeholder reference).
- Grid and H4b stages: only JPY is scaled, JPY = reference JPY x 2^d x multiplier, with USD fixed at reference USD x 2^d (d = number of doublings).
- All other rules unchanged: start multipliers 75, 50, 25, 10%; at least 2 lower levels with a Model A `partial` / `insufficient_funds` in every calibration seed; halve at most 3 times; H4b level = highest level with such a `partial` in at least half of the seeds at each of delays 0, 60 and 300 s; seeds 101 to 110; failure 0%.

**Reason.** Attempt 1 did not reach its grid condition, and the explanation above points to how the grid was built rather than to the liquidity level. Lowering JPY alone is the smallest change that makes a Model A second-leg shortage possible without changing any decision rule in `hypotheses.md`.

**Pre-fixed fallback.** If attempt 2 also fails, there is no third revision. H1b and H4b are recorded as Inconclusive (untestable). The Exp3 grid is then fixed at the original multipliers 100, 75, 50, 25 and 10% (JPY only), and the Exp1 baseline proceeds at the ample reference.

**Consequence (threat to validity; methodology sec. 9).** Exp3 "liquidity stress" now means JPY liquidity stress, with USD at the reference. A first-leg USD shortage is not expected in Exp3. This changes what L\* (H3) and the success-rate change (H4a) measure: they describe sensitivity to JPY liquidity only, not to both currencies.

### Attempt 2 (run on Day 11)

Run once on 2026-11-10 (UTC 05:29:22), code at commit `3927553`, seeds 101 to 110, failure probability 0%, models A, B and C, grid scaling JPY only. Sources: `results/calibration.csv`, `results/calibration_checks.csv`, `results/experiment_log.csv` (attempt-2 row). Recorded only; not interpreted.

| Step | Rule (sec. 6) | Outcome |
|---|---|---|
| Ample reference | As in attempt 1 | Met at the placeholder reference (USD 100,000,000 and JPY 15,000,000,000 per bank), 0 doublings; 0 `insufficient_funds` in all 240 ample count rows |
| Grid | As in attempt 1, JPY only | **Met** after 3 halvings. Final lower JPY multipliers 0.09375, 0.0625, 0.03125, 0.0125 (USD at the reference). Qualifying lower levels (a Model A `partial` / `insufficient_funds` in all 10 seeds): 0.03125 and 0.0125 |
| H4b level | Highest level with such a `partial` in at least half of the seeds at each of delays 0, 60, 300 s | 0.09375 (H4b testable) |

Fixed for the main runs: ample reference USD 100,000,000 / JPY 15,000,000,000 per bank; Exp3 grid = JPY multipliers 1, 0.09375, 0.0625, 0.03125, 0.0125 (USD at the reference); H4b cells at JPY multiplier 0.09375. Which Exp3 levels are "active" for H1b is decided from the main runs (30 seeds), as `hypotheses.md` states, not from the calibration.

## 3. Exp1 Baseline (descriptive only; no hypothesis verdict)

**Setup.** Run on 2026-11-10 at code commit `743f1ba` (`git_commit` and `run_utc` in `results/run_metrics.csv`). Seeds 1 to 30, 500 transactions, 2 banks, sequential arrival, delay 60 s, cut-off W = 3,600 s. Reference balances USD 100,000,000 and JPY 15,000,000,000 per bank (ample; calibration attempt 2, sec. 2). Two conditions: `baseline` (failure probability 1%) and `sanity_0pct` (failure probability 0%). All three models see the same transactions within a seed. Ample liquidity held: `n_insufficient_funds` = 0 in every run (the max is 0 in every row for that metric). The data are synthetic.

Sources: `results/baseline_results.csv` (per condition, model and metric: `mean`, `min`, `max` over 30 seeds; `n_valid` = 30 unless stated), with `results/run_metrics.csv` and `results/experiment_log.csv` as the per-run records. Each cell is "mean [min, max]". Numbers are rounded to 4 significant figures; small integers and exact values are shown as they are in the file. Models: A Sequential (`sequential`), B Prefunded (`prefunded`), C Atomic PvP (`atomic`).

### 3.1 Condition `baseline` (failure 1%)

| Metric | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| success_rate | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] |
| partial_rate | 0.009533 [0.004, 0.02] | 0.009533 [0.004, 0.02] | 0 [0, 0] |
| failure_rate | 0 [0, 0] | 0 [0, 0] | 0.009533 [0.004, 0.02] |
| n_partial | 4.767 [2, 10] | 4.767 [2, 10] | 0 [0, 0] |
| n_failed | 0 [0, 0] | 0 [0, 0] | 4.767 [2, 10] |
| n_technical_failure | 4.767 [2, 10] | 4.767 [2, 10] | 4.767 [2, 10] |
| n_insufficient_funds | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| principal_exposure_usd | 2,596,000 [605,800, 5,169,000] | 2,596,000 [605,800, 5,169,000] | 0 [0, 0] |
| principal_exposure_usd_seconds (W = 3,600 s) | 2.573e10 [1.874e10, 3.469e10] | 2.573e10 [1.874e10, 3.469e10] | 0 [0, 0] |
| gross_prefunding_usd | n/a (not applicable) | 5.512e8 [5.312e8, 5.695e8] | 5.512e8 [5.312e8, 5.695e8] |
| liquidity_utilization | n/a (not applicable) | 0.9953 [0.9905, 0.9989] | 0.9906 [0.9811, 0.9978] |
| peak_liquidity_proxy_usd (proxy) | 4.007e7 [2.244e7, 8.049e7] | 4.221e7 [2.470e7, 8.169e7] | 4.013e7 [2.244e7, 8.041e7] |
| average_settlement_time_seconds | 60 [60, 60] | 60 [60, 60] | 60 [60, 60] |

For A, `gross_prefunding_usd` and `liquidity_utilization` have `n_valid` = 0 (the metrics are not defined for A), so they are not applicable and are not zero.

### 3.2 Condition `sanity_0pct` (failure 0%)

At 0% failure, every model has success_rate 1 [1, 1]; partial_rate, failure_rate, n_partial, n_failed, n_technical_failure and n_insufficient_funds are 0 [0, 0]; principal_exposure_usd is 0 [0, 0]; and average_settlement_time_seconds is 60 [60, 60]. The other metrics are:

| Metric | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| principal_exposure_usd_seconds (W = 3,600 s) | 1.654e10 [1.594e10, 1.708e10] | 1.654e10 [1.594e10, 1.708e10] | 0 [0, 0] |
| gross_prefunding_usd | n/a (not applicable) | 5.512e8 [5.312e8, 5.695e8] | 5.512e8 [5.312e8, 5.695e8] |
| liquidity_utilization | n/a (not applicable) | 1 [1, 1] | 1 [1, 1] |
| peak_liquidity_proxy_usd (proxy) | 4.001e7 [2.244e7, 8.057e7] | 4.217e7 [2.457e7, 8.177e7] | 4.001e7 [2.244e7, 8.057e7] |

### 3.3 Reading notes

These notes separate what the table reports from how it may be read. Exp1 has no decision rule and no hypothesis verdict.

**Correctness checks, not evidence.** Each item below follows from the model rules and the injection rule (`methodology.md` sec. 5 and 7; `hypotheses.md`: guaranteed by design is not evidence). The table is consistent with all of them, which is what a correct implementation should give. None of them supports or fails to support any hypothesis.
- Model C has `n_partial` = 0 and principal exposure 0 in both conditions.
- A and B have identical principal exposure (both measures) at ample liquidity with no `insufficient_funds`.
- A transaction hit by the injected failure is `partial` in A and B and `failed` in C. For this reason `n_partial` in A and B equals `n_failed` in C (4.767 each in `baseline`), and `n_technical_failure` is the same in all three models.
- Average settlement time is 60 s in every model and condition. Every `settled` transaction takes exactly the delay, so equality is by construction.
- Gross prefunding is equal in B and C here. Both count both legs of each transaction. B counts `settled` and `partial` transactions and C counts `settled` and `technical_failure` transactions (`methodology.md` sec. 5). With no `insufficient_funds` in these runs, the same transactions are counted, so the two sums are equal by construction.
- The peak liquidity proxy of A and C is identical at 0% failure. At 1% failure it differs (A 4.007e7, C 4.013e7 mean), which is consistent with methodology sec. 5 (at constant delay the two can differ only through transactions hit by an injected failure); this was not checked transaction by transaction. B's proxy is higher than A's in both conditions, which is consistent with B reserving funds before settlement (the proxy counts reserved funds as unavailable; this is partly definitional).

**What the table reports.** In `baseline`, all three models have the same mean success rate (0.9905), since a failure-hit transaction is not `settled` in any of them. The models differ in how those transactions are recorded (`partial` or `failed`), in principal exposure (nonzero in A and B, 0 in C), and in `liquidity_utilization` (B 0.9953, C 0.9906). The ranges across seeds are wide for exposure (A and B: 605,800 to 5,169,000 USD) partly because the number of injected failures varies by seed (2 to 10).

**Interpretation (tentative).** Under these simplified models and synthetic inputs, an injected second-leg failure leaves exposure in A and B and none in C. This is the design of the models. It is not a test of how often or how large such exposure would be in real markets. `principal_exposure_usd_seconds` depends on W: each unrepaired `partial` contributes W regardless of delay (`methodology.md` sec. 5), so the A and B values in `baseline` also include a W-driven part and should not be read as a measured duration of real exposure.

**Limits of this baseline.**
- Liquidity is ample, so it says nothing about liquidity shortage. In these models at ample liquidity, Model C leaves no one-leg-only exposure by design; this run does not test liquidity risk.
- `gross_prefunding_usd` is not peak liquidity, and the peak proxy ignores netting and credit.
- Smart-contract-style completion in the simulation is not legal settlement finality.
- The models are simplified, the data are synthetic, and only 2 banks, one delay and one failure level are used.
- No policy suggestion follows from Exp1 alone.

### 3.4 Protocol note

Before the committed run, during development on 2026-11-10, a timing dry run of the runner used the main seeds 1 to 30 in a temporary directory. The code was uncommitted and the outputs were deleted. Its values were not used or recorded, but the first few lines of its `baseline_results.csv` were printed and seen during the format check (a `head` of the file, condition `baseline`). The runner was then changed after review (self-checks, `n_valid`, dirty-tree refusal); the committed run used commit `743f1ba`. Exp1 has no decision rule, so this cannot change any verdict. From now on, dry runs use test seeds only.
