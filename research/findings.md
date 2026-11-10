# Findings (draft)

Status: Day 12, 2026-11-10. **The Exp1 baseline was run on Day 11 (descriptive only; sec. 3). The Exp3 and Exp4 main runs were done on Day 12 and the verdicts for H1b, H2, H4a and H4b computed by pre-committed code are recorded in sec. 4. H3 is not computed yet (it needs Exp2 combined with Exp3).** Exp2 has not been run. This file records outcomes in the order they happen. Hypotheses are recorded as supported / not supported / inconclusive only after the main runs, under the rules fixed in `hypotheses.md`.

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

## 4. Exp3 and Exp4 stress runs (Day 12)

### 4.1 Run record

Main run of Exp3 (liquidity stress, JPY only) and Exp4 (failure, delay and H4b cells) on 2026-11-10 (`run_utc` 2026-11-10T23:29:23Z to 23:29:34Z in `results/stress_run_metrics.csv`), from the clean commit `5c3d59b` (runner `stress` in `src/experiments.py`; verdict code `src/verdicts.py`). Seeds 1 to 30, 500 transactions, 2 banks, sequential arrival, cut-off W = 3,600 s. 13 cells x 3 models x 30 seeds = 1,170 runs. Reference balances USD 100,000,000 and JPY 15,000,000,000 per bank (calibration attempt 2, sec. 2); in the JPY-stressed cells only JPY is lowered (JPY = 15,000,000,000 x multiplier; USD stays at the reference). Every run in a cell flagged ample had `n_insufficient_funds` = 0 (max 0 in every such row of `results/stress_test_results.csv`), so there was no ample violation and no verdict was withheld under methodology sec. 6.

Sources: `results/stress_run_metrics.csv` (one row per run; includes `ample_cell`, `jpy_multiplier`, `git_commit`, `run_utc`), `results/stress_test_results.csv` (per cell, model and metric: `mean`, `min`, `max` over 30 seeds, `n_valid`), `results/verdicts.csv`, `results/summary.csv` (rebuilt: Exp1 plus the stress experiments) and `results/experiment_log.csv` (1,170 rows added).

| Experiment | Cell (`condition`) | Failure probability | Delay (s) | JPY multiplier | Ample flag |
|---|---|---|---|---|---|
| exp3_liquidity | jpy_1 | 1% | 60 | 1 | yes |
| exp3_liquidity | jpy_0.09375 | 1% | 60 | 0.09375 | no |
| exp3_liquidity | jpy_0.0625 | 1% | 60 | 0.0625 | no |
| exp3_liquidity | jpy_0.03125 | 1% | 60 | 0.03125 | no |
| exp3_liquidity | jpy_0.0125 | 1% | 60 | 0.0125 | no |
| exp4_failure | failure_0 | 0% | 60 | 1 | yes |
| exp4_failure | failure_0.01 | 1% | 60 | 1 | yes |
| exp4_failure | failure_0.05 | 5% | 60 | 1 | yes |
| exp4_delay | delay_0 | 1% | 0 | 1 | yes |
| exp4_delay | delay_300 | 1% | 300 | 1 | yes |
| exp4_h4b | h4b_delay_0 | 1% | 0 | 0.09375 | no |
| exp4_h4b | h4b_delay_60 | 1% | 60 | 0.09375 | no |
| exp4_h4b | h4b_delay_300 | 1% | 300 | 0.09375 | no |

The ample (60 s, 1%) cell of Exp4 delay is the `exp4_failure` cell `failure_0.01`; it was run once and is not run again as `delay_60`. In `stress_test_results.csv`, the cells `exp3_liquidity` / `jpy_1`, `exp4_failure` / `failure_0.01` and the Exp1 `baseline` condition (sec. 3.1) have identical parameters (1% failure, delay 60 s, reference balances). Their numbers match: in `stress_test_results.csv` the two stress cells are identical in every metric and model (for example Success Rate 0.9905 [0.98, 0.996]; Principal Exposure of A and B 2,596,000 [605,800, 5,169,000]), they equal each other in every numeric column, and per seed they equal the Exp1 baseline in `results/run_metrics.csv` exactly (Success Rate, Principal Exposure, Peak Liquidity Proxy and Gross Prefunding; checked for all 30 seeds and all three models). The sec. 3.1 values are therefore the same (Peak Liquidity Proxy 4.007e7, 4.221e7 and 4.013e7 for A, B and C). Likewise `h4b_delay_60` has the same parameters as `exp3_liquidity` / `jpy_0.09375` and shows the same numbers.

### 4.2 Results by cell

Every cell is "mean [min, max]" over 30 seeds, taken from `results/stress_test_results.csv`. Rounding: rates to 4 significant figures; USD amounts to 4 significant figures, shown in whole USD with thousands separators; exact values such as 0 and 1 are shown as they are. Models: A Sequential, B Prefunded, C Atomic PvP. Rows for `jpy_1`, `failure_0.01` and `h4b_delay_60` repeat numbers from other rows as explained in sec. 4.1. Peak Liquidity Proxy is a proxy (methodology sec. 5), not Peak Liquidity.

**Success Rate** (counts `settled` only; `partial` is not included)

| Cell | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| jpy_1 | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] |
| jpy_0.09375 | 0.9698 [0.9, 0.992] | 0.9654 [0.9, 0.992] | 0.9698 [0.9, 0.992] |
| jpy_0.0625 | 0.952 [0.896, 0.986] | 0.9438 [0.896, 0.988] | 0.952 [0.896, 0.986] |
| jpy_0.03125 | 0.9067 [0.866, 0.954] | 0.8583 [0.822, 0.892] | 0.9067 [0.866, 0.954] |
| jpy_0.0125 | 0.7727 [0.732, 0.816] | 0.5278 [0.504, 0.578] | 0.7727 [0.732, 0.816] |
| failure_0 | 1 [1, 1] | 1 [1, 1] | 1 [1, 1] |
| failure_0.01 | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] |
| failure_0.05 | 0.9515 [0.936, 0.97] | 0.9515 [0.936, 0.97] | 0.9515 [0.936, 0.97] |
| delay_0 | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] |
| delay_300 | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] | 0.9905 [0.98, 0.996] |
| h4b_delay_0 | 0.9698 [0.9, 0.992] | 0.9698 [0.9, 0.992] | 0.9698 [0.9, 0.992] |
| h4b_delay_60 | 0.9698 [0.9, 0.992] | 0.9654 [0.9, 0.992] | 0.9698 [0.9, 0.992] |
| h4b_delay_300 | 0.9698 [0.9, 0.992] | 0.8883 [0.858, 0.922] | 0.9698 [0.9, 0.992] |

**Partial Rate**

| Cell | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| jpy_1 | 0.009533 [0.004, 0.02] | 0.009533 [0.004, 0.02] | 0 [0, 0] |
| jpy_0.09375 | 0.0302 [0.008, 0.1] | 0.009333 [0.004, 0.02] | 0 [0, 0] |
| jpy_0.0625 | 0.048 [0.014, 0.104] | 0.009133 [0.002, 0.02] | 0 [0, 0] |
| jpy_0.03125 | 0.09327 [0.046, 0.134] | 0.0084 [0.002, 0.016] | 0 [0, 0] |
| jpy_0.0125 | 0.2273 [0.184, 0.268] | 0.005333 [0, 0.014] | 0 [0, 0] |
| failure_0 | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| failure_0.01 | 0.009533 [0.004, 0.02] | 0.009533 [0.004, 0.02] | 0 [0, 0] |
| failure_0.05 | 0.04853 [0.03, 0.064] | 0.04853 [0.03, 0.064] | 0 [0, 0] |
| delay_0 | 0.009533 [0.004, 0.02] | 0.009533 [0.004, 0.02] | 0 [0, 0] |
| delay_300 | 0.009533 [0.004, 0.02] | 0.009533 [0.004, 0.02] | 0 [0, 0] |
| h4b_delay_0 | 0.0302 [0.008, 0.1] | 0.009267 [0.002, 0.018] | 0 [0, 0] |
| h4b_delay_60 | 0.0302 [0.008, 0.1] | 0.009333 [0.004, 0.02] | 0 [0, 0] |
| h4b_delay_300 | 0.0302 [0.008, 0.1] | 0.008733 [0.002, 0.018] | 0 [0, 0] |

**Failure Rate** (`failed` only: neither leg completed)

| Cell | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| jpy_1 | 0 [0, 0] | 0 [0, 0] | 0.009533 [0.004, 0.02] |
| jpy_0.09375 | 0 [0, 0] | 0.02527 [0, 0.088] | 0.0302 [0.008, 0.1] |
| jpy_0.0625 | 0 [0, 0] | 0.04707 [0.004, 0.1] | 0.048 [0.014, 0.104] |
| jpy_0.03125 | 0 [0, 0] | 0.1333 [0.1, 0.176] | 0.09327 [0.046, 0.134] |
| jpy_0.0125 | 0 [0, 0] | 0.4669 [0.42, 0.494] | 0.2273 [0.184, 0.268] |
| failure_0 | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| failure_0.01 | 0 [0, 0] | 0 [0, 0] | 0.009533 [0.004, 0.02] |
| failure_0.05 | 0 [0, 0] | 0 [0, 0] | 0.04853 [0.03, 0.064] |
| delay_0 | 0 [0, 0] | 0 [0, 0] | 0.009533 [0.004, 0.02] |
| delay_300 | 0 [0, 0] | 0 [0, 0] | 0.009533 [0.004, 0.02] |
| h4b_delay_0 | 0 [0, 0] | 0.02093 [0, 0.088] | 0.0302 [0.008, 0.1] |
| h4b_delay_60 | 0 [0, 0] | 0.02527 [0, 0.088] | 0.0302 [0.008, 0.1] |
| h4b_delay_300 | 0 [0, 0] | 0.103 [0.074, 0.138] | 0.0302 [0.008, 0.1] |

**Principal Exposure, amount-based (USD)**

| Cell | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| jpy_1 | 2,596,000 [605,800, 5,169,000] | 2,596,000 [605,800, 5,169,000] | 0 [0, 0] |
| jpy_0.09375 | 9,602,000 [1,782,000, 33,650,000] | 2,508,000 [605,800, 5,169,000] | 0 [0, 0] |
| jpy_0.0625 | 15,500,000 [4,169,000, 36,760,000] | 2,436,000 [146,200, 5,169,000] | 0 [0, 0] |
| jpy_0.03125 | 30,990,000 [15,390,000, 42,920,000] | 2,231,000 [146,200, 4,366,000] | 0 [0, 0] |
| jpy_0.0125 | 76,250,000 [60,730,000, 86,590,000] | 1,230,000 [0, 3,167,000] | 0 [0, 0] |
| failure_0 | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| failure_0.01 | 2,596,000 [605,800, 5,169,000] | 2,596,000 [605,800, 5,169,000] | 0 [0, 0] |
| failure_0.05 | 13,600,000 [8,685,000, 18,600,000] | 13,600,000 [8,685,000, 18,600,000] | 0 [0, 0] |
| delay_0 | 2,596,000 [605,800, 5,169,000] | 2,596,000 [605,800, 5,169,000] | 0 [0, 0] |
| delay_300 | 2,596,000 [605,800, 5,169,000] | 2,596,000 [605,800, 5,169,000] | 0 [0, 0] |
| h4b_delay_0 | 9,602,000 [1,782,000, 33,650,000] | 2,497,000 [202,500, 4,909,000] | 0 [0, 0] |
| h4b_delay_60 | 9,602,000 [1,782,000, 33,650,000] | 2,508,000 [605,800, 5,169,000] | 0 [0, 0] |
| h4b_delay_300 | 9,602,000 [1,782,000, 33,650,000] | 2,280,000 [202,500, 4,291,000] | 0 [0, 0] |

**Peak Liquidity Proxy (USD, proxy)**

| Cell | A Sequential | B Prefunded | C Atomic PvP |
|---|---|---|---|
| jpy_1 | 40,070,000 [22,440,000, 80,490,000] | 42,210,000 [24,700,000, 81,690,000] | 40,130,000 [22,440,000, 80,410,000] |
| jpy_0.09375 | 34,840,000 [22,440,000, 50,310,000] | 31,070,000 [20,930,000, 37,640,000] | 29,670,000 [20,060,000, 37,420,000] |
| jpy_0.0625 | 31,610,000 [21,870,000, 48,120,000] | 23,650,000 [18,510,000, 26,220,000] | 23,210,000 [15,660,000, 24,930,000] |
| jpy_0.03125 | 26,180,000 [17,350,000, 46,350,000] | 12,910,000 [11,730,000, 14,890,000] | 12,340,000 [11,930,000, 12,480,000] |
| jpy_0.0125 | 22,490,000 [13,720,000, 42,760,000] | 5,566,000 [4,793,000, 6,915,000] | 4,962,000 [4,910,000, 4,988,000] |
| failure_0 | 40,010,000 [22,440,000, 80,570,000] | 42,170,000 [24,570,000, 81,770,000] | 40,010,000 [22,440,000, 80,570,000] |
| failure_0.01 | 40,070,000 [22,440,000, 80,490,000] | 42,210,000 [24,700,000, 81,690,000] | 40,130,000 [22,440,000, 80,410,000] |
| failure_0.05 | 39,690,000 [22,700,000, 78,050,000] | 42,020,000 [24,850,000, 79,250,000] | 39,370,000 [22,950,000, 75,540,000] |
| delay_0 | 40,070,000 [22,440,000, 80,490,000] | 40,070,000 [22,440,000, 80,490,000] | 40,130,000 [22,440,000, 80,410,000] |
| delay_300 | 40,070,000 [22,440,000, 80,490,000] | 53,870,000 [35,990,000, 91,080,000] | 40,130,000 [22,440,000, 80,410,000] |
| h4b_delay_0 | 34,840,000 [22,440,000, 50,310,000] | 29,760,000 [20,110,000, 37,460,000] | 29,670,000 [20,060,000, 37,420,000] |
| h4b_delay_60 | 34,840,000 [22,440,000, 50,310,000] | 31,070,000 [20,930,000, 37,640,000] | 29,670,000 [20,060,000, 37,420,000] |
| h4b_delay_300 | 34,840,000 [22,440,000, 50,310,000] | 28,810,000 [26,660,000, 31,870,000] | 29,670,000 [20,060,000, 37,420,000] |

At `delay_0` the B mean (40,073,707 USD) differs from the A mean (40,070,621 USD) only after the fourth significant figure (unrounded means from `stress_run_metrics.csv`, rounded to whole dollars), so the two rounded cells look equal. The per-cell values of the other metrics (counts by reason, Gross Prefunding, Liquidity Utilization, duration-weighted exposure, Average Settlement Time) are in `results/stress_test_results.csv`.

### 4.3 Verdicts

Copied from `results/verdicts.csv`. Every row has `git_commit` 5c3d59b3533790b5376d210c9f74d2468f3dddae and `seeds` 1-30. "diff" columns follow the note of each row (for H1b: A minus B of amount-based Principal Exposure; for H2 gap rows: B minus A of Peak Liquidity Proxy; for H4a: change_A minus change_C of Success Rate; for H4b: change_A minus change_B of amount-based Principal Exposure). `n_pos`, `n_neg` and `n_zero` count seeds (out of `n_seeds`) with a positive, negative or exactly zero paired difference. Blank cells are blank in the file.

| Hypothesis | Level | Role | Verdict | n_seeds | n_pos / n_neg / n_zero | mean_diff | Note |
|---|---|---|---|---|---|---|---|
| H1b | jpy_0.09375 | descriptive | (none) | 30 | 26 / 0 / 4 | 7093531.3623 | not informative: A partial with insufficient_funds in only 26/30 seeds; not counted |
| H1b | jpy_0.0625 | decides | supported | 30 | 30 / 0 / 0 | 13068133.901 | active: A partial with insufficient_funds in 30/30 seeds; diff = A minus B |
| H1b | jpy_0.03125 | decides | supported | 30 | 30 / 0 / 0 | 28761399.823 | active: A partial with insufficient_funds in 30/30 seeds; diff = A minus B |
| H1b | jpy_0.0125 | decides | supported | 30 | 30 / 0 / 0 | 75019582.6613 | active: A partial with insufficient_funds in 30/30 seeds; diff = A minus B |
| H1b | overall | overall | supported | | | | 3 active level(s) of 4 |
| H2 | gap_delay_0 | descriptive | (none) | 30 | 1 / 0 / 29 | 3086.3667 | B minus A peak_liquidity_proxy_usd (mean_diff = mean gap) |
| H2 | gap_delay_60 | descriptive | (none) | 30 | 30 / 0 / 0 | 2141185.1933 | B minus A peak_liquidity_proxy_usd (mean_diff = mean gap) |
| H2 | gap_delay_300 | descriptive | (none) | 30 | 30 / 0 / 0 | 13796006.6737 | B minus A peak_liquidity_proxy_usd (mean_diff = mean gap) |
| H2 | gap300_minus_gap0 | decides | supported | 30 | 30 / 0 / 0 | 13792920.307 | ample, failure 1% |
| H2 | overall | overall | supported | 30 | 30 / 0 / 0 | 13792920.307 | single comparison |
| H4a | jpy_0.09375 | direction_check | (none) | 30 | 0 / 0 / 30 | 0.0 | mean exactly 0: not a reversal |
| H4a | jpy_0.0625 | direction_check | (none) | 30 | 0 / 0 / 30 | 0.0 | mean exactly 0: not a reversal |
| H4a | jpy_0.03125 | direction_check | (none) | 30 | 0 / 0 / 30 | 0.0 | mean exactly 0: not a reversal |
| H4a | jpy_0.0125 | decides | not supported | 30 | 0 / 0 / 30 | 0.0 | highest stress alone (change_A minus change_C of success_rate); verdict is in the overall row |
| H4a | overall | overall | not supported | 30 | 0 / 0 / 30 | 0.0 | no difference at the highest stress in every seed |
| H4b | h4b_cells | active_check | (none) | | | | A rows with partial insufficient_funds in the H4b cells: 78 of 90 (any delay, any seed needed) |
| H4b | delay_300 | decides | inconclusive | 30 | 8 / 1 / 21 | 217165.3537 | highest stress alone (change_A minus change_B of principal_exposure_usd); verdict is in the overall row |
| H4b | delay_60 | direction_check | (none) | 30 | 1 / 2 / 27 | -10988.612 | mean has the opposite sign of the highest stress: reversal |
| H4b | overall | overall | inconclusive | 30 | 8 / 1 / 21 | 217165.3537 | mixed signs (or no seeds) at the highest stress |
| input_check | seeds | active_check | (none) | | | | seeds are exactly 1-30 |

H1a is descriptive (no verdict; `role` = descriptive, overall "descriptive only, no verdict"). Its values, from the `value_mean`, `value_min` and `value_max` columns of `verdicts.csv` (mean principal exposure in USD over 30 seeds, whole USD):

| Level | Model | value_mean [value_min, value_max] |
|---|---|---|
| failure_0 | A Sequential | 0 [0, 0] |
| failure_0 | B Prefunded | 0 [0, 0] |
| failure_0.01 | A Sequential | 2,596,141 [605,798, 5,168,553] |
| failure_0.01 | B Prefunded | 2,596,141 [605,798, 5,168,553] |
| failure_0.05 | A Sequential | 13,604,296 [8,685,342, 18,597,497] |
| failure_0.05 | B Prefunded | 13,604,296 [8,685,342, 18,597,497] |

The verdicts were computed by code that was written, reviewed and committed before the main run (commit `5c3d59b`; the `git_commit` and `seeds` columns of `verdicts.csv` record this). The decision rules in `hypotheses.md` were not changed.

### 4.4 Reading notes

These notes separate what the tables report from how it may be read. "Result" sentences restate the files; "reading" sentences are interpretation and are tentative.

**H1b.** Result: at the three active levels (JPY multipliers 0.0625, 0.03125 and 0.0125) B had lower amount-based Principal Exposure than A in all 30 seeds, with mean differences (A minus B) of 13,068,133.901, 28,761,399.823 and 75,019,582.6613 USD; the code records "supported". The level 0.09375 was not active (A had a `partial` with `insufficient_funds` in 26 of 30 seeds, not all 30), so it is not counted, although its paired differences (26 positive, 4 zero) are shown. Reading: `hypotheses.md` already states that the direction is largely design-driven, because B reserves both legs at arrival and so cannot have a second-leg `insufficient_funds` `partial`. The verdict is therefore not independent evidence about B. What the run adds is the size of the gap under this grid (Principal Exposure of A against B in the Exposure table above), which measures how much this one mechanism matters in the simplified model. The code's "Not supported" reading for H1b (B not lower than A in every seed at every active level) was not triggered.

**H2.** Result: the B minus A gap in Peak Liquidity Proxy at 300 s minus the gap at 0 s was positive in all 30 seeds (mean 13,792,920.307 USD); the code records "supported". The mean gaps were 3,086.3667 USD at 0 s (positive in 1 seed, zero in 29), 2,141,185.1933 USD at 60 s and 13,796,006.6737 USD at 300 s. Reading: `hypotheses.md` says the direction can be anticipated from the reservation rule (B holds the JPY leg from arrival, A pays it after the delay), so the size of the gap over the delay is the main information. The proxy is partly definitional (reserved funds count as unavailable) and ignores netting and credit.

**H4a.** Result: Success Rate of A equals that of C in all 150 (level, seed) pairs of `exp3_liquidity` (checked directly on per-run `success_rate` in `stress_run_metrics.csv`); the same holds in all 13 cells of Exp3 and Exp4 (390 pairs). `verdicts.csv` accordingly records the paired difference of the change (A minus C) as exactly 0 in 30 of 30 seeds at each level (`n_zero` = 30). The code records "not supported" under rule (1) of `hypotheses.md`, no difference at the highest stress. Proposed reading, not verified: with USD at the reference, both A and C fail to settle exactly when the JPY leg is short at the second leg (A) or at commit time (C), so the equality may follow from the model rules rather than be an empirical finding. This was not checked transaction by transaction. This result applies to JPY-only stress (methodology sec. 9) and says nothing about a USD shortage or a shortage in both currencies. Success Rate is equal; the models still differ in how the shortfall is recorded and in Principal Exposure (A leaves `partial`, C leaves `failed`).

**H4b.** Result: the code records "inconclusive". The active check passed (78 of 90 A rows in the H4b cells had a `partial` with `insufficient_funds`). At 300 s (the highest stress) the paired difference (change_A minus change_B of amount-based Principal Exposure) was positive in 8 seeds, negative in 1 and zero in 21 (mean 217,165.3537 USD); at 60 s it was positive in 1, negative in 2 and zero in 27 (mean -10,988.612 USD), which the code labels a reversal of direction. Mixed signs at the highest stress decide the verdict. Reading: `methodology.md` sec. 9 already anticipated that H4b might show little or no difference, because amount-based exposure ignores delay and delay can act only through balances. The result is consistent with that expectation. Duration-weighted exposure is reported in `stress_test_results.csv` as a descriptive value (W = 3,600 s) and was not used for the verdict.

**Exploratory and descriptive only (no verdict depends on it).** In the Success Rate table, B's mean falls faster than A's and C's at low JPY levels (0.5278 for B against 0.7727 for A and C at multiplier 0.0125) and at 300 s in the H4b cells (0.8883 for B against 0.9698). In B the shortfall appears mainly as `failed` (reservation not possible), not as `partial`. Proposed reading, not tested: B reserves the JPY leg at arrival, so JPY for in-flight transactions is unavailable to later arrivals, and a longer delay holds it longer. In the Exp3 low-JPY cells (multipliers 0.09375 to 0.0125) B's Peak Liquidity Proxy is also below A's and above C's (see the Peak Liquidity Proxy table), and its Gross Prefunding is below C's (for example 2.411e8 against 4.024e8 USD at multiplier 0.0125, from `stress_test_results.csv`), which may reflect fewer transactions passing reservation; this was not checked. This is a descriptive pattern in simplified models, not a test.

**Other checks and limits of this section.**
- H3 is not computed. It needs Exp2 combined with the Exp3 grid (planned for Day 13).
- Several outcomes in the tables follow from the model rules and are correctness checks, not evidence: Model C has Partial Rate 0 and Principal Exposure 0 in every cell; A and B have identical Principal Exposure at ample liquidity; Average Settlement Time equals the delay in every model.
- Under JPY-only stress the second leg is JPY in every model, so the shortages seen here are second-leg shortages (and, in B, reservation failures). The results do not describe a stress on USD or on both currencies.
- The models are simplified, the data are synthetic, and 2 banks, one arrival pattern, one seed set and a coarse grid are used. The decision rules are not statistical tests (methodology sec. 9).
- Smart-contract-style completion in the simulation is not legal settlement finality. Atomic PvP, as modelled in C, removes the one-leg-only state (principal risk in this model) but does not remove liquidity risk: C still fails when funds are short, as its Failure Rate shows (0.2273 at multiplier 0.0125).
- Peak Liquidity Proxy is a proxy; Gross Prefunding is not Peak Liquidity.
- No policy suggestion is drawn from these results alone. Any policy reading is deferred to `policy/policy_brief.md`, after all experiments, and must keep the limits above.
