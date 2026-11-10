"""Tests for src/calibration.py. Fake count tables only; tiny runs use seeds 201-205."""

import pandas as pd

from src import calibration as cal
from src.calibration import FUNDS, PARTIAL_FUNDS
from src.simulator import Model

A = str(Model.SEQUENTIAL)
SEEDS = list(cal.CALIBRATION_SEEDS)


def ample_table(shortage: bool = False, model: str = A, seed: int = 101) -> pd.DataFrame:
    """Small fake ample table; optionally one shortage in one row."""
    rows = [
        {"model": m, "seed": s, "condition": c, FUNDS: 0}
        for m in ("sequential", "prefunded", "atomic")
        for s in (101, 102)
        for c in ("baseline", "delay_300")
    ]
    if shortage:
        for r in rows:
            if r["model"] == model and r["seed"] == seed and r["condition"] == "delay_300":
                r[FUNDS] = 1
    return pd.DataFrame(rows)


def grid_rows(level_seeds: dict[float, int], delay: float = 60) -> pd.DataFrame:
    """Model A rows: at each multiplier, the first n seeds have a funds-partial."""
    rows = []
    for multiplier, n in level_seeds.items():
        for i, seed in enumerate(SEEDS):
            rows.append({
                "model": A, "seed": seed, "multiplier": multiplier,
                "delay_seconds": delay, PARTIAL_FUNDS: 1 if i < n else 0,
            })  # fmt: skip
    return pd.DataFrame(rows)


def test_constants_and_conditions():
    assert list(cal.CALIBRATION_SEEDS) == list(range(101, 111))
    assert cal.FAILURE_PROBABILITY == 0.0
    names = [c.name for c in cal.AMPLE_CONDITIONS]
    assert names == [
        "baseline", "count_100", "count_1000", "banks_5", "banks_10",
        "arrival_burst", "delay_0", "delay_300",
    ]  # fmt: skip
    assert cal.MODELS == (Model.SEQUENTIAL, Model.PREFUNDED, Model.ATOMIC)
    assert cal.seeds_label(SEEDS) == "101-110"


def test_is_ample_requires_zero_shortages_everywhere():
    assert cal.is_ample(ample_table())
    for model in ("sequential", "prefunded", "atomic"):
        assert not cal.is_ample(ample_table(shortage=True, model=model, seed=102))
    assert not cal.is_ample(pd.DataFrame(columns=[FUNDS]))


def test_doubling_stops_at_first_ample_level():
    calls = []

    def fn(d: int) -> pd.DataFrame:
        calls.append(d)
        return ample_table(shortage=d < 2)

    doublings, tables = cal.find_ample_doubling(fn)
    assert doublings == 2
    assert calls == [0, 1, 2]
    assert len(tables) == 3


def test_doubling_limit_of_five():
    calls = []

    def fn(d: int) -> pd.DataFrame:
        calls.append(d)
        return ample_table(shortage=True)

    doublings, _ = cal.find_ample_doubling(fn)
    assert doublings is None
    assert calls == [0, 1, 2, 3, 4, 5]  # start + 5 doublings


def test_ample_at_five_doublings_is_accepted():
    doublings, _ = cal.find_ample_doubling(lambda d: ample_table(shortage=d < 5))
    assert doublings == 5


def test_exactly_two_qualifying_levels_passes_one_fails():
    lower = (0.75, 0.5, 0.25, 0.1)
    two = grid_rows({0.75: 0, 0.5: 0, 0.25: 10, 0.1: 10})
    one = grid_rows({0.75: 0, 0.5: 0, 0.25: 0, 0.1: 10})
    assert cal.qualifying_lower_levels(two, lower, SEEDS) == [0.25, 0.1]
    assert cal.qualifying_lower_levels(one, lower, SEEDS) == [0.1]
    assert len(cal.qualifying_lower_levels(two, lower, SEEDS)) >= cal.MIN_SHORT_LEVELS
    assert len(cal.qualifying_lower_levels(one, lower, SEEDS)) < cal.MIN_SHORT_LEVELS


def test_one_seed_without_shortage_disqualifies_level():
    table = grid_rows({0.5: 9, 0.25: 10})
    assert cal.qualifying_lower_levels(table, (0.5, 0.25), SEEDS) == [0.25]


def test_missing_seed_does_not_qualify():
    table = grid_rows({0.5: 10})
    table = table[table["seed"] != 110]
    assert cal.qualifying_lower_levels(table, (0.5,), SEEDS) == []


def test_halving_sequence():
    assert cal.halve((0.75, 0.5, 0.25, 0.1)) == (0.375, 0.25, 0.125, 0.05)


def fake_grid_fn(good_after: int):
    """Grid fake: levels qualify only once the multipliers were halved `good_after` times."""
    seen = []

    def fn(multipliers: tuple[float, ...], attempt: int) -> pd.DataFrame:
        assert attempt == len(seen)
        seen.append(multipliers)
        halvings = len(seen) - 1
        n = 10 if halvings >= good_after else 0
        return grid_rows({m: n for m in multipliers})

    return fn, seen


def test_grid_halves_until_two_levels_qualify():
    fn, seen = fake_grid_fn(good_after=1)
    final, halvings, levels, _ = cal.find_grid(fn, SEEDS)
    assert halvings == 1
    assert final == (0.375, 0.25, 0.125, 0.05)
    assert seen[0] == (0.75, 0.5, 0.25, 0.1)
    assert levels == list(final)


def test_grid_halving_limit_of_three():
    fn, seen = fake_grid_fn(good_after=99)
    final, halvings, levels, _ = cal.find_grid(fn, SEEDS)
    assert levels is None
    assert halvings == 3
    assert len(seen) == 4  # initial check + 3 halvings
    assert final == tuple(m / 8 for m in cal.LOWER_MULTIPLIERS)


def test_grid_succeeds_at_third_halving():
    fn, _ = fake_grid_fn(good_after=3)
    _, halvings, levels, _ = cal.find_grid(fn, SEEDS)
    assert halvings == 3
    assert levels is not None


def h4b_table(spec: dict[float, tuple[int, int, int]]) -> pd.DataFrame:
    """spec: multiplier -> number of seeds with a shortage at delays (0, 60, 300)."""
    parts = [
        grid_rows({m: n}, delay=d) for m, ns in spec.items() for d, n in zip(cal.H4B_DELAYS, ns)
    ]
    return pd.concat(parts, ignore_index=True)


def test_h4b_five_of_ten_qualifies_four_does_not():
    grid = (1.0, 0.5)
    assert cal.h4b_level(h4b_table({1.0: (0, 0, 0), 0.5: (5, 5, 5)}), grid, SEEDS) == 0.5
    assert cal.h4b_level(h4b_table({1.0: (0, 0, 0), 0.5: (5, 5, 4)}), grid, SEEDS) is None


def test_h4b_must_hold_at_all_three_delays():
    grid = (1.0, 0.5)
    for ns in [(0, 10, 10), (10, 0, 10), (10, 10, 0)]:
        assert cal.h4b_level(h4b_table({1.0: (0, 0, 0), 0.5: ns}), grid, SEEDS) is None


def test_h4b_picks_highest_qualifying_level():
    grid = (1.0, 0.75, 0.5, 0.25)
    spec = {1.0: (0, 0, 0), 0.75: (3, 9, 9), 0.5: (6, 6, 6), 0.25: (10, 10, 10)}
    assert cal.h4b_level(h4b_table(spec), grid, SEEDS) == 0.5


def test_h4b_reference_level_can_qualify_in_principle():
    grid = (1.0, 0.5)
    assert cal.h4b_level(h4b_table({1.0: (10, 10, 10), 0.5: (10, 10, 10)}), grid, SEEDS) == 1.0


def test_h4b_none_is_untestable():
    grid = (1.0, 0.5)
    assert cal.h4b_level(h4b_table({1.0: (0, 0, 0), 0.5: (0, 0, 0)}), grid, SEEDS) is None


def test_end_to_end_tiny_run_writes_expected_files(tmp_path):
    seeds = [201, 202]
    conditions = [
        cal.Condition("baseline", count=20),
        cal.Condition("delay_300", count=20, delay_seconds=300),
    ]
    row, checks = cal.run_calibration(cal.run_counts, seeds=seeds, conditions=conditions)
    cal.write_outputs(row, checks, tmp_path)

    summary = pd.read_csv(tmp_path / "calibration.csv")
    audit = pd.read_csv(tmp_path / "calibration_checks.csv")
    assert len(summary) == 1
    expected = {
        "reference_usd", "reference_jpy", "doublings_used", "ample_reached",
        "lower_multipliers", "halvings_used", "grid_condition_met",
        "qualifying_lower_levels", "h4b_multiplier", "h4b_testable", "seeds",
        "failure_probability", "git_commit", "run_utc", "status", "failed_condition",
    }  # fmt: skip
    assert expected <= set(summary.columns)
    assert summary.loc[0, "seeds"] == "201-202"
    assert summary.loc[0, "failure_probability"] == 0.0
    assert summary.loc[0, "attempt"] == 2
    assert summary.loc[0, "grid_scaling"] == "jpy_only"
    assert list(audit.columns) == cal.TABLE_COLUMNS
    assert {FUNDS, PARTIAL_FUNDS} <= set(audit.columns)
    assert (audit["seed"].isin(seeds)).all()
    assert len(audit) > 0


def test_runner_failure_is_recorded_not_raised(tmp_path):
    def always_short(condition, model, seed, usd, jpy):
        return {FUNDS: 1, PARTIAL_FUNDS: 1}

    row, checks = cal.run_calibration(always_short, seeds=[201], conditions=[cal.BASELINE])
    assert row["status"] == "failed"
    assert row["ample_reached"] is False
    assert row["doublings_used"] == cal.MAX_DOUBLINGS
    assert len(checks) == 6 * 3  # 6 levels x 3 models x 1 seed x 1 condition
    cal.write_outputs(row, checks, tmp_path)
    assert (tmp_path / "calibration.csv").exists()
    assert not (tmp_path / "experiment_log.csv").exists()


def test_fake_run_full_flow_no_halving_needed(tmp_path):
    """Fake runner: shortage appears only below a liquidity threshold."""

    def fake(condition, model, seed, usd, jpy):
        short = jpy < 4_500_000_000  # reference JPY is 15bn, so 0.25 and 0.1 are short
        return {FUNDS: int(short), PARTIAL_FUNDS: int(short and str(model) == A)}

    row, checks = cal.run_calibration(fake, seeds=[201, 202], conditions=[cal.BASELINE])
    assert row["ample_reached"] is True
    assert row["doublings_used"] == 0
    assert row["halvings_used"] == 0
    assert row["qualifying_lower_levels"] == "0.25 0.1"
    assert row["h4b_testable"] is True
    assert row["h4b_multiplier"] == "0.25"


# ----------------------------------------------------------- review fixes (M2, M3, L1-L3)

import pytest  # noqa: E402

from src import metrics, simulator, transactions  # noqa: E402


def test_condition_fields_are_exact():
    expected = {
        "baseline": (500, 2, "sequential", 60),
        "count_100": (100, 2, "sequential", 60),
        "count_1000": (1000, 2, "sequential", 60),
        "banks_5": (500, 5, "sequential", 60),
        "banks_10": (500, 10, "sequential", 60),
        "arrival_burst": (500, 2, "burst", 60),
        "delay_0": (500, 2, "sequential", 0),
        "delay_300": (500, 2, "sequential", 300),
    }
    actual = {
        c.name: (c.count, c.n_banks, c.arrival, c.delay_seconds) for c in cal.AMPLE_CONDITIONS
    }
    assert actual == expected
    e = cal.EXP3_CONDITION
    assert (e.count, e.n_banks, e.arrival, e.delay_seconds) == (500, 2, "sequential", 60)


def test_run_counts_passes_the_right_arguments(monkeypatch):
    captured = {}
    real_generate = transactions.generate_transactions

    def fake_generate(**kwargs):
        captured["gen"] = kwargs
        return real_generate(**kwargs)

    def fake_run(data, model, params):
        captured["params"] = params
        captured["model"] = model
        return [], None

    monkeypatch.setattr(cal.transactions, "generate_transactions", fake_generate)
    monkeypatch.setattr(cal.simulator, "run_model", fake_run)
    monkeypatch.setattr(cal.metrics, "count_by_reason", lambda results: {
        "n_insufficient_funds": 7, "n_partial_insufficient_funds": 3,
    })
    condition = cal.Condition("x", count=30, n_banks=5, arrival="burst", delay_seconds=300)
    scale = 2**3 * 0.25
    usd, jpy = cal.REFERENCE_USD * scale, cal.REFERENCE_JPY * scale
    out = cal.run_counts(condition, Model.ATOMIC, 203, usd, jpy)

    assert out == {FUNDS: 7, PARTIAL_FUNDS: 3}
    assert captured["gen"] == {"count": 30, "seed": 203, "n_banks": 5, "arrival": "burst"}
    p = captured["params"]
    assert captured["model"] == Model.ATOMIC
    assert p.seed == 203
    assert p.n_banks == 5
    assert p.delay_seconds == 300
    assert p.failure_probability == 0
    assert p.initial_usd == 100_000_000 * 2.0
    assert p.initial_jpy == 15_000_000_000 * 2.0
    assert p.initial_jpy / p.initial_usd == 150


def test_make_table_scales_usd_and_jpy_together_by_default():
    seen = []

    def fake(condition, model, seed, usd, jpy):
        seen.append((usd, jpy))
        return {FUNDS: 0, PARTIAL_FUNDS: 0}

    table = cal.make_table(fake, "grid", [cal.BASELINE], [Model.SEQUENTIAL], [201], 2, 0.5)
    assert seen == [(100_000_000 * 2.0, 15_000_000_000 * 2.0)]
    assert table.loc[0, "usd"] == 200_000_000
    assert table.loc[0, "jpy"] == 30_000_000_000
    assert table.loc[0, "scaled_currency"] == "both"


def test_make_table_jpy_only_keeps_usd_fixed():
    seen = []

    def fake(condition, model, seed, usd, jpy):
        seen.append((usd, jpy))
        return {FUNDS: 0, PARTIAL_FUNDS: 0}

    table = cal.make_table(
        fake, "grid", [cal.BASELINE], [Model.SEQUENTIAL], [201], 2, 0.5, jpy_only=True
    )
    assert seen == [(100_000_000 * 4.0, 15_000_000_000 * 4.0 * 0.5)]
    assert table.loc[0, "usd"] == 400_000_000
    assert table.loc[0, "jpy"] == 30_000_000_000
    assert table.loc[0, "scaled_currency"] == "jpy"


def test_run_counts_matches_real_engine_for_partial_funds():
    """Tight JPY liquidity: partial (USD leg done, JPY short) differs from failed count."""
    condition = cal.Condition("tiny", count=40, n_banks=2, delay_seconds=60)
    usd, jpy = 2_000_000.0, 100_000_000.0  # tight: both partial and failed shortages occur
    seed = 201
    data = transactions.generate_transactions(count=40, seed=seed, n_banks=2, arrival="sequential")
    params = simulator.SimulationParams(
        seed=seed, initial_usd=usd, initial_jpy=jpy, delay_seconds=60,
        failure_probability=0.0, n_banks=2,
    )  # fmt: skip
    for model in cal.MODELS:
        results, _ = simulator.run_model(data, model, params)
        expected = metrics.count_by_reason(results)
        got = cal.run_counts(condition, model, seed, usd, jpy)
        assert got[FUNDS] == expected["n_insufficient_funds"]
        assert got[PARTIAL_FUNDS] == expected["n_partial_insufficient_funds"]
    results, _ = simulator.run_model(data, Model.SEQUENTIAL, params)
    expected = metrics.count_by_reason(results)
    got = cal.run_counts(condition, Model.SEQUENTIAL, seed, usd, jpy)
    assert got[PARTIAL_FUNDS] > 0
    assert expected["n_failed_insufficient_funds"] > 0
    assert expected["n_insufficient_funds"] == (
        expected["n_partial_insufficient_funds"] + expected["n_failed_insufficient_funds"]
    )
    assert got[PARTIAL_FUNDS] != expected["n_failed_insufficient_funds"]
    assert got[FUNDS] != got[PARTIAL_FUNDS]


def test_ample_stage_calls_every_condition_model_seed():
    calls = []

    def fake(condition, model, seed, usd, jpy):
        calls.append((condition.name, str(model), seed, usd, jpy))
        return {FUNDS: 0, PARTIAL_FUNDS: 0}

    seeds = [201, 202]
    row, checks = cal.run_calibration(fake, seeds=seeds)
    ample_calls = [c for c in calls if c[3] == cal.REFERENCE_USD]
    assert len(ample_calls) >= 8 * 3 * 2
    first = calls[: 8 * 3 * 2]
    assert {(c[0], c[1], c[2]) for c in first} == {
        (cond.name, str(m), s) for cond in cal.AMPLE_CONDITIONS for m in cal.MODELS for s in seeds
    }
    assert (checks[checks["stage"] == "ample"]["attempt"] == 0).all()


def threshold_fake(limit_jpy: float):
    """Fake runner: shortage (and funds-partial in Model A) below limit_jpy; ample above."""
    calls = []

    def fake(condition, model, seed, usd, jpy):
        calls.append((condition.name, str(model), seed, usd, jpy))
        short = jpy < limit_jpy
        return {FUNDS: int(short), PARTIAL_FUNDS: int(short and str(model) == A)}

    return fake, calls


def test_doublings_path_scales_grid_and_h4b():
    # Ample only from JPY 60bn (USD 400M, 2 doublings); every lower JPY level is short.
    fake, calls = threshold_fake(limit_jpy=60_000_000_000)
    row, checks = cal.run_calibration(fake, seeds=[201, 202], conditions=[cal.BASELINE])
    assert row["doublings_used"] == 2
    assert row["reference_usd"] == 400_000_000
    assert row["reference_jpy"] == 60_000_000_000
    grid = checks[checks["stage"].isin(["grid", "h4b"])]
    assert (grid["doublings"] == 2).all()
    assert set(grid["multiplier"]) == {0.75, 0.5, 0.25, 0.1, 1.0}
    assert (grid["usd"] == 400_000_000).all()  # USD fixed in grid and H4b stages
    assert (grid["jpy"] == 60_000_000_000 * grid["multiplier"]).all()
    assert (grid["scaled_currency"] == "jpy").all()
    ample = checks[checks["stage"] == "ample"]
    assert (ample["scaled_currency"] == "both").all()
    assert (ample["usd"] == 100_000_000 * 2.0 ** ample["doublings"]).all()
    assert (ample["jpy"] == 15_000_000_000 * 2.0 ** ample["doublings"]).all()
    assert (ample["multiplier"] == 1.0).all()
    assert set(ample["doublings"]) == {0, 1, 2}


def test_h4b_uses_final_halved_grid_and_includes_reference():
    # Shortage only below JPY 3bn. First grid: only 0.1 (1.5bn) is short, so one halving:
    # 0.375, 0.25, 0.125, 0.05 -> 1.875bn and 0.75bn are short.
    fake, _ = threshold_fake(limit_jpy=3_000_000_000)
    row, checks = cal.run_calibration(fake, seeds=[201, 202], conditions=[cal.BASELINE])
    assert row["halvings_used"] == 1
    assert row["lower_multipliers"] == "0.375 0.25 0.125 0.05"
    assert row["qualifying_lower_levels"] == "0.125 0.05"
    h4b = checks[checks["stage"] == "h4b"]
    assert set(h4b["multiplier"]) == {1.0, 0.375, 0.25, 0.125, 0.05}
    assert set(h4b["delay_seconds"]) == {0, 60, 300}
    assert row["h4b_multiplier"] == "0.125"
    grid = checks[checks["stage"] == "grid"]
    assert sorted(grid["attempt"].unique()) == [0, 1]


def test_grid_failure_gives_failed_status_and_empty_h4b():
    def fake(condition, model, seed, usd, jpy):
        return {FUNDS: 0, PARTIAL_FUNDS: 0}  # ample, but never a funds-partial

    row, checks = cal.run_calibration(fake, seeds=[201], conditions=[cal.BASELINE])
    assert row["status"] == "failed"
    assert row["grid_condition_met"] is False
    assert row["halvings_used"] == 3
    assert row["h4b_testable"] == ""
    assert row["h4b_multiplier"] == ""
    assert "h4b" not in set(checks["stage"])
    assert sorted(checks[checks["stage"] == "grid"]["attempt"].unique()) == [0, 1, 2, 3]


def test_h4b_odd_seed_count_threshold_is_ceil():
    seeds = [201, 202, 203]

    def table(n: int) -> pd.DataFrame:
        rows = [
            {"model": A, "seed": s, "multiplier": 0.5, "delay_seconds": d,
             PARTIAL_FUNDS: int(i < n)}
            for d in cal.H4B_DELAYS for i, s in enumerate(seeds)
        ]  # fmt: skip
        return pd.DataFrame(rows)

    assert cal.h4b_level(table(2), (0.5,), seeds) == 0.5
    assert cal.h4b_level(table(1), (0.5,), seeds) is None


def test_missing_seed_row_depends_on_set_check():
    # Every present seed has a shortage, so the count equals len(seeds) - 1 only if a seed
    # is missing; add a duplicate seed row so the plain count would reach len(seeds).
    table = grid_rows({0.5: 10})
    table = table[table["seed"] != 110]
    extra = table[table["seed"] == 101].copy()
    extra["seed"] = 999  # unknown seed with a shortage: count of 10 seeds, but 110 missing
    table = pd.concat([table, extra], ignore_index=True)
    assert cal.seeds_with_shortage(table) == 10
    assert cal.qualifying_lower_levels(table, (0.5,), SEEDS) == []


def test_main_refuses_to_overwrite_without_force(tmp_path):
    fake = lambda condition, model, seed, usd, jpy: {FUNDS: 0, PARTIAL_FUNDS: 0}  # noqa: E731
    (tmp_path / "calibration.csv").write_text("keep me")
    with pytest.raises(FileExistsError, match="--force"):
        cal.main(tmp_path, fake)
    assert (tmp_path / "calibration.csv").read_text() == "keep me"
    assert not (tmp_path / "calibration_checks.csv").exists()


def test_main_refuses_if_only_checks_file_exists(tmp_path):
    fake = lambda condition, model, seed, usd, jpy: {FUNDS: 0, PARTIAL_FUNDS: 0}  # noqa: E731
    (tmp_path / "calibration_checks.csv").write_text("keep me")
    with pytest.raises(FileExistsError):
        cal.main(tmp_path, fake)


def test_main_force_overwrites(tmp_path, monkeypatch):
    def fake(condition, model, seed, usd, jpy):
        return {FUNDS: 0, PARTIAL_FUNDS: 0}

    monkeypatch.setattr(cal, "CALIBRATION_SEEDS", range(201, 203))
    monkeypatch.setattr(cal, "AMPLE_CONDITIONS", (cal.BASELINE,))
    (tmp_path / "calibration.csv").write_text("old")
    # Defaults of run_calibration were bound at import, so call run_calibration pieces via main.
    cal.main(tmp_path, fake, force=True)
    assert (tmp_path / "calibration.csv").read_text() != "old"


def test_cli_exit_code_when_file_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cal, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(cal.main, "__defaults__", (tmp_path, cal.run_counts, False))
    (tmp_path / "calibration.csv").write_text("keep me")
    assert cal.cli([]) == 1
    assert "--force" in capsys.readouterr().out
    assert (tmp_path / "calibration.csv").read_text() == "keep me"


# ------------------------------------------- Day 11: why 2-bank symmetric scaling fails
# Test seeds 201-205 only. These check an explanation of the Day 10 failure; they are not results.

MULTIPLIERS = (1, 0.5, 0.1, 0.05, 0.0125)
STRUCTURE_SEEDS = range(201, 206)


def model_a_counts(seed: int, usd_multiplier: float, jpy_multiplier: float) -> dict[str, int]:
    """Run Model A on 500 two-bank transactions and return the reason counts."""
    data = transactions.generate_transactions(count=500, seed=seed, n_banks=2, arrival="sequential")
    params = simulator.SimulationParams(
        seed=seed,
        initial_usd=cal.REFERENCE_USD * usd_multiplier,
        initial_jpy=cal.REFERENCE_JPY * jpy_multiplier,
        delay_seconds=60,
        failure_probability=0.0,
        n_banks=2,
    )
    results, _ = simulator.run_model(data, Model.SEQUENTIAL, params)
    return metrics.count_by_reason(results)


def test_two_banks_symmetric_scaling_never_gives_second_leg_shortage():
    """With 2 banks and USD and JPY scaled together, no JPY-leg shortage is observed.

    Proposed explanation (a hypothesis, not a proof): the JPY payer at the second leg
    received the same value in USD at the first leg (jpy_amount = 150 * usd_amount), so
    with failure probability 0 and initial_jpy = 150 * initial_usd its JPY tends to stay
    covered while the other bank runs short of USD first. This is not a strict invariant:
    with a 60 s delay and 10 s spacing, legs of different transactions overlap, and USD
    held for an in-flight transaction can let the other bank pay more USD. So this test only
    records the observation for test seeds 201-205 and these multipliers. It checks the
    explanation of the attempt-1 calibration failure; it is not an experimental result.
    """
    first_leg_shortage_seen = False
    for multiplier in MULTIPLIERS:
        for seed in STRUCTURE_SEEDS:
            counts = model_a_counts(seed, multiplier, multiplier)
            assert counts["n_partial_insufficient_funds"] == 0, (multiplier, seed, counts)
            if multiplier <= 0.1 and counts["n_failed_insufficient_funds"] > 0:
                first_leg_shortage_seen = True
    assert first_leg_shortage_seen  # not vacuous: shortages do occur, as first-leg failures


def test_lowering_jpy_only_can_give_second_leg_shortage():
    """With USD at reference and only JPY lowered, a second-leg shortage can occur."""
    found = [
        (m, seed)
        for m in MULTIPLIERS
        for seed in STRUCTURE_SEEDS
        if model_a_counts(seed, 1, m)["n_partial_insufficient_funds"] > 0
    ]
    assert found


# ------------------------------------------- Day 11: attempt 2 (JPY-only grid) bookkeeping


def recording_run(seen: list):
    """Fake run_fn that records (condition name, model, seed, usd, jpy) and finds shortage below 4.5bn JPY."""

    def fake(condition, model, seed, usd, jpy):
        seen.append((condition.name, str(model), seed, usd, jpy))
        short = jpy < 4_500_000_000
        return {FUNDS: int(short), PARTIAL_FUNDS: int(short and str(model) == A)}

    return fake


def test_attempt_constants():
    assert cal.ATTEMPT == 2
    assert cal.GRID_SCALING == "jpy_only"
    assert "scaled_currency" in cal.TABLE_COLUMNS


def test_summary_row_records_attempt_and_grid_scaling():
    row, _ = cal.run_calibration(recording_run([]), seeds=[201, 202], conditions=[cal.BASELINE])
    assert row["attempt"] == 2
    assert row["grid_scaling"] == "jpy_only"
    failed_row, _ = cal.run_calibration(
        lambda *a: {FUNDS: 1, PARTIAL_FUNDS: 1}, seeds=[201], conditions=[cal.BASELINE]
    )
    assert failed_row["attempt"] == 2  # also recorded when the ample stage fails
    assert failed_row["grid_scaling"] == "jpy_only"


def test_grid_and_h4b_pass_reference_usd_and_scaled_jpy_to_run_fn():
    seen: list = []
    row, checks = cal.run_calibration(
        recording_run(seen), seeds=[201], conditions=[cal.BASELINE]
    )
    assert row["doublings_used"] == 0
    n_ample = 1 * 3 * 1
    non_ample = seen[n_ample:]
    assert non_ample  # grid and h4b calls exist
    assert {usd for _, _, _, usd, _ in non_ample} == {cal.REFERENCE_USD}
    jpys = {round(jpy / cal.REFERENCE_JPY, 6) for _, _, _, _, jpy in non_ample}
    assert {0.5, 0.25, 0.1, 1.0} <= jpys
    for stage in ("grid", "h4b"):
        part = checks[checks["stage"] == stage]
        assert len(part) > 0
        assert (part["scaled_currency"] == "jpy").all()
        assert (part["usd"] == cal.REFERENCE_USD).all()
        assert (part["jpy"] == cal.REFERENCE_JPY * part["multiplier"]).all()


def test_ample_stage_scales_both_currencies_in_run_fn_calls():
    seen: list = []
    cal.run_calibration(recording_run(seen), seeds=[201], conditions=[cal.BASELINE])
    ample_calls = seen[:3]  # doubling 0: 1 condition x 3 models x 1 seed
    assert {(usd, jpy) for _, _, _, usd, jpy in ample_calls} == {
        (cal.REFERENCE_USD, cal.REFERENCE_JPY)
    }
    # With a shortage at doubling 0 the ample stage doubles BOTH currencies together.
    seen2: list = []

    def short_then_ample(condition, model, seed, usd, jpy):
        seen2.append((usd, jpy))
        return {FUNDS: int(usd < 200_000_000), PARTIAL_FUNDS: 0}

    cal.run_calibration(short_then_ample, seeds=[201], conditions=[cal.BASELINE])
    assert (200_000_000, 30_000_000_000) in seen2[:6]
    ample_pairs = {pair for pair in seen2[:6]}
    assert ample_pairs == {(100_000_000, 15_000_000_000), (200_000_000, 30_000_000_000)}


def test_scaled_currency_column_values_by_stage():
    _, checks = cal.run_calibration(
        recording_run([]), seeds=[201], conditions=[cal.BASELINE]
    )
    by_stage = checks.groupby("stage")["scaled_currency"].unique().apply(list).to_dict()
    assert by_stage == {"ample": ["both"], "grid": ["jpy"], "h4b": ["jpy"]}
