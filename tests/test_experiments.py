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
