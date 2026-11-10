"""Verdicts for H1a, H1b, H2, H4a and H4b (Day 12). Decision rules are from research/hypotheses.md.

Run with: python -m src.verdicts [--force]
Input:  results/stress_run_metrics.csv (only this file)
Output: results/verdicts.csv (never overwritten without --force)

The rules were fixed before any main run and are coded literally. Nothing here decides
what the result "means"; it only labels each claim supported / not supported / inconclusive.

Columns of verdicts.csv:
  hypothesis, level, role, verdict, n_seeds, n_pos, n_neg, n_zero, mean_diff, note,
  model, value_mean, value_min, value_max  (used by the H1a descriptive rows)
  git_commit, seeds  (provenance, taken from the input rows; same value in every row)
Roles: decides (counts toward the verdict), direction_check (milder level of H4),
active_check (is the hypothesis testable at all), descriptive (no verdict), overall.
The verdict is empty for descriptive rows and for checks that passed.

Float handling. Metric values are sums of cents or ratios n / 500. Paired differences are
rounded to 4 decimals before the sign is taken (CLEAN_DIGITS). The smallest real USD
difference is 0.01 and the smallest real rate difference is 1/500 = 0.002, so rounding at
4 decimals only removes floating-point noise (about 1e-7 for values near 1e8) and never a
real difference. After that, "identical" means exactly 0. Means are never compared as floats: the sign of a mean
(zero or not) is decided from the exact integer sum of the differences in units of 10^-4
(mean_sign), because a float mean of values that sum to zero is often about 1e-18, not 0.

Ambiguities in hypotheses.md that this code resolves in a stated way are marked "READING".
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
STRESS_RUN_METRICS_FILE = "stress_run_metrics.csv"
VERDICTS_FILE = "verdicts.csv"
COLUMNS = ["hypothesis", "level", "role", "verdict", "n_seeds", "n_pos", "n_neg", "n_zero",
           "mean_diff", "note", "model", "value_mean", "value_min", "value_max", "git_commit", "seeds"]  # fmt: skip

SUPPORTED = "supported"
NOT_SUPPORTED = "not supported"
INCONCLUSIVE = "inconclusive"
VERDICTS = (SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE)

CLEAN_DIGITS = 4
A, B, C = "sequential", "prefunded", "atomic"
FAILURE_PROBABILITY = 0.01
H2_DELAYS = (0, 60, 300)  # 0 and 300 decide; 60 is descriptive (cell shared with exp4_failure)


# ------------------------------------------------------------------ paired rule

def clean(values: Sequence[float]) -> list[float]:
    """Round differences to CLEAN_DIGITS decimals (removes float noise, see module docstring)."""
    return [round(float(v), CLEAN_DIGITS) + 0.0 for v in values]  # + 0.0 turns -0.0 into 0.0


def sign_counts(diffs: Sequence[float]) -> tuple[int, int, int]:
    """Return (n_pos, n_neg, n_zero) of the (already cleaned) differences."""
    return (sum(d > 0 for d in diffs), sum(d < 0 for d in diffs), sum(d == 0 for d in diffs))


def units(diffs: Sequence[float]) -> list[int]:
    """Cleaned differences as integers in units of 10^-CLEAN_DIGITS (exact integer arithmetic)."""
    return [round(d * 10**CLEAN_DIGITS) for d in diffs]


def mean_sign(diffs: Sequence[float]) -> int:
    """Sign (+1, 0, -1) of the mean, decided from the exact integer sum of the units.

    A float mean of values that sum to zero is often not exactly 0 (e.g. 0.1 + 0.2 - 0.3),
    so every "mean is not 0" / "mean has the opposite sign" test uses this function.
    """
    total = sum(units(diffs))
    return (total > 0) - (total < 0)


def mean_of(diffs: Sequence[float]) -> float:
    """Mean of the differences, for reporting: integer sum / n, rounded to CLEAN_DIGITS.

    NaN for an empty list. An exactly-zero mean is returned as 0.0 (never -0.0 or 1e-18).
    """
    if len(diffs) == 0:
        return float("nan")
    return round(sum(units(diffs)) / len(diffs) / 10**CLEAN_DIGITS, CLEAN_DIGITS) + 0.0


def paired_verdict(diffs: Sequence[float], predicted_sign: int | None) -> str:
    """Common decision rule, hypotheses.md sec. 1 (differences must be cleaned already).

    Directional claim "X lower than Y" (diff = Y minus X, predicted_sign +1; -1 if the
    prediction is a negative difference), checked in this order:
      Not supported: "(1) Values are identical across the two models in every seed ... OR the
                      paired difference has the opposite sign in every seed."
      Supported:     "(2) The paired difference has the predicted sign in every seed, and its
                      mean is not 0."
      Inconclusive:  "(3) Otherwise (mixed signs, or some seeds with no difference)."
    Non-directional claim (predicted_sign None): "Supported if the paired difference has the
    same non-zero sign in every seed ... there is no 'opposite' case."
    READING: for a non-directional claim, all differences 0 is still "no difference" and is
    Not supported (rule (1) first half); everything else that is not Supported is Inconclusive.
    No seeds at all is Inconclusive.
    """
    n_pos, n_neg, n_zero = sign_counts(diffs)
    n = len(diffs)  # (mean_sign != 0 below is redundant in practice: same-sign non-zero diffs have a non-zero sum; kept to mirror hypotheses.md)
    if n == 0:
        return INCONCLUSIVE
    if n_zero == n:
        return NOT_SUPPORTED
    if predicted_sign is None:
        return SUPPORTED if (n_pos == n or n_neg == n) and mean_sign(diffs) != 0 else INCONCLUSIVE
    opposite_in_every_seed = (n_neg == n) if predicted_sign > 0 else (n_pos == n)
    if opposite_in_every_seed:
        return NOT_SUPPORTED
    predicted_in_every_seed = (n_pos == n) if predicted_sign > 0 else (n_neg == n)
    if predicted_in_every_seed and mean_sign(diffs) != 0:
        return SUPPORTED
    return INCONCLUSIVE


def h4_verdict(top_diffs: Sequence[float], other_levels: Sequence[Sequence[float]]) -> tuple[str, str]:
    """H4 rule (hypotheses.md H4a; H4b uses the same rule). Returns (verdict, note).

    "Supported if at the lowest grid level (highest stress) the paired difference of the
    change (A minus C) has the same sign in every seed and a non-zero mean, AND at every
    other stress level the mean paired difference is not of the opposite sign (a mean of
    exactly 0 is not a reversal). Not supported if at the highest stress the change is
    identical for A and C in every seed (no difference). Inconclusive if otherwise (mixed
    signs at the highest stress, or a reversal at a milder level)."
    The claim is non-directional, so the sign of the highest level is reported in the note.
    """
    top = paired_verdict(top_diffs, None)
    if top == NOT_SUPPORTED:
        return NOT_SUPPORTED, "no difference at the highest stress in every seed"
    if top == INCONCLUSIVE:
        return INCONCLUSIVE, "mixed signs (or no seeds) at the highest stress"
    sign = mean_sign(top_diffs)
    direction = "positive" if sign > 0 else "negative"
    for diffs in other_levels:
        mean = mean_sign(diffs)
        if mean != 0 and mean != sign:
            return INCONCLUSIVE, f"highest stress {direction} in every seed, but a milder level has the opposite mean sign (reversal)"
    return SUPPORTED, f"{direction} difference in every seed at the highest stress; no reversal at milder levels"


# ------------------------------------------------------------------ table helpers

def select_cell(runs: pd.DataFrame, experiment: str, *, failure: float | None = None,
                delay: float | None = None, multiplier: float | None = None) -> pd.DataFrame:
    """Rows of one cell: an experiment plus optional failure, delay and JPY multiplier filters."""
    cell = runs[runs["experiment"] == experiment]
    if failure is not None:
        cell = cell[cell["failure_probability"] == failure]
    if delay is not None:
        cell = cell[cell["delay_seconds"] == delay]
    if multiplier is not None:
        cell = cell[cell["jpy_multiplier"] == multiplier]
    return cell


def by_seed(cell: pd.DataFrame, model: str, column: str) -> pd.Series:
    """One model's metric per seed, indexed by seed and sorted. Needs one row per seed."""
    part = cell[cell["model"] == model]
    if part["seed"].duplicated().any():
        raise ValueError("cell has more than one row per seed (selection too wide)")
    return part.set_index("seed")[column].astype(float).sort_index()


def paired(first: pd.Series, second: pd.Series) -> list[float]:
    """Per-seed first minus second, cleaned. ValueError if the two have different seeds."""
    if not first.index.equals(second.index):
        raise ValueError("the two series do not have the same seeds")
    return clean((first - second).tolist())


def delay_cell(runs: pd.DataFrame, delay: float) -> pd.DataFrame:
    """The ample, failure 1%, JPY multiplier 1 cell for one delay (Exp4 delay levels).

    Delay 0 and 300 s are the cells of exp4_delay. Delay 60 s is NOT in exp4_delay: it is the
    cell exp4_failure at failure 1% (shared, not run twice), so it is read from there.
    """
    if delay == 60:
        return select_cell(runs, "exp4_failure", failure=FAILURE_PROBABILITY, delay=60)
    return select_cell(runs, "exp4_delay", failure=FAILURE_PROBABILITY, delay=delay)


def row(hypothesis: str, level: str, role: str, diffs: Sequence[float] | None = None,
        verdict: str = "", note: str = "") -> dict[str, object]:
    """One verdicts.csv row. Sign counts and mean are filled from `diffs` if given."""
    out: dict[str, object] = {c: "" for c in COLUMNS}
    out.update(hypothesis=hypothesis, level=level, role=role, verdict=verdict, note=note)
    if diffs is not None:
        n_pos, n_neg, n_zero = sign_counts(diffs)
        out.update(n_seeds=len(diffs), n_pos=n_pos, n_neg=n_neg, n_zero=n_zero, mean_diff=mean_of(diffs))
    return out


def overall_from_levels(levels: Sequence[str]) -> str:
    """Hypotheses.md sec. 1 'Several levels': Supported only if every level is Supported;
    Not supported only if every level is Not supported; otherwise Inconclusive."""
    if levels and all(v == SUPPORTED for v in levels):
        return SUPPORTED
    if levels and all(v == NOT_SUPPORTED for v in levels):
        return NOT_SUPPORTED
    return INCONCLUSIVE


# ------------------------------------------------------------------ hypotheses

def h1a_rows(runs: pd.DataFrame) -> list[dict[str, object]]:
    """H1a (descriptive, no verdict): A and B principal exposure (USD) at failure 0 / 1 / 5%.

    "That Principal Exposure in A and B does not fall as Failure Probability rises is
    guaranteed by the injection rule, so it is a Required test. We report its size (mean and
    range per level)."
    """
    rows = []
    cells = runs[runs["experiment"] == "exp4_failure"]
    for failure in sorted(cells["failure_probability"].unique()):
        for model in (A, B):
            values = by_seed(select_cell(cells, "exp4_failure", failure=failure), model, "principal_exposure_usd")
            out = row("H1a", f"failure_{failure:g}", "descriptive", note="mean and range of principal_exposure_usd")
            out.update(n_seeds=len(values), model=model, value_mean=values.mean(),
                       value_min=values.min(), value_max=values.max())  # fmt: skip
            rows.append(out)
    rows.append(row("H1a", "overall", "overall", note="descriptive only, no verdict"))
    return rows


def h1b_rows(runs: pd.DataFrame) -> list[dict[str, object]]:
    """H1b: B has lower Principal Exposure than A under liquidity stress (Exp3, levels below 1).

    "Levels counted: only 'active' levels, where A has at least one partial with reason
    insufficient_funds in every seed ... Other levels are reported as not informative and are
    not counted. If no level is active, H1b is Inconclusive (untestable under the chosen grid).
    Supported if B is lower (paired rule) at every active level.
    Not supported if at every active level A and B are identical or B is higher.
    Inconclusive if otherwise."
    Diff = A minus B (B lower = positive diff, predicted sign +1).
    READING: the overall "Not supported" needs B >= A in every seed at every active level
    (identical or higher, seed by seed). A level with a mix of zero and B-higher seeds is
    Inconclusive in the level row (paired rule) but counts as "identical or higher" here.
    """
    exp3 = runs[runs["experiment"] == "exp3_liquidity"]
    lower = sorted((m for m in exp3["jpy_multiplier"].unique() if m < 1.0), reverse=True)
    rows = []
    active_diffs: list[list[float]] = []
    for multiplier in lower:
        cell = select_cell(exp3, "exp3_liquidity", multiplier=multiplier)
        partial = by_seed(cell, A, "n_partial_insufficient_funds")
        n_with = int((partial >= 1).sum())
        active = n_with == len(partial) and len(partial) > 0
        diffs = paired(by_seed(cell, A, "principal_exposure_usd"), by_seed(cell, B, "principal_exposure_usd"))
        level = f"jpy_{multiplier:g}"
        if active:
            active_diffs.append(diffs)
            rows.append(row("H1b", level, "decides", diffs, paired_verdict(diffs, +1),
                            f"active: A partial with insufficient_funds in {n_with}/{len(partial)} seeds; diff = A minus B"))
        else:
            rows.append(row("H1b", level, "descriptive", diffs, "",
                            f"not informative: A partial with insufficient_funds in only {n_with}/{len(partial)} seeds; not counted"))
    if not active_diffs:
        rows.append(row("H1b", "overall", "overall", verdict=INCONCLUSIVE, note="untestable under the chosen grid (no active level)"))
        return rows
    level_verdicts = [paired_verdict(d, +1) for d in active_diffs]
    if all(v == SUPPORTED for v in level_verdicts):
        verdict = SUPPORTED
    elif all(all(x <= 0 for x in d) for d in active_diffs):  # B >= A in every seed at every active level
        verdict = NOT_SUPPORTED
    else:
        verdict = INCONCLUSIVE
    rows.append(row("H1b", "overall", "overall", verdict=verdict, note=f"{len(active_diffs)} active level(s) of {len(lower)}"))
    return rows


def h2_rows(runs: pd.DataFrame) -> list[dict[str, object]]:
    """H2: the B minus A gap in Peak Liquidity Proxy is larger at a longer delay.

    "gap = B minus A in the same seed. Compared within each seed: gap at delay 300 s minus gap
    at delay 0 s, ample liquidity, failure 1%, Exp4 delay levels.
    Supported if this difference is positive in every seed and its mean is not 0.
    Not supported if it is 0 in every seed, or negative in every seed.
    Inconclusive if otherwise."
    Also reports the mean gap at 0, 60 and 300 s (descriptive; the 60 s cell is shared with
    exp4_failure, see delay_cell).
    """
    gaps: dict[int, pd.Series] = {}
    rows = []
    for delay in H2_DELAYS:
        cell = delay_cell(runs, delay)
        gaps[delay] = by_seed(cell, B, "peak_liquidity_proxy_usd") - by_seed(cell, A, "peak_liquidity_proxy_usd")
        rows.append(row("H2", f"gap_delay_{delay}", "descriptive", clean(gaps[delay].tolist()),
                        note="B minus A peak_liquidity_proxy_usd (mean_diff = mean gap)"))
    diffs = paired(gaps[300], gaps[0])
    verdict = paired_verdict(diffs, +1)
    rows.append(row("H2", "gap300_minus_gap0", "decides", diffs, verdict, "ample, failure 1%"))
    rows.append(row("H2", "overall", "overall", diffs, verdict, "single comparison"))
    return rows


def h4a_rows(runs: pd.DataFrame) -> list[dict[str, object]]:
    """H4a: liquidity stress affects A and C differently (Exp3, primary metric Success Rate).

    Change = success_rate(level) minus success_rate(multiplier 1) per seed and model; the
    paired difference is change_A minus change_C. Highest stress = lowest multiplier.
    The rule is h4_verdict (quoted there).
    """
    exp3 = runs[runs["experiment"] == "exp3_liquidity"]
    base = select_cell(exp3, "exp3_liquidity", multiplier=1.0)
    lower = sorted((m for m in exp3["jpy_multiplier"].unique() if m < 1.0), reverse=True)
    if not lower or base.empty:
        return [row("H4a", "overall", "overall", verdict=INCONCLUSIVE, note="no stress levels in the input")]
    diffs_by_level = {}
    for multiplier in lower:
        cell = select_cell(exp3, "exp3_liquidity", multiplier=multiplier)
        change_a = by_seed(cell, A, "success_rate") - by_seed(base, A, "success_rate")
        change_c = by_seed(cell, C, "success_rate") - by_seed(base, C, "success_rate")
        diffs_by_level[multiplier] = paired(change_a, change_c)
    return h4_rows("H4a", diffs_by_level, "change_A minus change_C of success_rate")


def h4b_rows(runs: pd.DataFrame) -> list[dict[str, object]]:
    """H4b: delay stress affects A and B differently (H4b cells, primary metric principal exposure).

    "This check comes first: H4b is informative only if A has a partial with reason
    insufficient_funds in some seed in those cells; otherwise it is reported as untestable
    (Inconclusive), before the verdict rule is applied."
    Change = exposure(delay) minus exposure(delay 0) per seed and model; the paired
    difference is change_A minus change_B. 300 s is the highest stress, 60 s the other level.
    """
    cells = runs[runs["experiment"] == "exp4_h4b"]
    if cells.empty:
        return [row("H4b", "overall", "overall", verdict=INCONCLUSIVE, note="untestable: no H4b cells in the input")]
    a_cells = cells[cells["model"] == A]
    n_with = int((a_cells["n_partial_insufficient_funds"] >= 1).sum())
    testable = n_with >= 1
    rows = [row("H4b", "h4b_cells", "active_check", verdict="" if testable else INCONCLUSIVE,
                note=f"A rows with partial insufficient_funds in the H4b cells: {n_with} of {len(a_cells)} (any delay, any seed needed)")]
    base = select_cell(cells, "exp4_h4b", delay=0)
    diffs_by_delay = {}
    for delay in (300, 60):
        cell = select_cell(cells, "exp4_h4b", delay=delay)
        change_a = by_seed(cell, A, "principal_exposure_usd") - by_seed(base, A, "principal_exposure_usd")
        change_b = by_seed(cell, B, "principal_exposure_usd") - by_seed(base, B, "principal_exposure_usd")
        diffs_by_delay[delay] = paired(change_a, change_b)
    if not testable:
        for delay, diffs in diffs_by_delay.items():
            rows.append(row("H4b", f"delay_{delay}", "descriptive", diffs, "", "not used: H4b untestable"))
        rows.append(row("H4b", "overall", "overall", verdict=INCONCLUSIVE, note="untestable: no partial with insufficient_funds in any H4b cell"))
        return rows
    verdict, note = h4_verdict(diffs_by_delay[300], [diffs_by_delay[60]])
    rows.append(row("H4b", "delay_300", "decides", diffs_by_delay[300], paired_verdict(diffs_by_delay[300], None),
                    "highest stress alone (change_A minus change_B of principal_exposure_usd); verdict is in the overall row"))
    rows.append(row("H4b", "delay_60", "direction_check", diffs_by_delay[60], "", direction_note(diffs_by_delay[300], diffs_by_delay[60])))
    rows.append(row("H4b", "overall", "overall", diffs_by_delay[300], verdict, note))
    return rows


def direction_note(top_diffs: Sequence[float], diffs: Sequence[float]) -> str:
    """Words for a direction check: does the mean of this level reverse the highest level's sign?"""
    top_mean, mean = mean_sign(top_diffs), mean_sign(diffs)
    if mean == 0:
        return "mean exactly 0: not a reversal"
    if top_mean != 0 and mean != top_mean:
        return "mean has the opposite sign of the highest stress: reversal"
    return "mean has the same sign as the highest stress (or the highest stress mean is 0): no reversal"


def h4_rows(hypothesis: str, diffs_by_level: dict[float, list[float]], what: str) -> list[dict[str, object]]:
    """Rows of an H4a-style hypothesis: lowest multiplier decides, other levels check direction."""
    top_level = min(diffs_by_level)
    top = diffs_by_level[top_level]
    others = {m: d for m, d in diffs_by_level.items() if m != top_level}
    verdict, note = h4_verdict(top, list(others.values()))
    rows = []
    for multiplier in sorted(others, reverse=True):
        rows.append(row(hypothesis, f"jpy_{multiplier:g}", "direction_check", others[multiplier], "",
                        direction_note(top, others[multiplier])))
    rows.append(row(hypothesis, f"jpy_{top_level:g}", "decides", top, paired_verdict(top, None),
                    f"highest stress alone ({what}); verdict is in the overall row"))
    rows.append(row(hypothesis, "overall", "overall", top, verdict, note))
    return rows


# ------------------------------------------------------------------ build and CLI

AMPLE_WITHHELD_NOTE = "ample violated: verdict withheld (methodology sec. 6)"
# Methodology sec. 6: if "ample" does not hold, the reference must be raised and the runs repeated
# "before any verdict is computed". The reference is then invalid for every grid level and for the
# H4b level too, so ALL hypotheses are withheld, not only those that read ample cells directly.
AMPLE_DEPENDENT = ("H1a", "H1b", "H2", "H4a", "H4b")
MAIN_SEEDS = list(range(1, 31))


def seeds_text(seeds: Sequence[int]) -> str:
    """'1-30' for consecutive seeds, otherwise a comma list."""
    ordered = sorted(int(x) for x in seeds)
    if ordered and ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{ordered[0]}-{ordered[-1]}"
    return ",".join(str(x) for x in ordered)


def ample_violations(runs: pd.DataFrame) -> pd.DataFrame:
    """Rows of ample cells with insufficient_funds > 0. ValueError if a needed column is missing."""
    for column in ("ample_cell", "n_insufficient_funds"):
        if column not in runs.columns:
            raise ValueError(f"input has no column {column!r}; cannot check the ample reference")
    ample = runs["ample_cell"].astype(str) == "True"
    return runs[ample & (runs["n_insufficient_funds"] > 0)]


def build_verdicts(runs: pd.DataFrame) -> pd.DataFrame:
    """All verdict rows (H1a, H1b, H2, H4a, H4b) from the stress_run_metrics table.

    Provenance: git_commit and seeds are copied from the input into every row. ValueError if
    the input has more than one git_commit. A warning row is added if the seeds are not 1-30.
    Ample check: if any ample cell has insufficient_funds > 0, NO hypothesis gets a verdict
    (blank verdict, note AMPLE_WITHHELD_NOTE), a warning is printed and an `ample_check` row is
    added. Reason (methodology sec. 6): the reference must be raised and the runs repeated before
    any verdict is computed; it is invalid for every grid level and for the H4b level too.
    A git_commit ending in "-dirty" gives a warning and a note in the input_check row.
    """
    commits = sorted(runs["git_commit"].astype(str).unique()) if "git_commit" in runs.columns else [""]
    if len(commits) > 1:
        raise ValueError(f"input has more than one git_commit: {commits}")
    seeds = sorted(runs["seed"].unique())
    rows = h1a_rows(runs) + h1b_rows(runs) + h2_rows(runs) + h4a_rows(runs) + h4b_rows(runs)
    violated = ample_violations(runs)
    if len(violated) > 0:
        print(f"WARNING: ample violated in {len(violated)} run(s); all verdicts withheld (methodology sec. 6).")
        for r in rows:
            if r["hypothesis"] in AMPLE_DEPENDENT and (r["verdict"] != "" or r["role"] == "overall"):
                r["verdict"], r["note"] = "", AMPLE_WITHHELD_NOTE
        cells = sorted(set(violated["experiment"] + "/" + violated["condition"]))
        rows.append(row("ample_check", "all ample cells", "active_check", note=f"ample violated in {len(violated)} run(s): {', '.join(cells)}"))
        rows[-1]["n_seeds"] = int(violated["seed"].nunique())
    if seeds != MAIN_SEEDS:
        print(f"WARNING: input seeds are {seeds_text(seeds)}, not exactly 1-30. Not the main run.")
        rows.append(row("input_check", "seeds", "active_check", note=f"WARNING: seeds are {seeds_text(seeds)}, not exactly 1-30 (not the main run)"))
    else:
        rows.append(row("input_check", "seeds", "active_check", note="seeds are exactly 1-30"))
    if commits[0].endswith("-dirty"):
        print(f"WARNING: input git_commit {commits[0]} is dirty (uncommitted changes). Not a clean main run.")
        rows[-1]["note"] += f"; WARNING: git_commit {commits[0]} is dirty"
    for r in rows:
        r["git_commit"], r["seeds"] = commits[0], seeds_text(seeds)
    return pd.DataFrame(rows, columns=COLUMNS)


def main(results_dir: Path = RESULTS_DIR, force: bool = False) -> pd.DataFrame:
    """Read stress_run_metrics.csv, write verdicts.csv. FileExistsError if it exists without force."""
    source = results_dir / STRESS_RUN_METRICS_FILE
    target = results_dir / VERDICTS_FILE
    if target.exists() and not force:
        raise FileExistsError(f"Output already exists: {target}. Use --force to overwrite.")
    if not source.exists():
        raise ValueError(f"{source} not found. Run `python -m src.experiments stress` first.")
    table = build_verdicts(pd.read_csv(source))
    table.to_csv(target, index=False)
    overall = table[table["role"] == "overall"]
    for _, line in overall.iterrows():
        print(f"{line['hypothesis']}: {line['verdict'] or '(descriptive)'}  {line['note']}")
    print(f"Wrote {target}")
    return table


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line entry point. Returns the exit code (0 = ok, 1 = refused)."""
    parser = argparse.ArgumentParser(description="Compute hypothesis verdicts from the stress runs.")
    parser.add_argument("--force", action="store_true", help="overwrite results/verdicts.csv")
    args = parser.parse_args(argv)
    try:
        main(force=args.force)
    except (FileExistsError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
