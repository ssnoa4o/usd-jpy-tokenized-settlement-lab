# Hypotheses (draft)

Hypotheses are things to test, not conclusions. Each result is recorded as supported / not supported / inconclusive.

Status: Day 4 draft, 2026-11-02. No experiment has been run. The decision rules below are fixed before any experiment.

This is an independent research prototype on synthetic data. No institution (BIS, BoJ, CLS, OSFI or any other) has reviewed, approved or endorsed it. Source IDs refer to `sources.md`.

This file holds the claims and decision rules. Definitions of metrics, design values **(DV)**, experiment levels, required tests and limits are in `methodology.md` ("M" below, with section numbers).

## 1. Common decision rule

- **Inputs.** 30 seeds (DV) per condition and common random numbers (M sec. 6, 7).
- **Reported per condition and model:** mean and per-seed range [min, max]. For each comparison we also report the **per-seed paired difference** (model Y minus model X, same seed).
- **Claim at one level** (a "level" is one pre-listed condition, such as one failure probability). For a directional claim "X lower than Y":

| Outcome | Rule (checked in this order) |
|---|---|
| Not supported | (1) Values are identical across the two models in every seed ("no difference"; noted explicitly), OR the paired difference has the opposite sign in every seed. |
| Supported | (2) The paired difference has the predicted sign in every seed, and its mean is not 0. |
| Inconclusive | (3) Otherwise (mixed signs, or some seeds with no difference). |

- **Why paired.** Models share transactions and failure draws within a seed, so the paired rule decides model comparisons. Non-overlapping ranges are a stronger result and are noted, but overlapping ranges do not by themselves make the verdict Inconclusive.
- **Same model across conditions** (H3: factor levels use different transactions). The range rule decides instead: Supported if ranges do not overlap (touching counts as overlapping), Not supported if identical in every seed, Inconclusive otherwise.
- **Non-directional claims** ("differs") are Supported if the paired difference has the same non-zero sign in every seed (the direction is then reported); there is no "opposite" case.
- **Several levels.** The claim is stated per level. Overall: Supported only if every pre-listed level is Supported; Not supported only if every level is Not supported; otherwise Inconclusive (mixed, or any level Inconclusive). A level-by-level table goes into `findings.md` later. H4 uses its own rule (below).
- **Guaranteed by design is not evidence.** Outcomes that follow from the model rules are Required tests (M sec. 7) and are not part of any decision.
- **One primary metric and comparison per hypothesis** (named below, fixed now). Everything else is exploratory: descriptive, not decisive.

## H1. Principal exposure

**Statement.** Part of H1 is true by design: Model C commits both legs or neither (Required tests). The testable questions are how A's and B's exposure respond to failures, and when B differs from A. OSFI says PvP arrangements "are designed to eliminate principal risk, but will not eliminate a bank's replacement cost risk or liquidity risk" (OSFI-1, sec. 2.1). We read this as a reason to report liquidity and failure metrics beside exposure; that reading is ours.

**Primary metric.** Principal Exposure, amount-based (M sec. 5).

- **H1a (descriptive, no verdict).** That Principal Exposure in A and B does not fall as Failure Probability rises is guaranteed by the injection rule, so it is a Required test. We report its size (mean and range per level). Exp4, failure levels.
- **H1b.** B has lower Principal Exposure than A under liquidity stress, where A can leave `partial` after a second-leg `insufficient_funds` and B cannot. Exp3, every level below the reference. A and B are identical at ample liquidity by construction, so Exp4 is not a test of this.
  - Levels counted: only "active" levels, where A has at least one `partial` with reason `insufficient_funds` in **every** seed. A first-leg shortage gives `failed` and no exposure, so it does not count. Other levels are reported as not informative and are not counted. If no level is active, H1b is Inconclusive (untestable under the chosen grid).
  - B cannot have this kind of `partial` by design, so the direction is largely design-driven. The result is reported with its size and read as a measure of how much this mechanism matters, not as independent evidence.
  - Supported if B is lower (paired rule) at every active level.
  - Not supported if at every active level A and B are identical or B is higher (B's reservation then adds nothing to A in our model).
  - Inconclusive if otherwise.

**Exploratory.** C vs A and B on Failure Rate under liquidity stress (at ample liquidity the difference only restates that an injected failure is `partial` in A and B and `failed` in C); duration-weighted exposure. Average Settlement Time is equal across the models by construction (M sec. 5), so it is reported but is not evidence of a speed difference.

## H2. Liquidity and funding requirement

**Statement.** Part of the funding comparison follows from the definitions (M sec. 5): B is expected to have a Peak Liquidity Proxy at least equal to A's, and Liquidity Utilization is close to a success ratio. Both are descriptive only. B reserves the JPY leg from arrival while A pays it after the delay, so the claim tested is that **the B minus A gap is larger at a longer delay**. The direction can be anticipated from the reservation rule, so the size of the gap is reported as the main information.

**Primary metric and comparison.** Peak Liquidity Proxy, gap = B minus A in the same seed. Compared within each seed: gap at delay 300 s minus gap at delay 0 s (DV), ample liquidity, failure 1% (DV), Exp4 delay levels. Transactions and failure draws are the same across these levels, so the paired rule applies.
- Supported if this difference is positive in every seed and its mean is not 0.
- Not supported if it is 0 in every seed, or negative in every seed.
- Inconclusive if otherwise.

**Exploratory.** C vs A proxy (at ample liquidity and constant delay, payments only shift in time, so the two can differ only through transactions hit by an injected failure; close to equal by construction, M sec. 5); B vs A proxy by volume (Exp2); B vs C Gross Prefunding and Liquidity Utilization; **liquidity grid (Exp3):** how Gross Prefunding and Peak Liquidity Proxy change as initial liquidity falls, per model. This sub-comparison matches the "as initial liquidity changes" wording in `research_question.md`, but it is descriptive, not decisive.

## H3. Scale, participants and arrival pattern

**Statement.** The relation between funding demand and success rate is made concrete as **L\*** (M sec. 5). The claim: L\* differs between factor levels.

**Primary metric.** L\*. **Primary comparison.** For each factor separately (volume, banks, arrival), L\* at the highest vs the lowest level of Exp2 (burst vs sequential for arrival), other factors at baseline, non-directional.
- Verdicts are given separately for each model and each factor (up to 9 verdicts); there is no pooled H3 verdict, and "any one factor" is not enough.
  - Supported if, for that model and factor, the L\* ranges at the two levels do not overlap.
  - Not supported if L\* is identical in every seed at both levels.
  - Inconclusive if otherwise (overlapping or touching ranges).
- If L\* sits at the edge of the grid (lowest level, or "not reached") at either level in any seed, that result is censored: the true value may lie beyond the grid. A censored comparison is Inconclusive, never Not supported.
- A difference that vanishes with a finer grid is reported as grid-dependent (M sec. 9).

**Exploratory.** Peak Liquidity Proxy and Success Rate by factor; middle factor levels.

## H4. Stress affects models differently

"Change" = stress minus baseline, per seed. Differences that follow only from C having no partial state (C partial = 0, C exposure = 0, the partial/failed split of an injected failure) are excluded from decisions. A difference that appears only in definitional metrics does not count.

- **H4a. Liquidity stress.** Primary metric: change in Success Rate (it counts only `settled`, so it does not depend on the partial/failed split). Primary comparison: A vs C (other pairs exploratory). Exp3; baseline is the reference level, stress is every lower level.
  - Supported if at the lowest grid level (highest stress) the paired difference of the change (A minus C) has the same sign in every seed and a non-zero mean, AND at every other stress level the mean paired difference is not of the opposite sign (a mean of exactly 0 is not a reversal).
  - Not supported if at the highest stress the change is identical for A and C in every seed (no difference).
  - Inconclusive if otherwise (mixed signs at the highest stress, or a reversal at a milder level).
- **H4b. Delay stress.** Primary metric: change in amount-based Principal Exposure. Primary comparison: A vs B (C is 0 by design). Because A and B are identical at ample liquidity, this runs in the H4b cells of Exp4, with baseline delay 0 s (DV) and 300 s (DV) as the highest level. Verdict by the same rule as H4a, read with 300 s as the highest stress and 60 s as the other stress level.
  - This check comes first: H4b is informative only if A has a `partial` with reason `insufficient_funds` in some seed in those cells; otherwise it is reported as untestable (Inconclusive), before the verdict rule is applied. "Some seed" is enough here because the paired rule then requires a consistent sign across all seeds; H1b's stricter "every seed" keeps levels where the rule could never be met out of its all-levels verdict.
  - Delay affects this metric only through balances (M sec. 9), so H4b may show little or no difference.
  - Duration-weighted exposure is reported beside it as a descriptive value with W stated. It is not used for the verdict, because every `partial` contributes W regardless of delay (M sec. 5).

H4 is the exception to the all-levels aggregation: the highest level decides, milder levels check direction consistency. Exploratory: Failure Rate by reason, Partial Settlement Rate, other model pairs.

## 2. Not yet decided

The liquidity levels are set by the calibration in M sec. 6 before the main runs. Other open items are listed in M sec. 11.
