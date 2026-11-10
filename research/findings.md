# Findings (draft)

Status: Day 11, 2026-11-10. **No main experiment has been run.** This file records outcomes in the order they happen. Hypotheses are recorded as supported / not supported / inconclusive only after the main runs, under the rules fixed in `hypotheses.md`.

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

### Attempt 2: not yet run

No attempt-2 result exists. Results will be added here only from the attempt-2 output files in `results/`, with the file name and condition cited.
