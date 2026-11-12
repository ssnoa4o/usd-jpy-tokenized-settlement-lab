"""Tests for src/figures.py. Small hand-made tables; no simulation. One optional PNG test."""

from pathlib import Path

import pandas as pd
import pytest

from src import figures
from src.figures import FigureDataError, FigureMeta

MODELS = ["sequential", "prefunded", "atomic"]
SEED_ROWS = [1, 2, 3]


CELL_IDS: dict[tuple[str, str, str, str], int] = {}


def cell_value(experiment: str, condition: str, model: str, metric: str) -> tuple[float, float, float]:
    """Distinct made-up (mean, min, max) for every cell, so a wrong pick is noticed.

    Each new cell gets the next number (1, 2, 3, ...), so no two cells share a value and nothing
    depends on PYTHONHASHSEED.
    """
    key = (experiment, condition, model, metric)
    base = 100.0 + 5.0 * CELL_IDS.setdefault(key, len(CELL_IDS) + 1)
    return base, base - 1.5, base + 2.5


def make_table(experiment: str, conditions: list[str], metrics: list[str], n_seeds: int = 3, nan_cells=()) -> pd.DataFrame:
    """Summary-style table for one experiment."""
    rows = []
    for condition in conditions:
        for model in MODELS:
            for metric in metrics:
                mean, low, high = cell_value(experiment, condition, model, metric)
                valid = n_seeds
                if (condition, model, metric) in nan_cells:
                    mean = low = high = float("nan")
                    valid = 0
                rows.append({"experiment": experiment, "condition": condition, "model": model, "metric": metric,
                             "n_seeds": n_seeds, "n_valid": valid, "mean": mean, "min": low, "max": high})
    return pd.DataFrame(rows)


def stress_table(n_seeds: int = 3, **kwargs) -> pd.DataFrame:
    """Stress-style table with all experiments used by F2, F3 and F4."""
    parts = [
        make_table(figures.F2_EXPERIMENT, figures.F2_CONDITIONS,
                   [m for m, _ in figures.F2_PANELS] + [figures.F6_METRIC], n_seeds=n_seeds, **kwargs),
        make_table(figures.F3_FAILURE_EXPERIMENT, figures.F3_FAILURE_CONDITIONS,
                   [m for m, _ in figures.F3_ROWS] + [figures.F7_METRIC], n_seeds=n_seeds),
        make_table(figures.F3_DELAY_EXPERIMENT, figures.F3_DELAY_CONDITIONS,
                   [m for m, _ in figures.F3_ROWS] + [figures.F7_METRIC], n_seeds=n_seeds),
        make_table(figures.F4_EXPERIMENT, figures.F4_CONDITIONS, [figures.F4_METRIC], n_seeds=n_seeds),
    ]
    return pd.concat(parts, ignore_index=True)


def summary_table(nan_a_gross: bool = True) -> pd.DataFrame:
    """Summary-style table for F1."""
    nan = [(figures.F1_CONDITION, "sequential", "gross_prefunding_usd")] if nan_a_gross else []
    return make_table(figures.F1_EXPERIMENT, [figures.F1_CONDITION], [m for m, _, _ in figures.F1_PANELS], nan_cells=nan)


def lstar_table() -> pd.DataFrame:
    """L* rows: 2 factor levels, 3 models, 4 seeds."""
    rows = []
    for factor, level in [("baseline", "baseline"), ("volume", "100")]:
        for model in MODELS:
            for seed in range(1, 5):
                lstar = 1.0 if (seed == 1 or model == "prefunded") else 0.0625
                rows.append({"factor": factor, "level": level, "model": model, "seed": seed, "lstar": lstar,
                             "lstar_rank": 0, "censored_low": False, "not_reached": False})
    return pd.DataFrame(rows)


GRID = (0.0125, 0.03125, 0.0625, 0.09375, 1.0)
META = FigureMeta(seeds="1-3", note="", shared_delay=60.0, grid=GRID)


def all_figures() -> dict[str, object]:
    stress = stress_table()
    return {
        "f1": figures.build_f1(summary_table(), META), "f2": figures.build_f2(stress, META),
        "f3": figures.build_f3(stress, META), "f4": figures.build_f4(stress, META),
        "f5": figures.build_f5(lstar_table(), META),
        "f6": figures.build_f6(stress, META),
        "f7": figures.build_f7(stress, META),
    }


def traces_by_model(fig, model: str) -> list:
    return [t for t in fig.data if t.name == figures.MODEL_NAMES[model]]


def text_of(fig) -> str:
    """All visible text of a figure: title, subtitle, annotations and axis titles."""
    parts = [fig.layout.title.text, fig.layout.title.subtitle.text]
    parts += [a.text for a in fig.layout.annotations]
    for key in fig.layout:
        if key.startswith(("xaxis", "yaxis")):
            parts.append(fig.layout[key].title.text or "")
            parts += list(fig.layout[key].ticktext or [])
    return " | ".join(p for p in parts if p)


# ------------------------------------------------------------ values equal the CSV

def test_f1_values_and_error_bars_match_table():
    table = summary_table()
    fig = figures.build_f1(table, META)
    for col, (metric, _, _) in enumerate(figures.F1_PANELS):
        for model in MODELS:
            mean, low, high = cell_value(figures.F1_EXPERIMENT, "baseline", model, metric)
            if metric == "gross_prefunding_usd" and model == "sequential":
                continue
            bar = [t for t in traces_by_model(fig, model) if t.xaxis == f"x{col + 1}" or (col == 0 and t.xaxis == "x")][0]
            assert bar.y[0] == pytest.approx(mean)
            assert bar.error_y.array[0] == pytest.approx(high - mean)
            assert bar.error_y.arrayminus[0] == pytest.approx(mean - low)


def test_f1_nan_is_not_drawn_as_zero():
    fig = figures.build_f1(summary_table(), META)
    gross_a = [t for t in traces_by_model(fig, "sequential") if t.xaxis == "x2"][0]
    assert pd.isna(gross_a.y[0])
    assert "n/a" in text_of(fig)


def test_f1_reads_the_baseline_experiment_only():
    other = make_table("exp3_liquidity", ["baseline"], [m for m, _, _ in figures.F1_PANELS])
    with pytest.raises(FigureDataError, match="exp1_baseline"):
        figures.build_f1(other, META)


def test_f2_lines_match_table_and_success_has_no_partial():
    stress = stress_table()
    fig = figures.build_f2(stress, META)
    for model in MODELS:
        traces = traces_by_model(fig, model)
        assert len(traces) == 3
        for trace, (metric, _) in zip(traces, figures.F2_PANELS, strict=True):
            for i, condition in enumerate(figures.F2_CONDITIONS):
                mean, low, high = cell_value(figures.F2_EXPERIMENT, condition, model, metric)
                assert trace.y[i] == pytest.approx(mean)
                assert trace.error_y.array[i] == pytest.approx(high - mean)
                assert trace.error_y.arrayminus[i] == pytest.approx(mean - low)
        success, partial = traces[0], traces[1]
        for i, condition in enumerate(figures.F2_CONDITIONS):
            success_mean = cell_value(figures.F2_EXPERIMENT, condition, model, "success_rate")[0]
            partial_mean = cell_value(figures.F2_EXPERIMENT, condition, model, "partial_rate")[0]
            assert success.y[i] == pytest.approx(success_mean)
            assert success.y[i] != pytest.approx(success_mean + partial_mean)
        assert list(success.x) == ["1", "0.09375", "0.0625", "0.03125", "0.0125"]


def test_f3_every_trace_matches_table():
    """18 traces in the order: sweep (failure, delay), row (3 metrics), model (A, B, C)."""
    fig = figures.build_f3(stress_table(), META)
    sweeps = [
        ("exp4_failure", ["failure_0", "failure_0.01", "failure_0.05"], [0.0, 0.01, 0.05], "exp4_failure"),
        ("delay", ["delay_0", "failure_0.01", "delay_300"], [0.0, 60.0, 300.0], None),
    ]
    metrics = ["principal_exposure_usd", "principal_exposure_usd_seconds", "success_rate"]
    expected = []
    for _, conditions, x, _ in sweeps:
        for metric in metrics:
            for model in MODELS:
                expected.append((conditions, x, metric, model))
    assert len(fig.data) == len(expected) == 18
    for trace, (conditions, x, metric, model) in zip(fig.data, expected, strict=True):
        assert trace.name == figures.MODEL_NAMES[model]
        assert list(trace.x) == x
        for i, condition in enumerate(conditions):
            experiment = {"failure_0.01": "exp4_failure", "delay_0": "exp4_delay", "delay_300": "exp4_delay"}.get(condition, "exp4_failure")
            mean, low, high = cell_value(experiment, condition, model, metric)
            assert trace.y[i] == pytest.approx(mean)
            assert trace.error_y.array[i] == pytest.approx(high - mean)
            assert trace.error_y.arrayminus[i] == pytest.approx(mean - low)


def test_f3_subtitle_text():
    text = text_of(figures.build_f3(stress_table(), FigureMeta(seeds="1-3", note="NOTE", shared_delay=60.0)))
    assert "NOTE" in text
    assert "Lines that overlap are drawn with different markers" in text


def test_f3_requires_shared_delay_in_meta():
    with pytest.raises(FigureDataError, match="shared_delay"):
        figures.build_f3(stress_table(), FigureMeta(seeds="1-3"))


def test_f4_plots_amount_based_exposure_for_h4b_cells():
    stress = stress_table()
    fig = figures.build_f4(stress, META)
    for model in MODELS:
        (trace,) = traces_by_model(fig, model)
        assert list(trace.x) == [0.0, 60.0, 300.0]
        for i, condition in enumerate(figures.F4_CONDITIONS):
            mean, low, high = cell_value("exp4_h4b", condition, model, "principal_exposure_usd")
            assert trace.y[i] == pytest.approx(mean)
            assert trace.error_y.array[i] == pytest.approx(high - mean)
            assert trace.error_y.arrayminus[i] == pytest.approx(mean - low)


def test_f5_counts_every_panel_and_model():
    table = lstar_table()
    fig = figures.build_f5(table, META)
    facets = [("baseline", "baseline"), ("volume", "100")]
    assert len(fig.data) == len(facets) * 3
    expected_x = ["1", "0.0625"]
    for index, (factor, level) in enumerate(facets):
        for j, model in enumerate(MODELS):
            trace = fig.data[index * 3 + j]
            assert trace.name == figures.MODEL_NAMES[model]
            assert list(trace.x) == expected_x
            cell = table[(table["factor"] == factor) & (table["level"] == level) & (table["model"] == model)]
            assert list(trace.y) == [int((cell["lstar"] == 1.0).sum()), int((cell["lstar"] == 0.0625).sum())]
            assert sum(trace.y) == 4
    assert [a.text for a in fig.layout.annotations][:2] == ["baseline", "volume = 100"]


def test_f5_names_grid_values_without_seeds():
    text = text_of(figures.build_f5(lstar_table(), META))
    assert "no seed, not shown: 0.09375, 0.03125, 0.0125" in text
    no_grid = text_of(figures.build_f5(lstar_table(), FigureMeta(seeds="1-4")))
    assert "not shown" not in no_grid


def test_f5_value_outside_grid_raises():
    table = lstar_table()
    table.loc[0, "lstar"] = 0.5
    with pytest.raises(FigureDataError, match="not on the Exp3 grid"):
        figures.build_f5(table, META)


def test_f6_plots_amount_exposure_for_every_model_and_condition():
    fig = figures.build_f6(stress_table(), META)
    assert [t.name for t in fig.data] == [figures.MODEL_NAMES[m] for m in MODELS]
    for model, trace in zip(MODELS, fig.data, strict=True):
        assert list(trace.x) == ["1", "0.09375", "0.0625", "0.03125", "0.0125"]
        for i, condition in enumerate(figures.F2_CONDITIONS):
            mean, low, high = cell_value("exp3_liquidity", condition, model, "principal_exposure_usd")
            assert trace.y[i] == pytest.approx(mean)
            assert trace.error_y.array[i] == pytest.approx(high - mean)
            assert trace.error_y.arrayminus[i] == pytest.approx(mean - low)
    text = text_of(fig)
    assert "Principal exposure, amount (USD)" in text
    assert "categorical" in text and "evenly spaced" in text


def test_f2_panel_titles_are_pinned():
    fig = figures.build_f2(stress_table(), META)
    titles = [a.text for a in fig.layout.annotations if a.text in {t for _, t in figures.F2_PANELS}]
    assert titles == ["Success rate (settled only)", "Partial rate", "Failure rate"]
    assert "partial" not in titles[0].lower()
    assert "categorical" in text_of(fig)


def test_f1_labels_use_the_axis_style():
    text = text_of(figures.build_f1(summary_table(), META))
    assert " bn" not in text and " m<" not in text
    assert figures.short_number(2.57e10) == "25.7B" and figures.short_number(5.51e8) == "551M"
    assert figures.short_number(float("nan")) == "n/a"


# ------------------------------------------------------------ style and labels

def test_model_order_names_and_colours_are_the_same_in_every_figure():
    for name, fig in all_figures().items():
        seen = list(dict.fromkeys(t.name for t in fig.data))
        assert seen == [figures.MODEL_NAMES[m] for m in MODELS], name
        for model in MODELS:
            colours = {t.marker.color for t in traces_by_model(fig, model)}
            assert colours == {figures.MODEL_COLORS[model]}, name
        legend = [t.name for t in fig.data if t.showlegend]
        assert legend == [figures.MODEL_NAMES[m] for m in MODELS], name
    assert len(set(figures.MODEL_COLORS.values())) == 3


def test_overlapping_models_have_different_markers_and_dashes():
    fig = figures.build_f2(stress_table(), META)
    first = {m: traces_by_model(fig, m)[0] for m in MODELS}
    assert len({t.marker.symbol for t in first.values()}) == 3
    assert len({t.line.dash for t in first.values()}) == 3


def test_required_label_text():
    figs = all_figures()
    for name, fig in figs.items():
        text = text_of(fig)
        assert "Synthetic data, own model — independent research prototype" in text, name
        assert "n = " in text and "seeds" in text, name
        assert "conditions:" in text or "condition:" in text, name
    assert "proxy" in text_of(figs["f1"]).lower()
    assert "USD·s" in text_of(figs["f1"])
    assert "n = 3 seeds (seeds 1-3)" in text_of(figs["f1"])
    for name in ["f2", "f4", "f5", "f6"]:
        assert "JPY-only" in text_of(figs[name]), name
    assert "Share of transactions" in text_of(figs["f2"])
    assert "seconds" in text_of(figs["f4"])


def test_titles_state_no_verdict_words():
    for name, fig in all_figures().items():
        text = text_of(fig).lower()
        for word in ["supported", "inconclusive", "eliminat", "proves", "better than"]:
            assert word not in text, (name, word)


def test_figures_are_16_by_9():
    for fig in all_figures().values():
        assert fig.layout.width / fig.layout.height == pytest.approx(16 / 9, rel=0.01)


# ------------------------------------------------------------ guards on data

def test_missing_condition_raises_with_name():
    stress = stress_table()
    stress = stress[stress["condition"] != "jpy_0.0625"]
    with pytest.raises(FigureDataError, match="jpy_0.0625"):
        figures.build_f2(stress, META)


def test_missing_model_and_metric_raise():
    stress = stress_table()
    no_atomic = stress[~((stress["experiment"] == "exp4_h4b") & (stress["model"] == "atomic"))]
    with pytest.raises(FigureDataError, match="atomic"):
        figures.build_f4(no_atomic, META)
    no_metric = stress[stress["metric"] != "partial_rate"]
    with pytest.raises(FigureDataError, match="partial_rate"):
        figures.build_f2(no_metric, META)


def test_missing_column_raises():
    with pytest.raises(FigureDataError, match="max"):
        figures.build_f4(stress_table().drop(columns=["max"]), META)
    with pytest.raises(FigureDataError, match="seed"):
        figures.build_f5(lstar_table().drop(columns=["seed"]), META)


def test_mismatched_n_seeds_raises():
    stress = stress_table()
    mask = (stress["condition"] == "failure_0.05") & (stress["model"] == "atomic")
    stress.loc[mask, "n_seeds"] = 29
    with pytest.raises(FigureDataError, match="n_seeds"):
        figures.build_f3(stress, META)
    mask = (stress["experiment"] == "exp4_delay")
    stress2 = stress_table()
    stress2.loc[mask, "n_seeds"] = 20
    with pytest.raises(FigureDataError, match="n_seeds"):
        figures.build_f3(stress2, META)


def test_duplicate_row_raises():
    stress = stress_table()
    doubled = pd.concat([stress, stress[stress["experiment"] == "exp4_h4b"].head(1)], ignore_index=True)
    with pytest.raises(FigureDataError, match="2 times"):
        figures.build_f4(doubled, META)


def test_format_seeds():
    assert figures.format_seeds([3, 1, 2]) == "1-3"
    assert figures.format_seeds([1, 3]) == "1,3"
    assert figures.format_seeds([7]) == "7"


# ------------------------------------------------------------ files, guards, manifest

def write_results(folder: Path, n_seeds: int = 3) -> None:
    """A temp results folder with small CSV files shaped like the real ones."""
    seeds = list(range(1, n_seeds + 1))
    make_table(figures.F1_EXPERIMENT, [figures.F1_CONDITION], [m for m, _, _ in figures.F1_PANELS],
               n_seeds=n_seeds, nan_cells=[("baseline", "sequential", "gross_prefunding_usd")]).to_csv(folder / "summary.csv", index=False)
    stress_table(n_seeds=n_seeds).to_csv(folder / "stress_test_results.csv", index=False)
    big = lstar_table()
    big = big[big["seed"] <= n_seeds]
    big.to_csv(folder / "lstar_by_seed.csv", index=False)
    log_rows = []
    common = "count=500;n_banks=2;arrival=sequential"
    cells = {
        "exp1_baseline": [("baseline", 60, 0.01)],
        "exp3_liquidity": [("jpy_1", 60, 0.01)],
        "exp4_failure": [("failure_0", 60, 0.0), ("failure_0.01", 60, 0.01), ("failure_0.05", 60, 0.05)],
        "exp4_delay": [("delay_0", 0, 0.01), ("delay_300", 300, 0.01)],
        "exp4_h4b": [("h4b_delay_0", 0, 0.01)],
        "exp2_x_exp3": [("baseline/jpy_1", 60, 0.01)],
    }
    for experiment, conditions in cells.items():
        for condition, delay, failure in conditions:
            multiplier = "0.09375" if experiment == "exp4_h4b" else "1.0"
            parameters = (f"condition={condition};{common};delay_seconds={delay};failure_probability={failure};"
                          f"jpy_multiplier={multiplier}")
            for seed in seeds:
                log_rows.append({"run_utc": "2026-01-01T00:00:00Z", "experiment": experiment, "model": "sequential",
                                 "seeds": str(seed), "parameters": parameters, "git_commit": "abc123", "status": "ok",
                                 "note": ""})
    pd.DataFrame(log_rows).to_csv(folder / "experiment_log.csv", index=False)
    pd.DataFrame([{"hypothesis": "H3", "git_commit": "def456", "seeds": "1-3"}]).to_csv(folder / "h3_verdicts.csv", index=False)


def run_main(folder: Path, **kwargs) -> dict[str, object]:
    return figures.main(results_dir=folder, out_dir=folder / "figs", allow_dirty=True, write_png_files=False, **kwargs)


def test_main_writes_html_and_manifest(tmp_path):
    write_results(tmp_path, n_seeds=4)
    result = run_main(tmp_path)
    assert result["n_figures"] == 7
    out = tmp_path / "figs"
    for figure_id in figures.FIGURE_IDS:
        assert (out / f"{figure_id}.html").exists()
        assert not (out / f"{figure_id}.png").exists()  # PNG not requested
    manifest = pd.read_csv(out / "figures_manifest.csv", dtype=str, keep_default_na=False)
    assert list(manifest.columns) == figures.MANIFEST_COLUMNS
    assert list(manifest["figure_id"]) == figures.FIGURE_IDS
    assert set(manifest["slide_candidate"]) == {""}
    assert set(manifest["png_file"]) == {""}  # honest: no PNG was written
    row = manifest.set_index("figure_id")
    assert row.loc["f1_baseline", "n_seeds"] == "4" and row.loc["f1_baseline", "seeds"] == "1-4"
    assert row.loc["f1_baseline", "data_git_commits"] == "abc123"
    assert row.loc["f5_lstar", "data_git_commits"] == "def456;abc123"
    assert row.loc["f2_liquidity_stress", "experiments"] == "exp3_liquidity"
    assert row.loc["f3_delay_failure", "experiments"] == "exp4_failure;exp4_delay"
    assert row.loc["f7_proxy_delay", "metrics"] == "peak_liquidity_proxy_usd"
    assert row.loc["f7_proxy_delay", "experiments"] == "exp4_delay;exp4_failure"
    assert row.loc["f7_proxy_delay", "conditions"] == "delay_0;delay_300;failure_0.01"
    assert row.loc["f6_exposure_liquidity", "metrics"] == "principal_exposure_usd"
    assert row.loc["f6_exposure_liquidity", "experiments"] == "exp3_liquidity"
    assert "stress_test_results.csv" in row.loc["f5_lstar", "source_csvs"]
    assert "summary.csv" in row.loc["f1_baseline", "source_csvs"]


def test_main_stops_without_force_and_leaves_files_unchanged(tmp_path):
    write_results(tmp_path)
    out = tmp_path / "figs"
    out.mkdir()
    existing = out / "f3_delay_failure.html"
    existing.write_text("old")
    with pytest.raises(FileExistsError, match="--force"):
        run_main(tmp_path)
    assert existing.read_text() == "old"
    assert sorted(p.name for p in out.iterdir()) == ["f3_delay_failure.html"]  # nothing else written
    run_main(tmp_path, force=True)
    assert existing.read_text() != "old"


def test_main_writes_nothing_when_data_is_bad(tmp_path):
    write_results(tmp_path)
    stress = pd.read_csv(tmp_path / "stress_test_results.csv")
    stress[stress["condition"] != "h4b_delay_60"].to_csv(tmp_path / "stress_test_results.csv", index=False)
    with pytest.raises(FigureDataError, match="h4b_delay_60"):
        run_main(tmp_path)
    assert not (tmp_path / "figs").exists()


def test_main_missing_file_and_log_seed_mismatch(tmp_path):
    write_results(tmp_path)
    (tmp_path / "lstar_by_seed.csv").unlink()
    with pytest.raises(FigureDataError, match="lstar_by_seed.csv"):
        run_main(tmp_path)
    write_results(tmp_path)
    log = pd.read_csv(tmp_path / "experiment_log.csv")
    log[~((log["experiment"] == "exp4_h4b") & (log["seeds"] == 3))].to_csv(tmp_path / "experiment_log.csv", index=False)
    with pytest.raises(FigureDataError, match="n_seeds"):
        run_main(tmp_path)


def test_cli_exit_codes(tmp_path):
    write_results(tmp_path)
    args = ["--results-dir", str(tmp_path), "--out-dir", str(tmp_path / "o"), "--allow-dirty", "--no-png"]
    assert figures.cli(args) == 0
    assert figures.cli(args) == 1  # outputs exist, no --force
    assert figures.cli(args + ["--force"]) == 0


def test_png_failure_keeps_html_and_returns_nonzero(tmp_path, monkeypatch):
    write_results(tmp_path)

    def broken(fig, path):
        raise RuntimeError("Chrome not found")

    monkeypatch.setattr(figures, "write_png", broken)
    args = ["--results-dir", str(tmp_path), "--out-dir", str(tmp_path / "o"), "--allow-dirty"]
    assert figures.cli(args) == 1
    assert (tmp_path / "o" / "f1_baseline.html").exists()
    assert (tmp_path / "o" / "figures_manifest.csv").exists()


def test_real_png_export(tmp_path):
    try:
        figures.write_png(figures.build_f4(stress_table(), META), tmp_path / "f4.png")
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"PNG export not available (Chrome/kaleido): {error}")
    assert (tmp_path / "f4.png").stat().st_size > 1000


def test_model_colours_and_names_are_pinned():
    """Literal values: a change here changes every slide, so it must be deliberate."""
    assert figures.MODEL_ORDER == ["sequential", "prefunded", "atomic"]
    assert figures.MODEL_COLORS == {"sequential": "#D55E00", "prefunded": "#0072B2", "atomic": "#009E73"}
    assert figures.MODEL_NAMES == {"sequential": "A: Sequential", "prefunded": "B: Prefunded Tokenized",
                                   "atomic": "C: Atomic PvP"}


# ------------------------------------------------------------ Day 14 follow-up: offline HTML, stale files, manifest

def test_html_is_offline_and_plotly_js_is_an_output(tmp_path):
    write_results(tmp_path)
    run_main(tmp_path)
    out = tmp_path / "figs"
    assert (out / "plotly.min.js").stat().st_size > 100_000
    for figure_id in figures.FIGURE_IDS:
        html = (out / f"{figure_id}.html").read_text()
        assert "cdn.plot.ly" not in html, figure_id
        assert 'src="plotly.min.js"' in html, figure_id


def test_plotly_js_is_covered_by_the_overwrite_guard(tmp_path):
    write_results(tmp_path)
    out = tmp_path / "figs"
    out.mkdir()
    (out / "plotly.min.js").write_text("old js")
    with pytest.raises(FileExistsError, match="plotly.min.js"):
        run_main(tmp_path)
    assert (out / "plotly.min.js").read_text() == "old js"


def test_force_removes_png_not_written_in_this_run(tmp_path, capsys):
    write_results(tmp_path)
    out = tmp_path / "figs"
    out.mkdir()
    (out / "f2_liquidity_stress.png").write_bytes(b"old png")
    (out / "notes.png").write_bytes(b"not a figure")
    run_main(tmp_path, force=True)  # write_png_files=False
    assert not (out / "f2_liquidity_stress.png").exists()
    assert (out / "notes.png").exists()  # only figure PNGs are touched
    assert "Removed stale PNG" in capsys.readouterr().out
    manifest = pd.read_csv(out / "figures_manifest.csv", dtype=str, keep_default_na=False)
    assert set(manifest["png_file"]) == {""}


def test_png_failure_midway_removes_old_pngs_of_failed_figures(tmp_path, monkeypatch):
    write_results(tmp_path)
    out = tmp_path / "o"
    out.mkdir()
    for figure_id in figures.FIGURE_IDS:
        (out / f"{figure_id}.png").write_bytes(b"old png")

    def fail_on_third(fig, path):
        if path.name.startswith("f3"):
            raise RuntimeError("Chrome not found")
        path.write_bytes(b"new png")

    monkeypatch.setattr(figures, "write_png", fail_on_third)
    result = figures.main(results_dir=tmp_path, out_dir=out, force=True, allow_dirty=True)
    assert result["png_failed"][0] == "f3_delay_failure"
    assert (out / "f1_baseline.png").read_bytes() == b"new png"
    for figure_id in ["f3_delay_failure", "f4_h4b", "f5_lstar", "f6_exposure_liquidity"]:
        assert not (out / f"{figure_id}.png").exists()


def test_force_keeps_slide_candidate_values(tmp_path):
    write_results(tmp_path)
    run_main(tmp_path)
    path = tmp_path / "figs" / "figures_manifest.csv"
    manifest = pd.read_csv(path, dtype=str, keep_default_na=False)
    manifest.loc[manifest["figure_id"] == "f2_liquidity_stress", "slide_candidate"] = "yes, slide 5"
    manifest.loc[manifest["figure_id"] == "f5_lstar", "slide_candidate"] = "backup"
    # Reverse the row order: values must follow figure_id, not row position.
    manifest = manifest.iloc[::-1]
    manifest.to_csv(path, index=False)
    run_main(tmp_path, force=True)
    again = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("figure_id")
    assert again.loc["f2_liquidity_stress", "slide_candidate"] == "yes, slide 5"
    assert again.loc["f5_lstar", "slide_candidate"] == "backup"
    assert again.loc["f1_baseline", "slide_candidate"] == ""


def test_force_with_old_five_row_manifest_gives_new_figure_an_empty_value(tmp_path):
    write_results(tmp_path)
    out = tmp_path / "figs"
    out.mkdir()
    pd.DataFrame({"figure_id": ["f1_baseline"], "slide_candidate": ["main"]}).to_csv(out / "figures_manifest.csv", index=False)
    run_main(tmp_path, force=True)
    manifest = pd.read_csv(out / "figures_manifest.csv", dtype=str, keep_default_na=False).set_index("figure_id")
    assert manifest.loc["f1_baseline", "slide_candidate"] == "main"
    assert manifest.loc["f6_exposure_liquidity", "slide_candidate"] == ""


def test_n_valid_must_be_zero_or_n_seeds():
    summary = summary_table()
    mask = (summary["model"] == "prefunded") & (summary["metric"] == "gross_prefunding_usd")
    summary.loc[mask, "n_valid"] = 17
    with pytest.raises(FigureDataError, match="n_valid=17"):
        figures.build_f1(summary, META)
    # n_valid 0 is the by-definition NaN case (Model A gross prefunding) and is accepted
    figures.build_f1(summary_table(), META)


def edit_log(folder: Path, change) -> None:
    log = pd.read_csv(folder / "experiment_log.csv")
    change(log)
    log.to_csv(folder / "experiment_log.csv", index=False)


def test_shared_cell_must_have_delay_between_and_same_failure_probability(tmp_path):
    write_results(tmp_path)
    assert figures.shared_cell_delay(pd.read_csv(tmp_path / "experiment_log.csv")) == 60.0

    def other_failure(log):
        mask = (log["experiment"] == "exp4_failure") & log["parameters"].str.contains("condition=failure_0.01;")
        log.loc[mask, "parameters"] = log.loc[mask, "parameters"].str.replace("failure_probability=0.01", "failure_probability=0.02")

    edit_log(tmp_path, other_failure)
    with pytest.raises(FigureDataError, match="failure_probability"):
        run_main(tmp_path)
    assert not (tmp_path / "figs").exists()

    write_results(tmp_path)

    def other_delay(log):
        mask = (log["experiment"] == "exp4_failure") & log["parameters"].str.contains("condition=failure_0.01;")
        log.loc[mask, "parameters"] = log.loc[mask, "parameters"].str.replace("delay_seconds=60", "delay_seconds=500")

    edit_log(tmp_path, other_delay)
    with pytest.raises(FigureDataError, match="does not lie between"):
        run_main(tmp_path)


def test_shared_cell_must_match_other_parameters(tmp_path):
    write_results(tmp_path)

    def other_banks(log):
        mask = (log["experiment"] == "exp4_failure") & log["parameters"].str.contains("condition=failure_0.01;")
        log.loc[mask, "parameters"] = log.loc[mask, "parameters"].str.replace("n_banks=2", "n_banks=3")

    edit_log(tmp_path, other_banks)
    with pytest.raises(FigureDataError, match="more than the delay"):
        run_main(tmp_path)


def test_main_f3_note_mentions_shared_cell(tmp_path):
    write_results(tmp_path)
    run_main(tmp_path)
    html = (tmp_path / "figs" / "f3_delay_failure.html").read_text()
    assert "shared failure_0.01 cell" in html
    assert "Success-rate axis starts at 0" in html


# ------------------------------------------------------------ f7: peak liquidity proxy by delay

def test_f7_every_model_and_delay_matches_table():
    fig = figures.build_f7(stress_table(), META)
    assert [t.name for t in fig.data] == [figures.MODEL_NAMES[m] for m in MODELS]
    cells = [("exp4_delay", "delay_0"), ("exp4_failure", "failure_0.01"), ("exp4_delay", "delay_300")]
    for model, trace in zip(MODELS, fig.data, strict=True):
        assert list(trace.x) == [0.0, 60.0, 300.0]
        for i, (experiment, condition) in enumerate(cells):
            mean, low, high = cell_value(experiment, condition, model, "peak_liquidity_proxy_usd")
            assert trace.y[i] == pytest.approx(mean)
            assert trace.error_y.array[i] == pytest.approx(high - mean)
            assert trace.error_y.arrayminus[i] == pytest.approx(mean - low)


def test_f7_labels():
    fig = figures.build_f7(stress_table(), FigureMeta(seeds="1-3", note="NOTE", shared_delay=60.0))
    text = text_of(fig)
    assert "proxy" in fig.layout.title.text.lower()
    assert "Peak liquidity proxy (USD)" in text and "Settlement delay (seconds)" in text
    assert "Ranges are across seeds" in text and "within the same seed" in text
    assert "results/verdicts.csv" in text
    assert "Lines that overlap are drawn with different markers" in text
    assert "NOTE" in text and "n = 3 seeds (seeds 1-3)" in text
    assert "JPY-only" not in text
    for word in ["supported", "inconclusive", "gap ="]:
        assert word not in text.lower()


def test_f7_requires_shared_delay_in_meta():
    with pytest.raises(FigureDataError, match="shared_delay"):
        figures.build_f7(stress_table(), FigureMeta(seeds="1-3"))


def test_f7_log_must_show_the_reference_multiplier(tmp_path):
    write_results(tmp_path)
    run_main(tmp_path)  # fine with multiplier 1.0
    assert "Ample liquidity (JPY multiplier 1, reference level)" in (tmp_path / "figs" / "f7_proxy_delay.html").read_text()

    def stressed(log):
        mask = (log["experiment"] == "exp4_delay") & log["parameters"].str.contains("condition=delay_300;")
        log.loc[mask, "parameters"] = log.loc[mask, "parameters"].str.replace("jpy_multiplier=1.0", "jpy_multiplier=0.0625")

    edit_log(tmp_path, stressed)
    with pytest.raises(FigureDataError, match="jpy_multiplier 0.0625"):
        figures.check_ample_delay_cells(pd.read_csv(tmp_path / "experiment_log.csv"))
    with pytest.raises(FigureDataError):  # the whole run also stops, whichever check fires first
        run_main(tmp_path, force=True)
