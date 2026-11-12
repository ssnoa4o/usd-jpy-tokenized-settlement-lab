"""Dashboard tests with Streamlit's AppTest (Day 15). Seeds 201 and above only."""

import dataclasses
import math
from html import escape
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import experiments, live, metrics, simulator, transactions
from src.figures import MODEL_NAMES

APP_FILE = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def new_app() -> AppTest:
    """Start the app (first run)."""
    return AppTest.from_file(APP_FILE, default_timeout=60).run()


def small_run(app: AppTest, failure_pct: int = 1) -> AppTest:
    """Set small inputs (volume 100, seeds 201-202) and press Run Simulation."""
    app.number_input(key="first_seed").set_value(201)
    app.slider(key="n_seeds").set_value(2)
    app.number_input(key="count").set_value(100)
    app.slider(key="failure_pct").set_value(failure_pct)
    app.button(key="run").click()
    return app.run()


def texts(elements: object) -> str:
    """All values of an element list as one string."""
    return "\n".join(str(e.value) for e in elements)


def test_app_starts_with_title_and_info_and_no_results() -> None:
    app = new_app()
    assert not app.exception
    assert app.title[0].value == "USD/JPY Tokenized Settlement Lab"
    assert any("Independent research prototype" in c.value for c in app.caption)
    assert any("press Run Simulation" in i.value for i in app.info)
    # The only table before a run is the recorded verdict tables (tab 2), not a live summary.
    assert all("Metric" not in df.value.columns for df in app.dataframe)


def test_run_shows_summary_equal_to_the_engine() -> None:
    app = small_run(new_app())
    assert not app.exception
    assert not app.error
    shown = app.dataframe[0].value
    inputs = dataclasses.replace(live.default_inputs(), count=100, n_seeds=2, first_seed=201)
    expected = live.summary_table(live.summarize_live(live.run_live(inputs)))
    pd.testing.assert_frame_equal(shown.reset_index(drop=True), expected.reset_index(drop=True))
    assert list(shown.columns) == ["Metric", *MODEL_NAMES.values()]
    # Independent check: recompute one cell straight from the run rows.
    runs = live.run_live(inputs)
    atomic_mean = runs[runs["model"] == "atomic"]["success_rate"].mean()
    shown_value = shown.loc[shown["Metric"] == "Success rate", MODEL_NAMES["atomic"]].iloc[0]
    assert shown_value == atomic_mean
    markdown = texts(app.markdown)
    for note in live.LIVE_NOTES:
        assert escape(note) in markdown
    # The comparison at the top shows the same mean, formatted (display only).
    assert f"<td>{live.format_value('success_rate', atomic_mean)}</td>" in markdown
    assert "Outcome mix" in markdown


def test_changed_inputs_warn_and_rerun_updates_results() -> None:
    app = small_run(new_app(), failure_pct=1)
    before = app.dataframe[0].value.copy()
    assert not any("inputs have changed" in w.value for w in app.warning)
    app.slider(key="failure_pct").set_value(5)
    app.run()
    assert any("inputs have changed" in w.value for w in app.warning)
    app.button(key="run").click()
    app.run()
    assert not app.exception
    assert not any("inputs have changed" in w.value for w in app.warning)
    assert not app.dataframe[0].value.equals(before)


def test_no_model_selected_gives_error_not_exception() -> None:
    app = new_app()
    app.multiselect(key="models").set_value([])
    app.button(key="run").click()
    app.run()
    assert not app.exception
    assert any("at least one" in e.value for e in app.error)
    assert any("press Run Simulation" in i.value for i in app.info)


def test_recorded_tab_shows_caveats_and_general_note() -> None:
    app = new_app()
    assert not app.exception
    assert not app.error
    markdown = texts(app.markdown)
    assert "model rules" in markdown
    assert live.VERDICT_NOTES["H4a"] in markdown
    assert "- **H4a**: Success Rate of A equals that of C" in markdown
    assert "may follow from the model rules" in markdown
    assert live.MODEL_RULES_NOTE in markdown
    assert any(live.GENERAL_VERDICT_NOTE == c.value for c in app.caption)
    verdicts = [df.value for df in app.dataframe if "caveat" in df.value.columns]
    assert len(verdicts) == 2


def test_limits_tab_mentions_key_limits() -> None:
    markdown = texts(AppTest.from_file(APP_FILE, default_timeout=60).run().markdown)
    assert "synthetic" in markdown.lower()
    assert "Not endorsed" in markdown
    assert "research/findings.md" in markdown


def independent_means(case: dict[str, object], seeds: list[int]) -> dict[str, dict[str, float]]:
    """Mean metrics per model from direct engine calls (no src.live), typed parameters."""
    rows: dict[str, list[dict[str, float]]] = {"sequential": [], "prefunded": [], "atomic": []}
    for seed in seeds:
        data = transactions.generate_transactions(
            count=case["count"], fx_rate=case["fx_rate"], seed=seed,
            n_banks=case["n_banks"], arrival=case["arrival"],
        )  # fmt: skip
        params = simulator.SimulationParams(
            seed=seed, initial_usd=case["usd"], initial_jpy=case["jpy"],
            delay_seconds=case["delay"], failure_probability=case["failure"],
            cutoff_seconds=3600, n_banks=case["n_banks"],
        )  # fmt: skip
        for model in simulator.Model:
            results, ledger = simulator.run_model(data, model, params)
            rows[model.value].append(metrics.calculate_metrics(results, data, params, ledger))
    return {m: pd.DataFrame(r).mean().to_dict() for m, r in rows.items()}


def test_every_input_reaches_the_engine() -> None:
    """Set every widget to a non-default value; compare displayed cells with an independent calculation."""
    case = {"count": 300, "fx_rate": 120.0, "n_banks": 4, "arrival": "burst", "failure": 0.05,
            "delay": 30.0, "usd": 50_000_000, "jpy": 3_750_000_000}  # fmt: skip
    app = new_app()
    app.number_input(key="fx_rate").set_value(120.0)
    app.number_input(key="count").set_value(300)
    app.slider(key="n_banks").set_value(4)
    app.selectbox(key="arrival").set_value("burst")
    app.number_input(key="usd_mult").set_value(0.5)
    app.number_input(key="jpy_mult").set_value(0.25)
    app.slider(key="failure_pct").set_value(5)
    app.slider(key="delay").set_value(30)
    app.number_input(key="first_seed").set_value(201)
    app.slider(key="n_seeds").set_value(2)
    app.button(key="run").click()
    app.run()
    assert not app.exception
    assert not app.error
    shown = app.dataframe[0].value.set_index("Metric")
    expected = independent_means(case, [201, 202])
    labels = {"Success rate": "success_rate", "Principal exposure (USD)": "principal_exposure_usd",
              "Peak liquidity proxy (USD)": "peak_liquidity_proxy_usd",
              "Average settlement time (s)": "average_settlement_time_seconds"}  # fmt: skip
    for label, metric in labels.items():
        for model, name in MODEL_NAMES.items():
            want, got = expected[model][metric], shown.loc[label, name]
            assert got == pytest.approx(want, rel=1e-9, abs=1e-9) or (math.isnan(want) and math.isnan(got))
    conditions = texts(app.markdown)
    assert "4 banks, burst arrival" in conditions and "<dd>201-202 (2 seeds)</dd>" in conditions
    assert "<dd>120</dd>" in conditions and "<dd>50,000,000</dd>" in conditions
    assert "<dd>3,750,000,000</dd>" in conditions and "<dd>30 s</dd>" in conditions and "<dd>5%</dd>" in conditions


def run_and_compare(set_inputs: dict[str, object], case: dict[str, object]) -> dict[str, dict[str, float]]:
    """Set widgets, run, compare the Success rate and Peak liquidity cells with an independent calculation."""
    app = new_app()
    for key, value in set_inputs.items():
        widget = app.number_input if key in ("fx_rate", "usd_mult", "jpy_mult", "first_seed", "count") else app.slider
        widget(key=key).set_value(value)
    app.number_input(key="first_seed").set_value(201)
    app.slider(key="n_seeds").set_value(2)
    app.button(key="run").click()
    app.run()
    assert not app.exception
    shown = app.dataframe[0].value.set_index("Metric")
    expected = independent_means(case, [201, 202])
    for model, name in MODEL_NAMES.items():
        assert shown.loc["Success rate", name] == pytest.approx(expected[model]["success_rate"], abs=1e-12)
        assert shown.loc["Peak liquidity proxy (USD)", name] == pytest.approx(
            expected[model]["peak_liquidity_proxy_usd"], rel=1e-9)  # fmt: skip
    return expected


def test_low_jpy_multiplier_and_fx_reach_the_engine() -> None:
    """JPY multiplier 0.0625 at failure 0 and fx 120: JPY shortages, where fx matters too."""
    case = {"count": 500, "fx_rate": 120.0, "n_banks": 2, "arrival": "sequential", "failure": 0.0,
            "delay": 60.0, "usd": 100_000_000, "jpy": 937_500_000}  # fmt: skip
    expected = run_and_compare({"fx_rate": 120.0, "jpy_mult": 0.0625, "failure_pct": 0}, case)
    assert expected["sequential"]["success_rate"] < 1.0  # the stress is real, not a no-op


def test_low_usd_multiplier_reaches_the_engine() -> None:
    """USD multiplier 0.02: USD shortages (USD is the binding currency here)."""
    case = {"count": 500, "fx_rate": 150.0, "n_banks": 2, "arrival": "sequential", "failure": 0.0,
            "delay": 60.0, "usd": 2_000_000, "jpy": 15_000_000_000}  # fmt: skip
    expected = run_and_compare({"usd_mult": 0.02, "failure_pct": 0}, case)
    assert expected["sequential"]["success_rate"] < 1.0


def test_empty_model_selection_message_is_specific() -> None:
    app = new_app()
    app.multiselect(key="models").set_value([])
    app.button(key="run").click()
    app.run()
    assert [e.value for e in app.error] == ["Select at least one settlement model."]


# ------------------------------------------------------------------ scenario buttons


def widget_values(app: AppTest) -> dict[str, object]:
    """Current value of every sidebar input."""
    return {
        "fx_rate": app.number_input(key="fx_rate").value, "count": app.number_input(key="count").value,
        "usd_mult": app.number_input(key="usd_mult").value, "jpy_mult": app.number_input(key="jpy_mult").value,
        "failure_pct": app.slider(key="failure_pct").value, "delay": app.slider(key="delay").value,
        "n_banks": app.slider(key="n_banks").value, "arrival": app.selectbox(key="arrival").value,
        "first_seed": app.number_input(key="first_seed").value, "n_seeds": app.slider(key="n_seeds").value,
        "models": app.multiselect(key="models").value,
    }  # fmt: skip


def scenario_button(app: AppTest, label: str) -> object:
    """The scenario button with this label."""
    return next(b for b in app.button if b.label == label)


def test_scenarios_change_one_input_using_recorded_levels() -> None:
    levels = experiments.read_stress_levels(experiments.RESULTS_DIR / experiments.CALIBRATION_FILE)
    app = new_app()
    baseline = widget_values(app)
    assert baseline["fx_rate"] == experiments.FX_RATE and baseline["count"] == experiments.COUNT
    assert baseline["delay"] == experiments.DELAY_SECONDS and baseline["failure_pct"] == 1
    assert baseline["usd_mult"] == 1.0 and baseline["jpy_mult"] == 1.0
    expected = {
        "JPY shortage": {"jpy_mult": levels.lower_multipliers[1]},
        "High failure": {"failure_pct": 5},
        "Long delay": {"delay": 300},
    }
    assert expected["JPY shortage"]["jpy_mult"] in levels.lower_multipliers
    assert 0.05 in experiments.EXP4_FAILURE_LEVELS and 300 in experiments.EXP4_DELAY_LEVELS
    for label, change in expected.items():
        scenario_button(app, label).click()
        app.run()
        assert not app.exception
        assert widget_values(app) == {**baseline, **change}  # one change, everything else back to baseline
        assert "runs" not in app.session_state  # a scenario does not run the engine by itself
    scenario_button(app, "Baseline").click()
    app.run()
    assert widget_values(app) == baseline


def test_scenario_then_run_uses_the_scenario_inputs() -> None:
    app = new_app()
    scenario_button(app, "JPY shortage").click()
    app.run()
    app.number_input(key="first_seed").set_value(201)
    app.slider(key="n_seeds").set_value(2)
    app.button(key="run").click()
    app.run()
    assert not app.exception and not app.error
    case = {"count": 500, "fx_rate": 150.0, "n_banks": 2, "arrival": "sequential", "failure": 0.01,
            "delay": 60.0, "usd": 100_000_000, "jpy": 937_500_000}  # fmt: skip
    expected = independent_means(case, [201, 202])
    shown = app.dataframe[0].value.set_index("Metric")
    for model, name in MODEL_NAMES.items():
        assert shown.loc["Partial rate", name] == pytest.approx(expected[model]["partial_rate"], abs=1e-12)
    assert expected["sequential"]["partial_rate"] > expected["atomic"]["partial_rate"]
    assert "<dd>937,500,000</dd>" in texts(app.markdown)
