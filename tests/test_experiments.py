"""Tests for src/experiments.py (Exp1 Baseline). Small counts and few seeds, all in tmp_path."""

import math
from pathlib import Path

import pandas as pd
import pytest

from src import experiments, simulator, transactions
from src.simulator import Model

SEEDS = [201, 202]  # test seeds; never main seeds 1-30 or calibration seeds 101-110
COUNT = 40
OLD_HEADER = "run_utc,experiment,model,seeds,parameters,git_commit,status,note"
OLD_ROW = "2026-11-09T22:35:19Z,calibration,A|B|C,101-110,old,abc,failed,old note"


@pytest.fixture(autouse=True)
def clean_git(monkeypatch):
    """Pretend the git tree is clean, so tests do not depend on the real repo state."""
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123")


def write_calibration(path: Path, status: str = "ok", ample: bool = True,
                      usd: int = 100_000_000, jpy: int = 15_000_000_000) -> Path:
    """Write a fake calibration.csv with the columns the experiment reads."""
    pd.DataFrame([{"status": status, "ample_reached": ample,
                   "reference_usd": usd, "reference_jpy": jpy}]).to_csv(path, index=False)
    return path


def run_main(tmp_path: Path, **kwargs):
    """Run main with a fake calibration, 2 seeds and 40 transactions."""
    write_calibration(tmp_path / "calibration.csv")
    return experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT, **kwargs)


# ------------------------------------------------------------ spec defaults

def test_spec_defaults():
    assert list(experiments.MAIN_SEEDS) == list(range(1, 31))
    assert [(c.name, c.failure_probability) for c in experiments.CONDITIONS] == [
        ("baseline", 0.01), ("sanity_0pct", 0.0)]
    assert experiments.MODELS == (Model.SEQUENTIAL, Model.PREFUNDED, Model.ATOMIC)
    assert experiments.COUNT == 500
    assert experiments.N_BANKS == 2
    assert experiments.ARRIVAL == "sequential"
    assert experiments.DELAY_SECONDS == 60
    assert experiments.CUTOFF_SECONDS == 3600


# ------------------------------------------------------------ calibration

def test_refuses_missing_calibration(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)


def test_refuses_failed_calibration(tmp_path):
    write_calibration(tmp_path / "calibration.csv", status="failed")
    with pytest.raises(ValueError, match="status"):
        experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)


def test_refuses_ample_not_reached(tmp_path):
    write_calibration(tmp_path / "calibration.csv", ample=False)
    with pytest.raises(ValueError, match="ample"):
        experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)


def test_reads_reference_balances(tmp_path):
    path = write_calibration(tmp_path / "c.csv", usd=200, jpy=300)
    assert experiments.read_reference(path) == (200, 300)


def test_nothing_written_when_calibration_refused(tmp_path):
    write_calibration(tmp_path / "calibration.csv", status="failed")
    with pytest.raises(ValueError):
        experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    assert not (tmp_path / "run_metrics.csv").exists()
    assert not (tmp_path / "experiment_log.csv").exists()


# ------------------------------------------------------------ overwrite

def test_overwrite_protection(tmp_path):
    run_main(tmp_path)
    with pytest.raises(FileExistsError):
        run_main(tmp_path)
    assert run_main(tmp_path, force=True)["n_runs"] == 12


def test_overwrite_protection_baseline_file_only(tmp_path):
    (tmp_path / "baseline_results.csv").write_text("x\n")
    with pytest.raises(FileExistsError):
        run_main(tmp_path)


def test_overwrite_protection_summary_file_only(tmp_path):
    (tmp_path / "summary.csv").write_text("x\n")
    with pytest.raises(FileExistsError, match="summary.csv"):
        run_main(tmp_path)


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(experiments, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(experiments, "main", lambda **kw: (_ for _ in ()).throw(FileExistsError("x")))
    assert experiments.cli(["baseline"]) == 1
    monkeypatch.setattr(experiments, "main", lambda **kw: {})
    assert experiments.cli(["baseline"]) == 0
    with pytest.raises(SystemExit):
        experiments.cli(["unknown"])


# ------------------------------------------------------------ log

def test_log_appended_header_and_rows_kept(tmp_path):
    log = tmp_path / "experiment_log.csv"
    log.write_text(OLD_HEADER + "\n" + OLD_ROW + "\n")
    run_main(tmp_path)
    lines = log.read_text().splitlines()
    assert lines[0] == OLD_HEADER
    assert lines[1] == OLD_ROW
    assert len(lines) == 2 + 12
    table = pd.read_csv(log)
    new = table.iloc[1:]
    assert set(new["experiment"]) == {"exp1_baseline"}
    assert set(new["seeds"].astype(str)) == {"201", "202"}
    assert set(new["status"]) == {"ok"}
    assert "condition=baseline;count=40;n_banks=2;arrival=sequential;delay_seconds=60" in new["parameters"].iloc[0]


def test_log_appended_again_with_force(tmp_path):
    run_main(tmp_path)
    run_main(tmp_path, force=True)
    assert len(pd.read_csv(tmp_path / "experiment_log.csv")) == 24


def test_log_created_with_header_if_missing(tmp_path):
    run_main(tmp_path)
    assert (tmp_path / "experiment_log.csv").read_text().splitlines()[0] == OLD_HEADER


def test_log_row_added_after_file_without_trailing_newline(tmp_path):
    log = tmp_path / "experiment_log.csv"
    log.write_text(OLD_HEADER + "\n" + OLD_ROW)
    run_main(tmp_path)
    assert len(pd.read_csv(log)) == 13


# ------------------------------------------------------------ run_metrics

def test_run_metrics_one_row_per_run(tmp_path):
    run_main(tmp_path)
    runs = pd.read_csv(tmp_path / "run_metrics.csv")
    assert len(runs) == 2 * 3 * len(SEEDS)
    assert not runs.duplicated(["condition", "model", "seed"]).any()
    assert set(runs["model"]) == {"sequential", "prefunded", "atomic"}
    assert set(runs["condition"]) == {"baseline", "sanity_0pct"}
    first = ["experiment", "condition", "model", "seed", "count", "n_banks", "arrival",
             "delay_seconds", "failure_probability", "initial_usd", "initial_jpy"]
    assert list(runs.columns[: len(first)]) == first
    assert list(runs.columns[-2:]) == ["git_commit", "run_utc"]
    for column in ["success_rate", "n_partial", "principal_exposure_usd", "cutoff_seconds",
                   "gross_prefunding_usd", "peak_liquidity_proxy_usd", "n_insufficient_funds"]:
        assert column in runs.columns
    assert set(runs["failure_probability"]) == {0.01, 0.0}
    assert set(runs["count"]) == {COUNT}
    assert set(runs["initial_usd"]) == {100_000_000}


def test_run_metrics_column_order_is_stable(tmp_path):
    run_main(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    run_main(other)
    first = pd.read_csv(tmp_path / "run_metrics.csv").columns.tolist()
    assert first == pd.read_csv(other / "run_metrics.csv").columns.tolist()


def test_same_transactions_shared_across_models(monkeypatch):
    seen: list[tuple[Model, int]] = []
    real = simulator.run_model

    def spy(data, model, params):
        seen.append((model, id(data)))
        return real(data, model, params)

    monkeypatch.setattr(simulator, "run_model", spy)
    experiments.run_all(100_000_000, 15_000_000_000, seeds=[201, 202], count=COUNT)
    by_seed = [seen[i:i + 6] for i in range(0, len(seen), 6)]
    assert len(by_seed) == 2
    for group in by_seed:
        assert len({data_id for _, data_id in group}) == 1  # one data set per seed
        assert {m for m, _ in group} == set(experiments.MODELS)


def test_transactions_generated_once_per_seed_with_that_seed(monkeypatch):
    calls: list[int] = []
    real = transactions.generate_transactions

    def spy(**kwargs):
        calls.append(kwargs["seed"])
        return real(**kwargs)

    monkeypatch.setattr(transactions, "generate_transactions", spy)
    experiments.run_all(100_000_000, 15_000_000_000, seeds=[203, 204], count=COUNT)
    assert calls == [203, 204]


def test_sanity_condition_has_no_failures_baseline_uses_failure_probability():
    runs = experiments.run_all(100_000_000, 15_000_000_000, seeds=[201, 202, 203], count=200)
    sanity = runs[runs["condition"] == "sanity_0pct"]
    assert (sanity["failure_probability"] == 0.0).all()
    assert (sanity["n_technical_failure"] == 0).all()
    assert (sanity["n_settled"] == 200).all()
    base = runs[runs["condition"] == "baseline"]
    assert (base["failure_probability"] == 0.01).all()
    assert base["n_technical_failure"].sum() > 0


# ------------------------------------------------------------ aggregation

def test_baseline_results_nan_stays_nan_for_model_a_prefunding(tmp_path):
    run_main(tmp_path)
    table = pd.read_csv(tmp_path / "baseline_results.csv")
    assert list(table.columns) == ["condition", "model", "metric", "n_seeds", "n_valid", "mean", "min", "max"]
    a = table[(table["model"] == "sequential") & (table["metric"] == "gross_prefunding_usd")]
    assert len(a) == 2
    assert a[["mean", "min", "max"]].isna().all().all()
    assert (a["n_valid"] == 0).all()
    b = table[(table["model"] == "prefunded") & (table["metric"] == "gross_prefunding_usd")]
    assert b["mean"].notna().all()
    assert (table["n_seeds"] == len(SEEDS)).all()
    assert (b["n_valid"] == len(SEEDS)).all()
    assert len(table) == 2 * 3 * len(experiments.SUMMARY_METRICS)
    raw = (tmp_path / "run_metrics.csv").read_text()
    assert ",nan" not in raw.lower()


def test_aggregate_values():
    runs = pd.DataFrame({
        "condition": ["c"] * 3, "model": ["m"] * 3,
        **{metric: [1.0, 2.0, 6.0] for metric in experiments.SUMMARY_METRICS},
    })
    row = experiments.aggregate(runs).iloc[0]
    assert (row["n_seeds"], row["n_valid"], row["mean"], row["min"], row["max"]) == (3, 3, 3.0, 1.0, 6.0)


def test_aggregate_n_valid_ignores_nan_in_some_seeds():
    values = [1.0, float("nan"), 5.0]
    runs = pd.DataFrame({
        "condition": ["c"] * 3, "model": ["m"] * 3,
        **{metric: values for metric in experiments.SUMMARY_METRICS},
    })
    row = experiments.aggregate(runs).iloc[0]
    assert (row["n_seeds"], row["n_valid"]) == (3, 2)
    assert (row["mean"], row["min"], row["max"]) == (3.0, 1.0, 5.0)


def test_summary_has_experiment_column_and_same_rows(tmp_path):
    run_main(tmp_path)
    summary = pd.read_csv(tmp_path / "summary.csv")
    baseline = pd.read_csv(tmp_path / "baseline_results.csv")
    assert summary.columns[0] == "experiment"
    assert set(summary["experiment"]) == {"exp1_baseline"}
    assert len(summary) == len(baseline)


# ------------------------------------------------------------ self-checks

def test_self_check_raises_on_atomic_partial(monkeypatch):
    # Make calculate_metrics report an atomic partial.
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        row["n_partial"] = 1
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="atomic"):
        experiments.run_all(100_000_000, 15_000_000_000, seeds=[201], count=COUNT)


def test_self_check_raises_on_rates_not_summing_to_one(monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        row["success_rate"] = row["success_rate"] / 2 + 0.2
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="sum"):
        experiments.run_all(100_000_000, 15_000_000_000, seeds=[201], count=COUNT)


def test_self_check_raises_when_total_balance_changes(monkeypatch):
    real = simulator.run_model

    def leaking(data, model, params):
        results, ledger = real(data, model, params)
        ledger._balance[("A", simulator.Currency.USD)] += 1  # money appears from nowhere
        return results, ledger

    monkeypatch.setattr(simulator, "run_model", leaking)
    with pytest.raises(RuntimeError, match="total"):
        experiments.run_all(100_000_000, 15_000_000_000, seeds=[201], count=COUNT)


def test_self_check_raises_on_partial_in_sanity_condition(monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        if params.failure_probability == 0:
            row["n_partial_technical_failure"] = 1  # a technical partial cannot happen at 0%
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="technical-failure partial"):
        experiments.run_all(100_000_000, 15_000_000_000, seeds=[201], count=COUNT)


def test_self_check_raises_on_atomic_principal_exposure_seconds(monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        row["principal_exposure_usd_seconds"] = 1.0
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="atomic"):
        experiments.run_all(100_000_000, 15_000_000_000, seeds=[201], count=COUNT)


def test_check_run_passes_for_a_clean_run():
    data = transactions.generate_transactions(count=COUNT, seed=201)
    for model in experiments.MODELS:
        row = experiments.run_one(data, model, experiments.CONDITIONS[0], 201,
                                  100_000_000, 15_000_000_000, COUNT, 2, 60)
        assert math.isclose(row["success_rate"] + row["partial_rate"] + row["failure_rate"], 1.0)


def test_nothing_written_when_self_check_fails(tmp_path, monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        row["success_rate"] = 0.0
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    write_calibration(tmp_path / "calibration.csv")
    with pytest.raises(RuntimeError, match="sum"):
        experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    assert not (tmp_path / "run_metrics.csv").exists()
    assert not (tmp_path / "experiment_log.csv").exists()


# ------------------------------------------------------------ ample

def test_ample_violated_status_when_balances_are_tiny(tmp_path, capsys):
    write_calibration(tmp_path / "calibration.csv", usd=1000, jpy=150_000)
    result = experiments.main(results_dir=tmp_path, seeds=[201], count=COUNT)
    assert result["ample_violated"] is True
    assert "WARNING" in capsys.readouterr().out
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    assert "ample_violated" in set(log["status"])
    assert log["note"].notna().any()


def test_ample_reference_gives_status_ok(tmp_path, capsys):
    result = run_main(tmp_path)
    assert result["ample_violated"] is False
    assert "Ample violated: False" in capsys.readouterr().out


def test_ample_violation_by_partial_in_sanity_is_not_swallowed(tmp_path, capsys):
    # Tiny JPY balance: Model A pays the first leg, then the second leg lacks funds (partial).
    write_calibration(tmp_path / "calibration.csv", usd=100_000_000, jpy=150_000)
    result = experiments.main(results_dir=tmp_path, seeds=[201], count=COUNT)  # no exception
    assert result["ample_violated"] is True
    assert "WARNING" in capsys.readouterr().out
    runs = pd.read_csv(tmp_path / "run_metrics.csv")
    sanity_a = runs[(runs["condition"] == "sanity_0pct") & (runs["model"] == "sequential")]
    assert (sanity_a["n_partial_insufficient_funds"] > 0).all()
    assert (sanity_a["n_partial_technical_failure"] == 0).all()
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    assert "ample_violated" in set(log["status"])
    for name in ("run_metrics.csv", "baseline_results.csv", "summary.csv"):
        assert (tmp_path / name).exists()


def test_dirty_tree_is_refused_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123-dirty")
    with pytest.raises(experiments.DirtyTreeError, match="uncommitted"):
        run_main(tmp_path)
    assert not (tmp_path / "run_metrics.csv").exists()
    assert not (tmp_path / "experiment_log.csv").exists()


def test_dirty_tree_cli_exit_code_1_and_allow_dirty_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123-dirty")
    seen = {}

    def fake_main(**kwargs):
        seen.update(kwargs)
        if not kwargs["allow_dirty"]:
            raise experiments.DirtyTreeError("uncommitted changes")
        return {}

    monkeypatch.setattr(experiments, "main", fake_main)
    assert experiments.cli(["baseline"]) == 1
    assert "uncommitted" in capsys.readouterr().out
    assert experiments.cli(["baseline", "--allow-dirty"]) == 0
    assert seen["allow_dirty"] is True


def test_dirty_tree_with_allow_dirty_prints_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123-dirty")
    run_main(tmp_path, allow_dirty=True)
    assert "uncommitted" in capsys.readouterr().out
    assert set(pd.read_csv(tmp_path / "run_metrics.csv")["git_commit"]) == {"abc123-dirty"}


# ------------------------------------------------------------ reproducibility

def test_same_seeds_give_identical_run_metrics(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    run_main(first)
    run_main(second)
    ignore = ["run_utc", "git_commit"]
    one = pd.read_csv(first / "run_metrics.csv").drop(columns=ignore)
    two = pd.read_csv(second / "run_metrics.csv").drop(columns=ignore)
    pd.testing.assert_frame_equal(one, two)


# ====================================================================== stress (Day 12)
# Exp3 + Exp4. Test seeds 201+ only; every output goes to tmp_path.

STRESS_COUNT = 100
JPY_REF = 15_000_000_000


def write_stress_calibration(path: Path, lower: str = "0.5 0.25", h4b: float = 0.5, testable: bool = True,
                             jpy: int = JPY_REF, usd: int = 100_000_000) -> Path:
    """Write a fake calibration.csv with the columns the stress run reads."""
    pd.DataFrame([{
        "status": "ok", "ample_reached": True, "reference_usd": usd, "reference_jpy": jpy,
        "lower_multipliers": lower, "h4b_multiplier": h4b, "h4b_testable": testable,
    }]).to_csv(path, index=False)
    return path


def run_stress(tmp_path: Path, lower: str = "0.5 0.25", with_baseline: bool = True, seeds=SEEDS,
               jpy: int = JPY_REF, **kwargs):
    """Run Exp1 (small) for summary.csv, then the stress run (small) in tmp_path."""
    write_stress_calibration(tmp_path / "calibration.csv", lower=lower, jpy=jpy)
    if with_baseline:
        experiments.main(results_dir=tmp_path, seeds=seeds, count=COUNT)
    return experiments.main_stress(results_dir=tmp_path, seeds=seeds, count=STRESS_COUNT, **kwargs)


def fake_levels(lower=(0.5, 0.25), h4b=0.5) -> experiments.StressLevels:
    return experiments.StressLevels(tuple(lower), h4b, "" if h4b is not None else "not testable")


@pytest.fixture(scope="module")
def stress_runs() -> pd.DataFrame:
    """Small stress run table (2 test seeds), shared by the self-check tests."""
    with pytest.MonkeyPatch.context() as patch:  # module scope: the function-scope fixture is not usable
        patch.setattr(experiments, "git_version", lambda: "abc123")
        return experiments.run_stress_all(
            100_000_000, JPY_REF, experiments.stress_conditions(fake_levels()), seeds=SEEDS, count=STRESS_COUNT)


def test_stress_cells_read_from_real_calibration_file():
    levels = experiments.read_stress_levels(experiments.RESULTS_DIR / "calibration.csv")
    # These assert what the file holds today (attempt 2); the code itself never hard-codes them.
    assert levels.lower_multipliers == (0.09375, 0.0625, 0.03125, 0.0125)
    assert levels.h4b_multiplier == 0.09375
    cells = experiments.stress_conditions(levels)
    assert len(cells) == 13
    assert [c.name for c in cells if c.experiment == "exp3_liquidity"] == [
        "jpy_1", "jpy_0.09375", "jpy_0.0625", "jpy_0.03125", "jpy_0.0125"]


def test_stress_cells_follow_a_fake_calibration(tmp_path):
    path = write_stress_calibration(tmp_path / "c.csv", lower="0.5 0.2", h4b=0.4)
    levels = experiments.read_stress_levels(path)
    assert levels.lower_multipliers == (0.5, 0.2) and levels.h4b_multiplier == 0.4
    cells = experiments.stress_conditions(levels)
    by_name = {(c.experiment, c.name): c for c in cells}
    assert ("exp3_liquidity", "jpy_0.2") in by_name
    assert by_name[("exp4_h4b", "h4b_delay_300")].jpy_multiplier == 0.4
    assert len(cells) == 3 + 3 + 2 + 3


def test_stress_cell_table_is_exact():
    cells = experiments.stress_conditions(fake_levels())
    table = {(c.experiment, c.name): (c.failure_probability, c.delay_seconds, c.jpy_multiplier, c.ample)
             for c in cells}
    assert table == {
        ("exp3_liquidity", "jpy_1"): (0.01, 60, 1.0, True),
        ("exp3_liquidity", "jpy_0.5"): (0.01, 60, 0.5, False),
        ("exp3_liquidity", "jpy_0.25"): (0.01, 60, 0.25, False),
        ("exp4_failure", "failure_0"): (0.0, 60, 1.0, True),
        ("exp4_failure", "failure_0.01"): (0.01, 60, 1.0, True),
        ("exp4_failure", "failure_0.05"): (0.05, 60, 1.0, True),
        ("exp4_delay", "delay_0"): (0.01, 0, 1.0, True),
        ("exp4_delay", "delay_300"): (0.01, 300, 1.0, True),
        ("exp4_h4b", "h4b_delay_0"): (0.01, 0, 0.5, False),
        ("exp4_h4b", "h4b_delay_60"): (0.01, 60, 0.5, False),
        ("exp4_h4b", "h4b_delay_300"): (0.01, 300, 0.5, False),
    }


def test_stress_has_no_duplicate_cell_and_no_second_60s_delay_cell():
    cells = experiments.stress_conditions(fake_levels())
    assert len({(c.experiment, c.name) for c in cells}) == len(cells)
    # delay 60 / failure 1% / multiplier 1 under exp4_* exists once (in exp4_failure).
    sixty = [c for c in cells if c.experiment.startswith("exp4_") and c.delay_seconds == 60
             and c.failure_probability == 0.01 and c.jpy_multiplier == 1.0]
    assert [(c.experiment, c.name) for c in sixty] == [("exp4_failure", "failure_0.01")]
    assert "exp4_failure" in experiments.SHARED_CELL_NOTE


def test_h4b_cells_skipped_when_not_testable(tmp_path, capsys):
    path = write_stress_calibration(tmp_path / "calibration.csv", testable=False)
    levels = experiments.read_stress_levels(path)
    assert levels.h4b_multiplier is None and levels.h4b_skip_reason
    assert len(experiments.stress_conditions(levels)) == 8
    experiments.main(results_dir=tmp_path, seeds=[201], count=COUNT)
    result = experiments.main_stress(results_dir=tmp_path, seeds=[201], count=STRESS_COUNT)
    assert result["h4b_skipped"] is True
    assert "H4b cells skipped" in capsys.readouterr().out
    runs = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    assert "exp4_h4b" not in set(runs["experiment"])


def test_stress_refuses_bad_calibration(tmp_path):
    pd.DataFrame([{"status": "failed", "ample_reached": True, "reference_usd": 1, "reference_jpy": 1,
                   "lower_multipliers": "0.5", "h4b_multiplier": 0.5, "h4b_testable": True}]
                 ).to_csv(tmp_path / "calibration.csv", index=False)
    with pytest.raises(ValueError, match="status"):
        experiments.main_stress(results_dir=tmp_path, seeds=[201], count=STRESS_COUNT)
    path = tmp_path / "old.csv"
    write_calibration(path)  # no lower_multipliers column
    with pytest.raises(ValueError, match="lower_multipliers"):
        experiments.read_stress_levels(path)


def test_stress_needs_baseline_results(tmp_path):
    with pytest.raises(ValueError, match="Run Exp1"):
        run_stress(tmp_path, with_baseline=False)
    assert not (tmp_path / "stress_run_metrics.csv").exists()


def test_initial_jpy_is_rounded_reference_times_multiplier():
    assert experiments.initial_jpy_for(15_000_000_000, 0.09375) == 1_406_250_000
    assert experiments.initial_jpy_for(15_000_000_000, 0.0125) == 187_500_000
    assert experiments.initial_jpy_for(15_000_000_000, 1.0) == 15_000_000_000
    assert isinstance(experiments.initial_jpy_for(15_000_000_000, 0.0125), int)
    assert experiments.initial_jpy_for(101, 0.5) == 50  # rounds to a whole yen


def test_stress_run_rows_record_jpy_and_multiplier(tmp_path):
    result = run_stress(tmp_path)
    assert result["n_runs"] == 11 * 3 * len(SEEDS) and result["n_cells"] == 11
    runs = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    exp1_columns = pd.read_csv(tmp_path / "run_metrics.csv").columns.tolist()
    expected = exp1_columns[:11] + ["jpy_multiplier", "ample_cell"] + exp1_columns[11:]
    assert runs.columns.tolist() == expected
    for _, r in runs.iterrows():
        assert r["initial_jpy"] == round(JPY_REF * r["jpy_multiplier"])
        assert r["initial_usd"] == 100_000_000
    assert set(runs["seed"]) == set(SEEDS)
    one = runs[(runs["condition"] == "jpy_0.25") & (runs["model"] == "atomic") & (runs["seed"] == 201)].iloc[0]
    assert one["initial_jpy"] == JPY_REF // 4 and one["delay_seconds"] == 60
    h4b = runs[(runs["condition"] == "h4b_delay_300") & (runs["seed"] == 201)]
    assert set(h4b["delay_seconds"]) == {300} and set(h4b["jpy_multiplier"]) == {0.5}
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    stress_log = log[log["experiment"].str.startswith(("exp3", "exp4"))]
    assert len(stress_log) == result["n_runs"]
    assert all("jpy_multiplier=" in p for p in stress_log["parameters"])
    exp1_log = log[log["experiment"] == "exp1_baseline"]
    assert not any("jpy_multiplier" in p for p in exp1_log["parameters"])
    assert any("jpy_multiplier=0.5" in p for p in stress_log["parameters"])


def test_same_data_across_cells_and_models_within_a_seed(monkeypatch):
    seen: dict[int, set[int]] = {}
    calls: list[int] = []
    real_run, real_gen = simulator.run_model, transactions.generate_transactions

    def spy_run(data, model, params):
        seen.setdefault(params.seed, set()).add(id(data))
        return real_run(data, model, params)

    def spy_gen(**kwargs):
        calls.append(kwargs["seed"])
        return real_gen(**kwargs)

    monkeypatch.setattr(simulator, "run_model", spy_run)
    monkeypatch.setattr(transactions, "generate_transactions", spy_gen)
    cells = experiments.stress_conditions(fake_levels())
    experiments.run_stress_all(100_000_000, JPY_REF, cells, seeds=[203, 204], count=STRESS_COUNT)
    assert calls == [203, 204]
    assert all(len(ids) == 1 for ids in seen.values())  # one data set for all cells and models
    assert set(seen) == {203, 204}


def test_non_ample_cells_have_status_ok_and_ample_cells_flag_violations(tmp_path, capsys):
    # Tiny JPY reference: shortages everywhere. Ample cells -> ample_violated, others -> ok.
    result = run_stress(tmp_path, jpy=150_000)
    assert result["ample_violated"] is True
    assert "WARNING" in capsys.readouterr().out
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    log = log[log["experiment"].str.startswith(("exp3", "exp4"))]
    runs = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    assert (log["status"].values == ["ample_violated" if (a and n > 0) else "ok"
                                     for a, n in zip(runs["ample_cell"], runs["n_insufficient_funds"])]).all()
    h4b = runs[runs["experiment"] == "exp4_h4b"]
    assert (~h4b["ample_cell"]).all() and (h4b["n_insufficient_funds"] > 0).any()
    assert set(log[log["experiment"] == "exp4_h4b"]["status"]) == {"ok"}
    assert "ample_violated" in set(log[log["experiment"] == "exp3_liquidity"]["status"])


def test_ample_reference_gives_all_ok_and_ample_flag_in_csv(tmp_path):
    result = run_stress(tmp_path)
    assert result["ample_violated"] is False
    runs = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    flags = runs.groupby("condition")["ample_cell"].first().to_dict()
    assert flags["jpy_1"] and flags["failure_0.05"] and flags["delay_300"]
    assert not flags["jpy_0.5"] and not flags["jpy_0.25"] and not flags["h4b_delay_0"]


def test_stress_overwrite_protection(tmp_path):
    run_stress(tmp_path)
    with pytest.raises(FileExistsError, match="stress_run_metrics.csv"):
        run_stress(tmp_path, with_baseline=False)
    assert run_stress(tmp_path, with_baseline=False, force=True)["n_runs"] == 66


def test_stress_overwrite_protection_results_file_only(tmp_path):
    (tmp_path / "stress_test_results.csv").write_text("x\n")
    with pytest.raises(FileExistsError, match="stress_test_results.csv"):
        run_stress(tmp_path)


def test_stress_dirty_tree_refused_and_allowed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123-dirty")
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=[201], count=COUNT, allow_dirty=True)
    with pytest.raises(experiments.DirtyTreeError, match="uncommitted"):
        experiments.main_stress(results_dir=tmp_path, seeds=[201], count=STRESS_COUNT)
    assert not (tmp_path / "stress_run_metrics.csv").exists()
    experiments.main_stress(results_dir=tmp_path, seeds=[201], count=STRESS_COUNT, allow_dirty=True)
    assert "uncommitted" in capsys.readouterr().out
    assert set(pd.read_csv(tmp_path / "stress_run_metrics.csv")["git_commit"]) == {"abc123-dirty"}


def test_stress_cli_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(experiments, "main_stress", lambda **kw: (_ for _ in ()).throw(FileExistsError("x")))
    assert experiments.cli(["stress"]) == 1
    seen = {}
    monkeypatch.setattr(experiments, "main_stress", lambda **kw: seen.update(kw) or {})
    assert experiments.cli(["stress", "--force", "--allow-dirty"]) == 0
    assert seen == {"force": True, "allow_dirty": True}


def test_summary_contains_both_experiments_and_exp1_files_unchanged(tmp_path):
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    before = {n: (tmp_path / n).read_bytes() for n in ("run_metrics.csv", "baseline_results.csv")}
    exp1_summary = pd.read_csv(tmp_path / "summary.csv")
    experiments.main_stress(results_dir=tmp_path, seeds=SEEDS, count=STRESS_COUNT)
    for name, content in before.items():
        assert (tmp_path / name).read_bytes() == content
    summary = pd.read_csv(tmp_path / "summary.csv")
    stress = pd.read_csv(tmp_path / "stress_test_results.csv")
    assert list(summary.columns) == ["experiment", "condition", "model", "metric", "n_seeds", "n_valid",
                                     "mean", "min", "max"]
    assert list(stress.columns) == list(summary.columns)
    assert set(summary["experiment"]) == {"exp1_baseline", "exp3_liquidity", "exp4_failure",
                                          "exp4_delay", "exp4_h4b"}
    assert len(summary) == len(exp1_summary) + len(stress)
    pd.testing.assert_frame_equal(summary.iloc[: len(exp1_summary)], exp1_summary)
    assert len(stress) == 11 * 3 * len(experiments.SUMMARY_METRICS)
    assert (stress["n_seeds"] == len(SEEDS)).all()


def test_stress_log_appended_after_exp1_rows(tmp_path):
    run_stress(tmp_path)
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    assert len(log) == 12 + 66


def test_exp1_rows_still_use_exp1_experiment_name(tmp_path):
    run_main(tmp_path)
    assert set(pd.read_csv(tmp_path / "run_metrics.csv")["experiment"]) == {"exp1_baseline"}
    assert experiments.CONDITIONS[0].experiment == "exp1_baseline"
    assert experiments.CONDITIONS[0].jpy_multiplier == 1.0 and experiments.CONDITIONS[0].ample is True


def test_stress_same_seeds_give_identical_results(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    for folder in (first, second):
        folder.mkdir()
        run_stress(folder)
    ignore = ["run_utc", "git_commit"]
    one = pd.read_csv(first / "stress_run_metrics.csv").drop(columns=ignore)
    two = pd.read_csv(second / "stress_run_metrics.csv").drop(columns=ignore)
    pd.testing.assert_frame_equal(one, two)


def test_stress_sanity_failure_0_cell_has_no_technical_failure(stress_runs):
    zero = stress_runs[stress_runs["condition"] == "failure_0"]
    assert (zero["n_technical_failure"] == 0).all() and (zero["n_partial_technical_failure"] == 0).all()
    hit5 = stress_runs[(stress_runs["condition"] == "failure_0.05") & (stress_runs["model"] == "sequential")]
    assert hit5["n_technical_failure"].sum() > 0


# ------------------------------------------------------------ stress self-checks (mutation style)

def mutated(runs: pd.DataFrame, condition: str, model: str, seed: int, **changes) -> pd.DataFrame:
    """Copy of the runs with some columns of one run changed (to feed a bad row to the check)."""
    out = runs.copy()
    mask = (out["condition"] == condition) & (out["model"] == model) & (out["seed"] == seed)
    assert mask.sum() == 1
    for column, value in changes.items():
        out.loc[mask, column] = value
    return out


def test_check_stress_passes_on_a_clean_run(stress_runs):
    experiments.check_stress(stress_runs)


def test_check_stress_raises_when_a_and_b_exposure_differ_at_ample(stress_runs):
    bad = mutated(stress_runs, "delay_300", "prefunded", 201, principal_exposure_usd=1.0)
    with pytest.raises(RuntimeError, match="A and B exposure differ"):
        experiments.check_stress(bad)


def test_check_stress_skips_a_b_equality_when_a_shortage_exists(stress_runs):
    bad = mutated(stress_runs, "delay_300", "prefunded", 201, principal_exposure_usd=1.0, n_insufficient_funds=3)
    experiments.check_stress(bad)  # skipped on purpose: the shortage is reported via the ample status


def test_check_stress_raises_when_exposure_falls_with_failure_probability(stress_runs):
    # Make both models fall from 1% to 5% for seed 201 (A == B kept equal, so only the order check fires).
    bad = stress_runs
    for model in ("sequential", "prefunded"):
        bad = mutated(bad, "failure_0.05", model, 201, principal_exposure_usd=0.0)
    with pytest.raises(RuntimeError, match="falls"):
        experiments.check_stress(bad)


def test_check_stress_raises_when_mean_at_5_percent_is_not_above_0_percent(stress_runs):
    bad = stress_runs
    for seed in SEEDS:
        for model in ("sequential", "prefunded"):
            bad = mutated(bad, "failure_0.05", model, seed, principal_exposure_usd=0.0)
            bad = mutated(bad, "failure_0.01", model, seed, principal_exposure_usd=0.0)
    with pytest.raises(RuntimeError, match="not above"):
        experiments.check_stress(bad)


def test_check_stress_does_not_require_a_hit_in_every_single_seed(stress_runs):
    # One seed with no exposure at 5% (no hit in that seed) is fine: the check reads the mean.
    bad = stress_runs
    for model in ("sequential", "prefunded"):
        bad = mutated(bad, "failure_0.05", model, 201, principal_exposure_usd=0.0)
        bad = mutated(bad, "failure_0.01", model, 201, principal_exposure_usd=0.0)
    experiments.check_stress(bad)


def test_check_stress_skips_order_check_for_seed_with_insufficient_funds(stress_runs):
    bad = stress_runs
    for model in ("sequential", "prefunded"):
        bad = mutated(bad, "failure_0.05", model, 201, principal_exposure_usd=0.0)
    bad = mutated(bad, "failure_0.05", "sequential", 201, n_insufficient_funds=1)
    bad = mutated(bad, "failure_0.05", "prefunded", 201, n_insufficient_funds=1)
    experiments.check_stress(bad)


def test_stress_self_check_raises_on_atomic_partial(monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        row["n_partial"] = 1
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="atomic"):
        experiments.run_stress_all(100_000_000, JPY_REF, experiments.stress_conditions(fake_levels()),
                                   seeds=[201], count=STRESS_COUNT)


def test_stress_self_check_raises_on_technical_partial_in_0_percent_cell(monkeypatch):
    real_metrics = experiments.metrics.calculate_metrics

    def bad_metrics(results, data, params, ledger):
        row = real_metrics(results, data, params, ledger)
        if params.failure_probability == 0:
            row["n_partial_technical_failure"] = 1
        return row

    monkeypatch.setattr(experiments.metrics, "calculate_metrics", bad_metrics)
    with pytest.raises(RuntimeError, match="technical-failure partial"):
        experiments.run_stress_all(100_000_000, JPY_REF, experiments.stress_conditions(fake_levels()),
                                   seeds=[201], count=STRESS_COUNT)


def test_nothing_written_when_stress_self_check_fails(tmp_path, monkeypatch):
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=[201], count=COUNT)
    log_before = (tmp_path / "experiment_log.csv").read_text()
    monkeypatch.setattr(experiments, "check_stress", lambda runs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        experiments.main_stress(results_dir=tmp_path, seeds=[201], count=STRESS_COUNT)
    assert not (tmp_path / "stress_run_metrics.csv").exists()
    assert (tmp_path / "experiment_log.csv").read_text() == log_before


# ====================================================================== sensitivity (Day 13)
# Exp2 x Exp3. Test seeds 201+ only; every output goes to tmp_path. Small counts via `cells`.

SENS_COUNT = 30


def small_cells() -> list[experiments.SensitivityCell]:
    """The 6 real cells with small counts (baseline count must match the stress run count)."""
    cells = experiments.sensitivity_cells()
    sizes = {"volume_100": 20, "volume_1000": 60}
    return [experiments.SensitivityCell(c.name, c.factor, c.factor_level, sizes.get(c.name, SENS_COUNT),
                                        c.n_banks, c.arrival) for c in cells]  # fmt: skip


def run_sensitivity(tmp_path: Path, seeds=SEEDS, with_stress: bool = True, **kwargs):
    """Exp1 + stress (count 30, same seeds) for the inputs, then the small sensitivity run."""
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=seeds, count=COUNT)
    if with_stress:
        experiments.main_stress(results_dir=tmp_path, seeds=seeds, count=SENS_COUNT)
    return experiments.main_sensitivity(results_dir=tmp_path, seeds=seeds, cells=small_cells(), **kwargs)


def test_sensitivity_cell_table_is_exact():
    assert [(c.name, c.factor, c.factor_level, c.count, c.n_banks, c.arrival)
            for c in experiments.sensitivity_cells()] == [
        ("baseline", "baseline", "baseline", 500, 2, "sequential"),
        ("volume_100", "volume", "100", 100, 2, "sequential"),
        ("volume_1000", "volume", "1000", 1000, 2, "sequential"),
        ("banks_5", "banks", "5", 500, 5, "sequential"),
        ("banks_10", "banks", "10", 500, 10, "sequential"),
        ("arrival_burst", "arrival", "burst", 500, 2, "burst"),
    ]


def test_sensitivity_grid_comes_from_calibration():
    grid = experiments.sensitivity_multipliers(fake_levels(lower=(0.5, 0.25)))
    assert grid == [1.0, 0.5, 0.25]


def test_sensitivity_run_count_columns_and_files(tmp_path):
    result = run_sensitivity(tmp_path)
    assert result["n_runs"] == 6 * 3 * 3 * len(SEEDS) == 108
    runs = pd.read_csv(tmp_path / "sensitivity_run_metrics.csv", dtype={"factor_level": str})
    assert len(runs) == 108
    assert "status" not in runs.columns
    assert set(runs["experiment"]) == {"exp2_x_exp3"}
    for column in ("factor", "factor_level", "count", "n_banks", "arrival", "jpy_multiplier", "ample_cell"):
        assert column in runs.columns
    assert set(runs["condition"]) == {f"{c.name}/jpy_{m}" for c in small_cells() for m in ("1", "0.5", "0.25")}
    results = pd.read_csv(tmp_path / "sensitivity_results.csv")
    assert list(results.columns) == ["experiment"] + experiments.AGGREGATE_COLUMNS
    summary = pd.read_csv(tmp_path / "summary.csv")
    assert set(summary["experiment"]) == {"exp1_baseline", "exp3_liquidity", "exp4_failure", "exp4_delay",
                                          "exp4_h4b", "exp2_x_exp3"}  # fmt: skip
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    assert (log["experiment"] == "exp2_x_exp3").sum() == 108


def test_only_grid_level_one_is_an_ample_cell(tmp_path):
    run_sensitivity(tmp_path)
    runs = pd.read_csv(tmp_path / "sensitivity_run_metrics.csv")
    assert (runs["ample_cell"] == (runs["jpy_multiplier"] == 1.0)).all()


def test_n_banks_arrival_and_count_reach_the_engine(monkeypatch):
    calls = []
    real = transactions.generate_transactions

    def spy(**kwargs):
        data = real(**kwargs)
        calls.append((kwargs, data))
        return data

    monkeypatch.setattr(transactions, "generate_transactions", spy)
    seen_params = []
    real_run = simulator.run_model

    def spy_run(data, model, params):
        seen_params.append((len(data), params.n_banks))
        return real_run(data, model, params)

    monkeypatch.setattr(simulator, "run_model", spy_run)
    runs = experiments.run_sensitivity_all(100_000_000, JPY_REF, small_cells(), [1.0, 0.5], seeds=[201])
    by_name = {c["n_banks"]: d for c, d in calls}
    assert set(by_name) == {2, 5, 10}
    banks10 = runs[runs["factor_level"] == "10"]
    assert set(banks10["n_banks"]) == {10} and set(banks10["arrival"]) == {"sequential"}
    banks10_data = next(d for c, d in calls if c["n_banks"] == 10)
    assert len(set(banks10_data["usd_payer"]) | set(banks10_data["jpy_payer"])) > 2  # really uses many banks
    assert {n for n, _ in seen_params if _ == 10} == {SENS_COUNT}
    burst = next(d for c, d in calls if c["arrival"] == "burst")
    seq = next(d for c, d in calls if c["arrival"] == "sequential" and c["count"] == SENS_COUNT and c["n_banks"] == 2)
    assert burst["arrival_time"].tolist() != seq["arrival_time"].tolist()
    assert set(runs[runs["factor_level"] == "burst"]["arrival"]) == {"burst"}
    assert set(runs[runs["factor_level"] == "1000"]["count"]) == {60}
    assert set(runs[runs["factor_level"] == "100"]["count"]) == {20}


def test_transactions_shared_across_grid_levels_and_models(monkeypatch):
    seen = []
    real = simulator.run_model

    def spy(data, model, params):
        seen.append((id(data), model, params.initial_jpy))
        return real(data, model, params)

    monkeypatch.setattr(simulator, "run_model", spy)
    cells = small_cells()[:2]  # baseline and volume_100
    experiments.run_sensitivity_all(100_000_000, JPY_REF, cells, [1.0, 0.5, 0.25], seeds=[201])
    per_cell = [seen[i:i + 9] for i in range(0, len(seen), 9)]
    assert len(per_cell) == 2
    for group in per_cell:
        assert len({d for d, _, _ in group}) == 1  # one data set for 3 levels x 3 models
        assert len({j for _, _, j in group}) == 3
    assert per_cell[0][0][0] != per_cell[1][0][0]  # different cells: different data


def test_baseline_cross_check_passes_against_a_matching_stress_run(tmp_path, capsys):
    result = run_sensitivity(tmp_path)
    assert result["cross_check"].startswith("OK")
    assert "Baseline cross-check vs Exp3: OK" in capsys.readouterr().out


def test_cross_check_skipped_without_exp3_rows_and_raises_on_no_overlap(tmp_path, capsys):
    result = run_sensitivity(tmp_path, seeds=SEEDS)
    sens = pd.read_csv(tmp_path / "sensitivity_run_metrics.csv")
    stress = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    assert result["cross_check"].startswith("OK")
    no_exp3 = stress[stress["experiment"] != "exp3_liquidity"]
    assert experiments.cross_check_baseline(sens, no_exp3).startswith("skipped")
    assert "WARNING" in capsys.readouterr().out
    with pytest.raises(RuntimeError, match="partial or no overlap"):
        experiments.cross_check_baseline(sens, stress.assign(seed=stress["seed"] + 1000))


def test_cross_check_fails_when_a_value_is_altered(tmp_path):
    run_sensitivity(tmp_path)
    sens = pd.read_csv(tmp_path / "sensitivity_run_metrics.csv")
    stress = pd.read_csv(tmp_path / "stress_run_metrics.csv")
    assert experiments.cross_check_baseline(sens, stress).startswith("OK")
    stress.loc[(stress["experiment"] == "exp3_liquidity") & (stress["model"] == "atomic")
               & (stress["seed"] == 202) & (stress["jpy_multiplier"] == 0.5), "n_settled"] += 1
    with pytest.raises(RuntimeError, match="n_settled"):
        experiments.cross_check_baseline(sens, stress)


def test_cross_check_on_small_frames_missing_row_and_nan():
    sens = pd.DataFrame({"factor": ["baseline"] * 2, "seed": [1, 1], "model": ["sequential"] * 2,
                         "jpy_multiplier": [1.0, 0.5], "x": [float("nan"), 2.0], "condition": ["a", "b"]})
    stress = pd.DataFrame({"experiment": ["exp3_liquidity"] * 2, "seed": [1, 1], "model": ["sequential"] * 2,
                           "jpy_multiplier": [1.0, 0.5], "x": [float("nan"), 2.0], "condition": ["z", "y"]})
    assert experiments.cross_check_baseline(sens, stress).startswith("OK")  # NaN equals NaN, condition ignored
    with pytest.raises(RuntimeError, match="not in the sensitivity baseline"):
        experiments.cross_check_baseline(sens.iloc[:1], stress)
    with pytest.raises(RuntimeError, match="not in Exp3"):
        experiments.cross_check_baseline(sens, stress.iloc[:1])


def test_sensitivity_refuses_existing_output_and_force_overwrites(tmp_path):
    run_sensitivity(tmp_path)
    with pytest.raises(FileExistsError):
        experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())
    experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells(), force=True)


def test_sensitivity_refuses_dirty_tree_unless_allowed(tmp_path, monkeypatch):
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    experiments.main_stress(results_dir=tmp_path, seeds=SEEDS, count=SENS_COUNT)
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123-dirty")
    with pytest.raises(experiments.DirtyTreeError):
        experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())
    assert not (tmp_path / "sensitivity_run_metrics.csv").exists()
    experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells(), allow_dirty=True)


def test_sensitivity_needs_baseline_and_stress_results(tmp_path):
    write_stress_calibration(tmp_path / "calibration.csv")
    with pytest.raises(ValueError, match="not found"):
        experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())
    experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    with pytest.raises(ValueError, match="not found"):
        experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())


def test_sensitivity_cross_check_failure_writes_nothing(tmp_path):
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    experiments.main_stress(results_dir=tmp_path, seeds=SEEDS, count=50)  # baseline count differs from 30
    with pytest.raises(RuntimeError, match="cross-check"):
        experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())
    assert not (tmp_path / "sensitivity_run_metrics.csv").exists()


def test_sensitivity_does_not_change_exp1_or_stress_outputs(tmp_path):
    write_stress_calibration(tmp_path / "calibration.csv")
    experiments.main(results_dir=tmp_path, seeds=SEEDS, count=COUNT)
    experiments.main_stress(results_dir=tmp_path, seeds=SEEDS, count=SENS_COUNT)
    before = {n: (tmp_path / n).read_bytes() for n in
              ("run_metrics.csv", "baseline_results.csv", "stress_run_metrics.csv", "stress_test_results.csv")}  # fmt: skip
    experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells())
    assert {n: (tmp_path / n).read_bytes() for n in before} == before


def test_run_one_default_arrival_is_unchanged():
    data = transactions.generate_transactions(count=COUNT, seed=201)
    cond = experiments.CONDITIONS[0]
    row = experiments.run_one(data, Model.ATOMIC, cond, 201, 100_000_000, JPY_REF, COUNT, 2, 60)
    assert row["arrival"] == "sequential"


def test_cli_accepts_sensitivity(monkeypatch):
    seen = {}
    monkeypatch.setattr(experiments, "main_sensitivity", lambda **kw: seen.update(kw))
    assert experiments.cli(["sensitivity", "--force", "--allow-dirty"]) == 0
    assert seen == {"force": True, "allow_dirty": True}


def test_integration_sensitivity_then_h3(tmp_path):
    from src import verdicts
    run_sensitivity(tmp_path)
    table = verdicts.main_h3(results_dir=tmp_path)
    assert len(table[table["hypothesis"] == "H3"]) == 9
    lstar = pd.read_csv(tmp_path / "lstar_by_seed.csv")
    assert len(lstar) == 6 * 3 * len(SEEDS)


def test_cross_check_partial_seed_overlap_raises():
    sens = pd.DataFrame({"factor": ["baseline"] * 2, "seed": [1, 2], "model": ["atomic"] * 2,
                         "jpy_multiplier": [1.0, 1.0], "x": [1, 2]})
    stress = pd.DataFrame({"experiment": ["exp3_liquidity"], "seed": [1], "model": ["atomic"],
                           "jpy_multiplier": [1.0], "x": [1]})
    with pytest.raises(RuntimeError, match=r"\[2\]"):
        experiments.cross_check_baseline(sens, stress)
    bigger = pd.concat([stress, stress.assign(seed=2, x=2), stress.assign(seed=3, x=3)])
    assert experiments.cross_check_baseline(sens, bigger).startswith("OK")  # subset is fine


def test_cross_check_without_common_columns_raises(monkeypatch):
    sens = pd.DataFrame({"factor": ["baseline"], "seed": [1], "model": ["atomic"], "jpy_multiplier": [1.0]})
    stress = pd.DataFrame({"experiment": ["exp3_liquidity"], "seed": [1], "model": ["atomic"],
                           "jpy_multiplier": [1.0]})
    assert experiments.cross_check_baseline(sens, stress).startswith("OK")
    # Make every shared column "skipped": nothing is left to compare, so the check must not pass.
    monkeypatch.setattr(experiments, "CROSS_CHECK_SKIP", experiments.CROSS_CHECK_SKIP + ("seed", "model", "jpy_multiplier"))
    with pytest.raises(RuntimeError, match="no common columns"):
        experiments.cross_check_baseline(sens, stress)


def test_cross_check_empty_baseline_raises():
    sens = pd.DataFrame({"factor": ["volume"], "seed": [1], "model": ["atomic"], "jpy_multiplier": [1.0]})
    stress = pd.DataFrame({"experiment": ["exp3_liquidity"], "seed": [1], "model": ["atomic"],
                           "jpy_multiplier": [1.0]})
    with pytest.raises(RuntimeError, match="no baseline cell"):
        experiments.cross_check_baseline(sens, stress)


def test_force_warns_that_h3_files_are_stale(tmp_path, capsys):
    run_sensitivity(tmp_path)
    (tmp_path / "lstar_by_seed.csv").write_text("x\n")
    (tmp_path / "h3_verdicts.csv").write_text("x\n")
    experiments.main_sensitivity(results_dir=tmp_path, seeds=SEEDS, cells=small_cells(), force=True)
    out = capsys.readouterr().out
    assert "stale" in out and "python -m src.verdicts h3 --force" in out
