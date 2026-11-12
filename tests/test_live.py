"""Tests for src/live.py (Day 15). Seeds 201 and above only (1-30 are the main experiments)."""

import dataclasses
import math
from pathlib import Path

import pandas as pd
import pytest

from src import experiments, live, metrics, simulator, transactions
from src.figures import MODEL_COLORS, MODEL_NAMES
from src.simulator import Model, SimulationParams

RESULTS = experiments.RESULTS_DIR
FIRST = 201


def make_inputs(**changes: object) -> live.LiveInputs:
    """Small fast inputs (100 transactions, 2 seeds) with the reference balances."""
    base = live.default_inputs()
    values = {"count": 100, "n_seeds": 2, "first_seed": FIRST, **changes}
    return dataclasses.replace(base, **values)


def cell(runs: pd.DataFrame, seed: int, model: str) -> pd.Series:
    """One (seed, model) row."""
    return runs[(runs["seed"] == seed) & (runs["model"] == model)].iloc[0]


# ------------------------------------------------------------------ engine is real


# Hand-typed settings for the direct-engine comparison (reference is USD 1e8, JPY 1.5e10 per bank).
DIRECT_CASES = [
    pytest.param(
        dict(n_banks=4, arrival="burst", fx_rate=120.0, delay_seconds=30.0, count=300,
             failure_probability=0.05, initial_usd=50_000_000.0, initial_jpy=3_750_000_000.0),
        id="all_non_default",
    ),
    pytest.param(
        dict(n_banks=2, arrival="sequential", fx_rate=150.0, delay_seconds=60.0, count=500,
             failure_probability=0.0, initial_usd=100_000_000.0, initial_jpy=937_500_000.0),
        id="jpy_0.0625_failure_0",
    ),
    pytest.param(
        dict(n_banks=2, arrival="sequential", fx_rate=150.0, delay_seconds=60.0, count=100,
             failure_probability=0.05, initial_usd=100_000_000.0, initial_jpy=15_000_000_000.0),
        id="default_like",
    ),
]


@pytest.mark.parametrize("case", DIRECT_CASES)
def test_run_live_equals_direct_engine_call(case: dict[str, object]) -> None:
    """The expected side uses only values typed in the test and the engine modules."""
    inputs = live.LiveInputs(first_seed=201, n_seeds=2, **case)
    runs = live.run_live(inputs)
    assert len(runs) == 6
    for seed in (201, 202):
        data = transactions.generate_transactions(
            count=case["count"], fx_rate=case["fx_rate"], seed=seed,
            n_banks=case["n_banks"], arrival=case["arrival"],
        )  # fmt: skip
        params = SimulationParams(
            seed=seed, initial_usd=case["initial_usd"], initial_jpy=case["initial_jpy"],
            delay_seconds=case["delay_seconds"], failure_probability=case["failure_probability"],
            cutoff_seconds=3600, n_banks=case["n_banks"],
        )  # fmt: skip
        for model in Model:
            results, ledger = simulator.run_model(data, model, params)
            expected = metrics.calculate_metrics(results, data, params, ledger)
            row = cell(runs, seed, model.value)
            for key, value in expected.items():
                if math.isnan(value):
                    assert math.isnan(row[key]), key
                else:
                    assert row[key] == value, key
            assert row["fx_rate"] == case["fx_rate"]
            assert row["n_banks"] == case["n_banks"]


def test_direct_cases_are_really_different_from_defaults() -> None:
    """Guard: the non-default case must differ from the default-like case in its output."""
    values = {}
    for param in DIRECT_CASES:
        case = param.values[0]
        runs = live.run_live(live.LiveInputs(first_seed=201, n_seeds=1, **case))
        values[param.id] = runs["peak_liquidity_proxy_usd"].tolist()
    assert values["all_non_default"] != values["default_like"]
    assert values["jpy_0.0625_failure_0"] != values["default_like"]


def test_run_live_has_one_row_per_seed_and_model_and_fx_rate() -> None:
    runs = live.run_live(make_inputs())
    assert len(runs) == 2 * 3
    assert set(runs["seed"]) == {201, 202}
    assert (runs["fx_rate"] == 150.0).all()
    assert (runs["experiment"] == live.LIVE_EXPERIMENT).all()


def test_run_live_is_deterministic() -> None:
    inputs = make_inputs()
    pd.testing.assert_frame_equal(live.run_live(inputs), live.run_live(inputs))


def test_higher_failure_probability_gives_more_failures_and_partials() -> None:
    low = live.run_live(make_inputs(failure_probability=0.0))
    high = live.run_live(make_inputs(failure_probability=0.2))
    assert low["n_technical_failure"].sum() == 0
    assert high["n_technical_failure"].sum() > 0


def test_longer_delay_changes_settlement_time() -> None:
    short = live.run_live(make_inputs(delay_seconds=0.0))
    long = live.run_live(make_inputs(delay_seconds=300.0))
    column = "average_settlement_time_seconds"
    assert cell(short, FIRST, "sequential")[column] != cell(long, FIRST, "sequential")[column]
    assert (long["delay_seconds"] == 300.0).all()


def test_fx_rate_changes_the_run() -> None:
    """With ample JPY the fx rate changes nothing but the label; under JPY stress it matters."""
    stressed = make_inputs()
    stressed = dataclasses.replace(stressed, initial_jpy=stressed.initial_jpy * 0.0125)
    base = live.run_live(stressed)
    other = live.run_live(dataclasses.replace(stressed, fx_rate=100.0))
    assert (other["fx_rate"] == 100.0).all()
    assert other["n_insufficient_funds"].sum() < base["n_insufficient_funds"].sum()


def test_count_changes_the_run() -> None:
    base = live.run_live(make_inputs())
    other = live.run_live(make_inputs(count=200))
    assert (other["count"] == 200).all()
    assert (other["n_settled"] + other["n_partial"] + other["n_failed"] == 200).all()
    assert (base["n_settled"] + base["n_partial"] + base["n_failed"] == 100).all()


def test_low_jpy_creates_insufficient_funds() -> None:
    ample = live.run_live(make_inputs())
    low = live.run_live(dataclasses.replace(make_inputs(), initial_jpy=make_inputs().initial_jpy * 0.0125))
    assert ample["n_insufficient_funds"].sum() == 0
    assert low["n_insufficient_funds"].sum() > 0
    assert (low["initial_jpy"] < ample["initial_jpy"]).all()


def test_transactions_generated_once_per_seed_and_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    received: list[tuple[int, int]] = []  # (seed, id of the DataFrame)
    real_generate = transactions.generate_transactions
    real_run_one = experiments.run_one

    def spy_generate(*args: object, **kwargs: object) -> pd.DataFrame:
        calls.append(int(kwargs["seed"]))
        return real_generate(*args, **kwargs)

    def spy_run_one(data: pd.DataFrame, model: Model, condition: object, seed: int, *rest: object) -> dict:
        received.append((seed, id(data)))
        return real_run_one(data, model, condition, seed, *rest)

    monkeypatch.setattr(transactions, "generate_transactions", spy_generate)
    monkeypatch.setattr(experiments, "run_one", spy_run_one)
    live.run_live(make_inputs())
    assert calls == [201, 202]
    assert len(received) == 6
    for seed in (201, 202):
        ids = {identity for s, identity in received if s == seed}
        assert len(ids) == 1  # all three models got the very same DataFrame


# ------------------------------------------------------------------ model rules

def test_atomic_has_no_partial_and_no_exposure_even_under_stress() -> None:
    stressed = dataclasses.replace(make_inputs(failure_probability=0.2),
                                   initial_jpy=make_inputs().initial_jpy * 0.0125)  # fmt: skip
    runs = live.run_live(stressed)
    atomic = runs[runs["model"] == "atomic"]
    assert (atomic["n_partial"] == 0).all()
    assert (atomic["principal_exposure_usd"] == 0).all()


# ------------------------------------------------------------------ inputs

def test_single_model_selection() -> None:
    runs = live.run_live(make_inputs(models=("prefunded",)))
    assert set(runs["model"]) == {"prefunded"}
    assert len(runs) == 2


def test_models_run_in_fixed_order_whatever_the_selection_order() -> None:
    runs = live.run_live(make_inputs(models=("atomic", "sequential")))
    assert list(runs["model"][:2]) == ["sequential", "atomic"]


@pytest.mark.parametrize("change", [
    {"models": ()},
    {"models": ("bitcoin",)},
    {"models": ("atomic", "atomic")},
    {"n_seeds": 0},
    {"n_seeds": 31},
    {"n_seeds": 2.5},
    {"first_seed": -1},
    {"failure_probability": -0.1},
    {"n_banks": 1},
])
def test_invalid_inputs_raise_value_error(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        live.run_live(make_inputs(**change))


def test_default_inputs_come_from_calibration_file() -> None:
    usd, jpy = experiments.read_reference(RESULTS / "calibration.csv")
    inputs = live.default_inputs()
    assert (inputs.initial_usd, inputs.initial_jpy) == (usd, jpy)
    assert inputs.count == experiments.COUNT


def snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    """File name -> (mtime_ns, size) for every file under a folder."""
    return {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in folder.rglob("*") if p.is_file()}


def test_run_live_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("run_live tried to write a file")

    before = snapshot(RESULTS)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pd.DataFrame, "to_csv", refuse)
    monkeypatch.setattr(experiments, "append_log", refuse)
    live.run_live(make_inputs())
    assert snapshot(RESULTS) == before
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------------ tables

def test_summarize_live_matches_manual_pandas() -> None:
    runs = live.run_live(make_inputs(failure_probability=0.05))
    summary = live.summarize_live(runs)
    for (model, metric), row in summary.set_index(["model", "metric"]).iterrows():
        values = runs[runs["model"] == model][metric].astype(float)
        assert row["n_seeds"] == 2
        assert row["n_valid"] == values.notna().sum()
        for name, expected in (("mean", values.mean()), ("min", values.min()), ("max", values.max())):
            if math.isnan(expected):
                assert math.isnan(row[name])
            else:
                assert row[name] == expected
    assert set(summary["metric"]) == {m for m, _ in live.METRIC_LABELS}


def test_model_a_gross_prefunding_stays_nan() -> None:
    summary = live.summarize_live(live.run_live(make_inputs()))
    row = summary[(summary["model"] == "sequential") & (summary["metric"] == "gross_prefunding_usd")].iloc[0]
    assert row["n_valid"] == 0
    assert math.isnan(row["mean"])


def test_summary_table_shape_and_values() -> None:
    summary = live.summarize_live(live.run_live(make_inputs(models=("sequential", "atomic"))))
    table = live.summary_table(summary)
    assert list(table.columns) == ["Metric", MODEL_NAMES["sequential"], MODEL_NAMES["atomic"]]
    assert list(table["Metric"]) == [label for _, label in live.METRIC_LABELS]
    expected = summary[(summary["model"] == "atomic") & (summary["metric"] == "success_rate")].iloc[0]["mean"]
    assert table.loc[table["Metric"] == "Success rate", MODEL_NAMES["atomic"]].iloc[0] == expected


def test_reason_table_sums_over_seeds() -> None:
    runs = live.run_live(make_inputs(failure_probability=0.2))
    table = live.reason_table(runs).set_index("Model")
    for model in Model:
        group = runs[runs["model"] == model.value]
        row = table.loc[MODEL_NAMES[model.value]]
        assert row["settled"] == group["n_settled"].sum()
        assert row["partial"] == group["n_partial"].sum()
        assert row["failed"] == group["n_failed"].sum()
        assert row["settled"] + row["partial"] + row["failed"] == 2 * 100


# ------------------------------------------------------------------ figure

def fake_summary(nan_exposure_model: str | None = None) -> pd.DataFrame:
    """A small hand-made summary, so the test knows every expected number."""
    rows = []
    for index, model in enumerate(["sequential", "prefunded", "atomic"]):
        for metric, _ in live.METRIC_LABELS:
            mean = 10.0 * (index + 1)
            rows.append({"model": model, "metric": metric, "n_seeds": 3, "n_valid": 3,
                         "mean": mean, "min": mean - 1, "max": mean + 2})  # fmt: skip
    summary = pd.DataFrame(rows)
    if nan_exposure_model:
        mask = (summary["model"] == nan_exposure_model) & (summary["metric"] == "principal_exposure_usd")
        summary.loc[mask, ["n_valid", "mean", "min", "max"]] = [0, math.nan, math.nan, math.nan]
    return summary


def panel_traces(fig: object, axis: str) -> list:
    return [t for t in fig.data if t.xaxis == axis]


def test_figure_bars_equal_summary_means_and_colors() -> None:
    summary = live.summarize_live(live.run_live(make_inputs(failure_probability=0.05)))
    fig = live.build_live_figure(summary)
    assert "Live exploratory run" in fig.layout.title.text and "2 seeds" in fig.layout.title.text
    for trace, model in zip(panel_traces(fig, "x"), ["sequential", "prefunded", "atomic"]):
        means = [summary[(summary["model"] == model) & (summary["metric"] == m)].iloc[0]["mean"]
                 for m in ("success_rate", "partial_rate", "failure_rate")]  # fmt: skip
        assert list(trace.y) == means
        assert trace.marker.color == MODEL_COLORS[model]
    for axis, metric in (("x2", "principal_exposure_usd"), ("x3", "peak_liquidity_proxy_usd")):
        for trace, model in zip(panel_traces(fig, axis), ["sequential", "prefunded", "atomic"]):
            row = summary[(summary["model"] == model) & (summary["metric"] == metric)].iloc[0]
            assert list(trace.y) == [row["mean"]]
            assert trace.marker.color == MODEL_COLORS[model]
            assert trace.error_y.arrayminus[0] == pytest.approx(row["mean"] - row["min"])
            assert trace.error_y.array[0] == pytest.approx(row["max"] - row["mean"])


def test_figure_whiskers_on_hand_made_summary() -> None:
    fig = live.build_live_figure(fake_summary())
    first = panel_traces(fig, "x2")[0]
    assert list(first.y) == [10.0]
    assert (first.error_y.arrayminus[0], first.error_y.array[0]) == (1.0, 2.0)


def test_figure_nan_gives_no_bar() -> None:
    fig = live.build_live_figure(fake_summary(nan_exposure_model="prefunded"))
    nan_trace = panel_traces(fig, "x2")[1]
    assert list(nan_trace.y) == [None]  # nothing is drawn, and it is not a 0 bar
    assert 0 not in list(nan_trace.y)


def test_figure_shows_only_selected_models() -> None:
    summary = live.summarize_live(live.run_live(make_inputs(models=("atomic",))))
    fig = live.build_live_figure(summary)
    assert {t.name for t in fig.data} == {MODEL_NAMES["atomic"]}


# ------------------------------------------------------------------ verdicts

def test_verdicts_equal_csv_row_by_row() -> None:
    main, h3 = live.load_verdict_tables()
    csv_main = pd.read_csv(RESULTS / "verdicts.csv")
    overall = csv_main[csv_main["role"] == "overall"].set_index("hypothesis")
    assert list(main["hypothesis"]) == ["H1a", "H1b", "H2", "H4a", "H4b"]
    for row in main.itertuples():
        expected = overall.loc[row.hypothesis, "verdict"]
        if pd.isna(expected):
            assert row.hypothesis == "H1a"
            assert "no verdict" in row.verdict
        else:
            assert row.verdict == expected
    csv_h3 = pd.read_csv(RESULTS / "h3_verdicts.csv")
    csv_h3 = csv_h3[csv_h3["role"] == "decides"].reset_index(drop=True)
    assert len(h3) == 9
    for column in ("factor", "model", "low_level", "high_level", "verdict", "n_seeds_equal", "note"):
        assert list(h3[column].astype(str)) == list(csv_h3[column].astype(str)), column


def test_verdict_values_secondary_check() -> None:
    main, h3 = live.load_verdict_tables()
    assert dict(zip(main["hypothesis"], main["verdict"]))["H4a"] == "not supported"
    assert sorted(h3["verdict"].unique()) == ["inconclusive", "not supported"]


def test_every_row_has_a_caveat_and_model_rules_where_required() -> None:
    main, h3 = live.load_verdict_tables()
    assert (main["caveat"].str.len() > 0).all()
    assert (h3["caveat"].str.len() > 0).all()
    assert "model rules" in main[main["hypothesis"] == "H4a"]["caveat"].iloc[0]
    arrival = h3[h3["factor"] == "arrival"].set_index("model")
    assert "model rules" in arrival.loc["sequential", "caveat"]
    assert "model rules" in arrival.loc["atomic", "caveat"]
    assert "model rules" not in arrival.loc["prefunded", "caveat"]
    assert "model rules" not in h3[h3["factor"] != "arrival"]["caveat"].iloc[0]
    assert "all 150 (level, seed) pairs" in main[main["hypothesis"] == "H4a"]["caveat"].iloc[0]


def test_banks_caveat_only_on_banks_rows() -> None:
    _, h3 = live.load_verdict_tables()
    has_note = h3["caveat"].str.contains("adding banks also adds total liquidity")
    assert list(h3[has_note]["factor"].unique()) == ["banks"]
    assert has_note.sum() == (h3["factor"] == "banks").sum() == 3


def test_missing_verdict_files_raise_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        live.load_verdict_tables(tmp_path)
    (tmp_path / "verdicts.csv").write_text("hypothesis,role\nH1a,overall\n")
    with pytest.raises(ValueError, match="column"):
        live.load_verdict_tables(tmp_path)


# ------------------------------------------------------------------ display formats


@pytest.mark.parametrize(
    ("metric", "value", "text"),
    [
        ("success_rate", 0.9895, "99.0%"),
        ("partial_rate", 0.0, "0.0%"),
        ("principal_exposure_usd", 2596140.8, "2,596,141"),
        ("peak_liquidity_proxy_usd", 0.0, "0"),
        ("average_settlement_time_seconds", 60.0, "60.0"),
        ("liquidity_utilization", 0.5, "50.0%"),
        ("gross_prefunding_usd", float("nan"), "n/a"),
    ],
)
def test_format_value(metric: str, value: float, text: str) -> None:
    assert live.format_value(metric, value) == text


def test_every_summary_metric_has_a_format() -> None:
    assert set(live.METRIC_FORMATS) == {metric for metric, _ in live.METRIC_LABELS}
    assert {metric for metric, _ in live.HEADLINE_METRICS} <= set(live.METRIC_FORMATS)


def test_headline_rows_equal_summary_means() -> None:
    summary = live.summarize_live(live.run_live(make_inputs(models=("atomic", "sequential"))))
    rows = live.headline_rows(summary)
    assert [row["model"] for row in rows] == ["sequential", "atomic"]
    for row in rows:
        assert row["name"] == MODEL_NAMES[row["model"]]
        for metric, _ in live.HEADLINE_METRICS:
            cell = summary[(summary["model"] == row["model"]) & (summary["metric"] == metric)].iloc[0]
            assert row["values"][metric] == cell["mean"]
            assert row["text"][metric] == live.format_value(metric, cell["mean"])


def test_headline_nan_is_not_shown_as_zero() -> None:
    summary = pd.DataFrame(
        [{"model": "sequential", "metric": metric, "n_seeds": 1, "n_valid": 0, "mean": float("nan"),
          "min": float("nan"), "max": float("nan")} for metric, _ in live.METRIC_LABELS]
    )  # fmt: skip
    row = live.headline_rows(summary)[0]
    assert set(row["text"].values()) == {"n/a"}
