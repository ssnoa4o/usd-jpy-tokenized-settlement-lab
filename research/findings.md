# Findings (draft)

Status: Day 10, 2026-11-09. **No main experiment has been run.** This file records outcomes in the order they happen. Hypotheses are recorded as supported / not supported / inconclusive only after the main runs, under the rules fixed in `hypotheses.md`.

This is an independent research prototype on synthetic data. No institution (BIS, BoJ, CLS, OSFI or any other) has reviewed, approved or endorsed it.

## 1. Liquidity calibration (methodology sec. 6)

Run once on 2026-11-09 (UTC 22:35:19), code at commit `151fe7a`, seeds 101 to 110, failure probability 0%, models A, B and C. Sources: `results/calibration.csv`, `results/calibration_checks.csv`, `results/experiment_log.csv`.

| Step | Rule (sec. 6) | Outcome |
|---|---|---|
| Ample reference | No `insufficient_funds` in any model, seed and ample condition; double up to 5 times | Met at the placeholder reference (USD 100,000,000 and JPY 15,000,000,000 per bank), 0 doublings |
| Grid | At least 2 lower levels with a Model A `partial` / `insufficient_funds` in every seed; halve up to 3 times | **Not met.** After 3 halvings (final lower multipliers 0.09375, 0.0625, 0.03125, 0.0125) no level qualified. In all 16 lower levels tried, Model A had 0 `partial` with `insufficient_funds` in any of the 10 seeds; shortages occurred only as `failed` (first-leg) |
| H4b level | Depends on the grid | Not computed |

Under sec. 6, no main run starts, and H1b and H4b are to be reported as untestable unless the design is revised and recorded before any main run. That decision is open (see sec. 2). No verdict is recorded yet:
- H1b: if the design is kept, this would be recorded as Inconclusive (untestable under the chosen grid), the label in `hypotheses.md`.
- H4b: not evaluated. The H4b level was not computed, and the H4b-cell check in `hypotheses.md` (delays 0, 60 and 300 s) was not run; the calibration grid checked only the 60 s delay.

## 2. Open decision (before any main run)

A diagnostic on test seeds 201 to 205 (not calibration or main seeds; not a result) is consistent with a structural cause. Script: `scripts/diagnose_two_bank_mirror.py`; output: `results/diagnostic_two_bank_mirror.csv` (Model A, 500 transactions, sequential, delay 60 s, failure 0%, multipliers 0.25, 0.1, 0.05, 0.0125). With 2 banks, every transaction is between the same two banks. At the end of each run, bank A's JPY change equalled -150 times its USD change (`mirror_gap_jpy` = 0.0 in every row), and there was no second-leg shortage at any multiplier. A possible reading: the bank that would be short of JPY for a second leg is the one that has received USD, while the other bank runs short of USD first, at the earlier first leg. With 5 banks the same diagnostic showed second-leg shortages at multipliers 0.1 and below. This is an explanation to be checked, not a finding about settlement models.

Options to decide and record before any main run: report H1b and H4b as untestable, or revise how the liquidity grid is built (for example, lowering one currency only) and repeat the calibration with the revision and its reason recorded. The failed calibration above stays in the record either way.
