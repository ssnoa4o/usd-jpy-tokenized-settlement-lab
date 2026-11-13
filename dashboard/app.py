"""Streamlit dashboard (Day 15). A thin UI: every number comes from src/ (the real engine).

Run with: streamlit run dashboard/app.py
"""

import math
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src import experiments, figures, live  # noqa: E402

MAIN_FIGURES = ["f1_baseline", "f2_liquidity_stress", "f6_exposure_liquidity", "f7_proxy_delay"]
EXTRA_FIGURES = ["f3_delay_failure", "f4_h4b", "f5_lstar"]
NAME_TO_MODEL = {name: key for key, name in figures.MODEL_NAMES.items()}

ASSUMPTIONS = [
    "All data are synthetic. Amounts and bank pairs are random draws, not real FX flows.",
    "Three simplified own models: A Sequential, B Prefunded Tokenized, C Atomic PvP.",
    "Prefunding (B) and atomic PvP (C) are different concepts: a balance check alone is not atomicity.",
    "In the recorded experiments, liquidity stress lowers the initial JPY balance only; USD stays at the "
    "reference. The live tab can also change USD, but live runs are outside the recorded verdicts.",
    "The FX rate is fixed within a run.",
    "No netting, no credit lines, no intraday repo.",
    "Decision rules were fixed before the main runs and are not statistical tests.",
    "Not connected to any blockchain, wallet, bank API or real funds.",
    "Not endorsed by or affiliated with any central bank or institution.",
    "See research/findings.md (section 7, limitations) and research/methodology.md.",
]


# ------------------------------------------------------------------ cached recorded data


@st.cache_resource(show_spinner=False)
def recorded_figures() -> dict:
    """Build the recorded figures from results/*.csv once per server session."""
    return figures.build_all(experiments.RESULTS_DIR)


@st.cache_data(show_spinner=False)
def reference_balances() -> tuple[int, int]:
    """Reference (USD, JPY) per bank from the calibration file."""
    return live.reference_balances()


# ------------------------------------------------------------------ sidebar


# Baseline value of every sidebar widget (widget key -> value). These are the Exp1 baseline inputs.
BASELINE_WIDGETS: dict[str, object] = {
    "fx_rate": float(experiments.FX_RATE), "count": experiments.COUNT, "n_banks": experiments.N_BANKS,
    "arrival": experiments.ARRIVAL, "usd_mult": 1.0, "jpy_mult": 1.0, "models": list(NAME_TO_MODEL),
    "failure_pct": round(experiments.STRESS_FAILURE_PROBABILITY * 100),
    "delay": experiments.DELAY_SECONDS, "first_seed": 1, "n_seeds": 5,
}  # fmt: skip


# JPY multiplier of the "JPY shortage" button. It must be a level of the recorded grid (checked below).
JPY_SHORTAGE_LEVEL = 0.0625


@st.cache_data(show_spinner=False)
def scenarios() -> dict[str, dict[str, object]]:
    """Scenario buttons: the baseline plus one change each, with levels taken from the recorded experiments."""
    levels = experiments.read_stress_levels(experiments.RESULTS_DIR / experiments.CALIBRATION_FILE)
    if JPY_SHORTAGE_LEVEL not in levels.lower_multipliers:
        raise ValueError(f"JPY level {JPY_SHORTAGE_LEVEL} is not in the recorded grid {levels.lower_multipliers}.")
    jpy_level = JPY_SHORTAGE_LEVEL
    return {
        "Baseline": {},
        "JPY shortage": {"jpy_mult": jpy_level},
        "High failure": {"failure_pct": round(max(experiments.EXP4_FAILURE_LEVELS) * 100)},
        "Long delay": {"delay": max(experiments.EXP4_DELAY_LEVELS)},
    }


def apply_scenario(changes: dict[str, object]) -> None:
    """Button callback: put every input back to the baseline, then apply the scenario's change."""
    for key, value in {**BASELINE_WIDGETS, **changes}.items():
        st.session_state[key] = value


def group(title: str) -> None:
    """A small heading for a group of inputs in the sidebar."""
    st.markdown(f'<p class="lab-group">{escape(title)}</p>', unsafe_allow_html=True)


def sidebar_inputs() -> live.LiveInputs | str:
    """Draw the sidebar widgets. Returns the inputs, or an error message if they are invalid."""
    ref_usd, ref_jpy = reference_balances()
    for key, value in BASELINE_WIDGETS.items():
        st.session_state.setdefault(key, value)
    with st.sidebar:
        st.header("Inputs")
        st.button("Run Simulation", type="primary", key="run", width="stretch")

        group("Scenario")
        columns = st.columns(2)
        for index, (name, changes) in enumerate(scenarios().items()):
            columns[index % 2].button(name, key=f"scenario_{index}", on_click=apply_scenario,
                                      args=(changes,), width="stretch")  # fmt: skip
        st.caption("Each button puts every input back to the baseline (seeds 1-5) and changes one level, taken from "
                   "the recorded experiments. Then press Run Simulation. The recorded results use 30 seeds.")

        group("Market")
        left, right = st.columns(2)
        fx_rate = left.number_input("USD/JPY rate", 50.0, 300.0, step=1.0, format="%.2f", key="fx_rate")
        count = right.number_input("Transactions", 100, 1000, step=100, key="count")

        group("Liquidity per bank")
        usd_mult = st.number_input("USD, multiple of the reference", 0.0, 4.0, step=0.0125,
                                   format="%.5f", key="usd_mult")  # fmt: skip
        usd = round(ref_usd * usd_mult)
        st.caption(f"{usd:,} USD per bank ({usd_mult:.4g} x the reference {ref_usd:,})")
        jpy_mult = st.number_input("JPY, multiple of the reference", 0.0, 4.0, step=0.0125,
                                   format="%.5f", key="jpy_mult")  # fmt: skip
        jpy = round(ref_jpy * jpy_mult)
        st.caption(f"{jpy:,} JPY per bank ({jpy_mult:.4g} x the reference {ref_jpy:,})")

        group("Stress")
        failure_pct = st.slider("Failure probability (%)", 0, 20, step=1, key="failure_pct")
        delay = st.slider("Settlement delay (seconds)", 0, 600, step=30, key="delay")

        group("Settlement models")
        chosen = st.multiselect("Settlement models", list(NAME_TO_MODEL), key="models",
                                label_visibility="collapsed")  # fmt: skip

        with st.expander("Advanced: network and seeds"):
            n_banks = st.slider("Number of banks", 2, 10, key="n_banks")
            arrival = st.selectbox("Arrival pattern", ["sequential", "burst"], key="arrival")
            first_seed = st.number_input("First seed", min_value=0, step=1, key="first_seed")
            n_seeds = st.slider("Number of seeds", 1, 30, key="n_seeds")
    if not chosen:
        return "Select at least one settlement model."
    try:
        return live.LiveInputs(
            initial_usd=float(usd), initial_jpy=float(jpy), fx_rate=float(fx_rate), count=int(count),
            n_banks=int(n_banks), arrival=arrival, models=tuple(NAME_TO_MODEL[n] for n in chosen),
            failure_probability=failure_pct / 100, delay_seconds=float(delay),
            first_seed=int(first_seed), n_seeds=int(n_seeds),
        )  # fmt: skip
    except ValueError as error:
        return str(error)


def handle_run(inputs: live.LiveInputs | str) -> None:
    """Run the engine when the button was pressed; keep the result in session_state."""
    if not st.session_state.get("run"):
        return
    if isinstance(inputs, str):
        st.error(inputs)
        return
    try:
        runs = live.run_live(inputs)
    except ValueError as error:
        st.error(str(error))
        return
    except RuntimeError as error:
        st.error(f"Engine self-check failed: {error}")
        return
    st.session_state["inputs"] = inputs
    st.session_state["runs"] = runs


# ------------------------------------------------------------------ look of the results area

# Colours of the three settlement states in the outcome bar. `partial` is the state that
# carries principal exposure, so it is the one that stands out.
STATE_COLORS = {"success_rate": "#C9D1DC", "partial_rate": "#E6A700", "failure_rate": "#5B6575"}
STATE_NAMES = {"success_rate": "settled", "partial_rate": "partial", "failure_rate": "failed"}

STYLE = """
<style>
[data-testid="stMain"] { font-variant-numeric: tabular-nums; }
[data-testid="stMain"] h1 { font-size: 2rem; font-weight: 600; letter-spacing: -0.01em; padding-bottom: 0.15rem; }
[data-testid="stMain"] h3 { font-size: 1.2rem; font-weight: 600; margin-top: 1.5rem; padding-bottom: 0.4rem;
  border-bottom: 1px solid #2A3140; }
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p { color: #AEB7C4 !important; font-size: 0.9rem;
  line-height: 1.5; opacity: 1; }
[data-testid="stMain"] [data-testid="stCaptionContainer"] p { max-width: 80ch; }
.lab-conditions { display: grid; grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
  gap: 0.9rem 1.5rem; margin: 0.4rem 0 0.2rem; padding: 1rem 1.2rem; background: #161B24;
  border: 1px solid #2A3140; border-radius: 6px; }
.lab-conditions dt { color: #AEB7C4; font-size: 0.82rem; margin-bottom: 0.1rem; }
.lab-conditions dd { color: #E8ECF2; font-size: 1.02rem; font-weight: 600; margin: 0; }
.lab-compare { width: 100%; border-collapse: collapse; margin: 0.4rem 0 0.3rem; }
.lab-compare th, .lab-compare td { border: none; border-bottom: 1px solid #2A3140; padding: 0.7rem 0.9rem; }
.lab-compare th { color: #AEB7C4; font-size: 0.85rem; font-weight: 500; text-align: right;
  vertical-align: bottom; background: transparent; }
.lab-compare th.left, .lab-compare td.left { text-align: left; padding-left: 0; }
.lab-compare td { color: #E8ECF2; font-size: 1.15rem; font-weight: 600; text-align: right; white-space: nowrap; }
.lab-compare td.name { font-size: 1rem; }
.lab-compare td.quiet { color: #AEB7C4; font-weight: 500; }
.lab-swatch { display: inline-block; width: 0.3rem; height: 1.15rem; border-radius: 2px;
  margin-right: 0.6rem; vertical-align: -0.2rem; }
.lab-bar { display: flex; width: 100%; min-width: 9rem; height: 0.6rem; border-radius: 2px; overflow: hidden;
  background: #1E2532; }
.lab-bar span { display: block; height: 100%; }
.lab-key { color: #AEB7C4; font-size: 0.85rem; margin: 0.2rem 0 0; }
.lab-key i { display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 2px;
  margin: 0 0.35rem 0 0.9rem; vertical-align: -0.05rem; }
.lab-key i:first-child { margin-left: 0; }
.lab-notes { max-width: 80ch; margin: 0.3rem 0 0; padding-left: 1.2rem; color: #D5DBE4; line-height: 1.55; }
.lab-notes li { margin-bottom: 0.45rem; }
.lab-group { color: #E8ECF2; font-size: 0.95rem; font-weight: 600; margin: 1.1rem 0 0.1rem;
  padding-top: 0.9rem; border-top: 1px solid #2A3140; }
</style>
"""


def section(title: str, description: str = "") -> None:
    """A section heading with an optional one-line description under it."""
    st.subheader(title)
    if description:
        st.caption(description)


# ------------------------------------------------------------------ tab 1


def condition_items(inputs: live.LiveInputs) -> list[tuple[str, str]]:
    """The inputs of the run on screen, as (label, value) pairs."""
    last_seed = inputs.first_seed + inputs.n_seeds - 1
    models = ", ".join(figures.MODEL_SHORT[m] for m in figures.MODEL_ORDER if m in inputs.models)
    return [
        ("USD/JPY", f"{inputs.fx_rate:g}"),
        ("Transactions", f"{inputs.count:,}"),
        ("Network", f"{inputs.n_banks} banks, {inputs.arrival} arrival"),
        ("Initial USD per bank", f"{inputs.initial_usd:,.0f}"),
        ("Initial JPY per bank", f"{inputs.initial_jpy:,.0f}"),
        ("Failure probability", f"{inputs.failure_probability:.0%}"),
        ("Settlement delay", f"{inputs.delay_seconds:g} s"),
        ("Models", models),
        ("Seeds", f"{inputs.first_seed}-{last_seed} ({inputs.n_seeds} seeds)"),
    ]


def conditions_html(inputs: live.LiveInputs) -> str:
    """The run conditions as a compact grid of label / value pairs."""
    cells = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>" for label, value in condition_items(inputs)
    )
    return f'<dl class="lab-conditions">{cells}</dl>'


def outcome_bar(values: dict[str, float]) -> str:
    """A thin bar split into the settled / partial / failed shares of one model."""
    parts = "".join(
        f'<span style="width:{max(values[metric], 0) * 100:.2f}%;background:{color}"></span>'
        for metric, color in STATE_COLORS.items()
        if not math.isnan(values[metric])
    )
    return f'<div class="lab-bar">{parts}</div>'


def comparison_html(rows: list[dict[str, object]]) -> str:
    """The comparison at a glance: one row per model, the headline metrics as columns."""
    head = '<th class="left">Model</th>'
    for metric, label in live.HEADLINE_METRICS:
        head += f"<th>{escape(label)}</th>"
        if metric == "failure_rate":
            head += '<th class="left">Outcome mix</th>'
    body = ""
    for row in rows:
        cells = (f'<td class="left name"><span class="lab-swatch" style="background:{row["color"]}"></span>'
                 f'{escape(row["name"])}</td>')  # fmt: skip
        for metric, _ in live.HEADLINE_METRICS:
            text = row["text"][metric]
            quiet = ' class="quiet"' if text == live.NOT_AVAILABLE else ""
            cells += f"<td{quiet}>{escape(text)}</td>"
            if metric == "failure_rate":
                cells += f'<td class="left">{outcome_bar(row["values"])}</td>'
        body += f"<tr>{cells}</tr>"
    key = "".join(f'<i style="background:{STATE_COLORS[m]}"></i>{STATE_NAMES[m]}' for m in STATE_COLORS)
    return (f'<table class="lab-compare"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
            f'<p class="lab-key">Outcome mix: {key}</p>')  # fmt: skip


def styled_summary(table: pd.DataFrame) -> "pd.io.formats.style.Styler":
    """The summary table with one number format per metric row. The values stay exact numbers."""
    labels = dict(live.METRIC_LABELS)
    models = [column for column in table.columns if column != "Metric"]
    styler = table.style
    for metric in live.METRIC_FORMATS:
        rows = table.index[table["Metric"] == labels[metric]]
        styler = styler.format(lambda value, metric=metric: live.format_value(metric, value),
                               subset=pd.IndexSlice[rows, models], na_rep=live.NOT_AVAILABLE)  # fmt: skip
    return styler


def reasons_by_model(table: pd.DataFrame) -> pd.DataFrame:
    """Turn the reason table on its side: one row per status / reason, one column per model."""
    return table.set_index("Model").T.rename_axis(None, axis=1).reset_index(names="Status / reason")


def show_live_tab(current: live.LiveInputs | None) -> None:
    """Live simulation tab."""
    if "runs" not in st.session_state:
        st.info("Set the inputs in the sidebar and press Run Simulation.")
        return
    used: live.LiveInputs = st.session_state["inputs"]
    runs: pd.DataFrame = st.session_state["runs"]
    if current != used:
        st.warning("The inputs have changed since the last run. The results below belong to the "
                   "previous inputs; press Run Simulation to update.")  # fmt: skip
    summary = live.summarize_live(runs)

    section("Run conditions", "Live exploratory run. It is not one of the recorded experiments: "
            "nothing is saved and no hypothesis verdict is computed from it.")  # fmt: skip
    st.markdown(conditions_html(used), unsafe_allow_html=True)

    section("Comparison at a glance", f"Mean over {used.n_seeds} seeds. The same transactions feed every model.")
    st.markdown(comparison_html(live.headline_rows(summary)), unsafe_allow_html=True)
    st.plotly_chart(live.build_live_figure(summary), width="stretch")
    st.caption("Bars show the mean over seeds. Whiskers show the min - max range over seeds; "
               "they are not confidence intervals.")  # fmt: skip

    section("All metrics", "Mean over seeds, one row per metric. None means the metric is not defined for that model (it is not zero).")
    st.dataframe(styled_summary(live.summary_table(summary)), hide_index=True, width="stretch")
    with st.expander("Range over seeds (min - max)"):
        st.dataframe(live.range_table(summary), hide_index=True, width="stretch")

    section("Settlement status and failure reasons", "Number of transactions, summed over seeds.")
    st.dataframe(reasons_by_model(live.reason_table(runs)), hide_index=True, width="stretch")
    with st.expander("Every run (one row per seed and model)"):
        st.dataframe(runs, hide_index=True, width="stretch")

    section("How to read these numbers")
    notes = "".join(f"<li>{escape(note)}</li>" for note in live.LIVE_NOTES)
    st.markdown(f'<ul class="lab-notes">{notes}</ul>', unsafe_allow_html=True)


# ------------------------------------------------------------------ tab 2

VERDICT_COLUMNS = {
    "hypothesis": st.column_config.TextColumn("Hypothesis", width="small"),
    "factor": st.column_config.TextColumn("Factor", width="small"),
    "model": st.column_config.TextColumn("Model", width="small"),
    "low_level": st.column_config.TextColumn("Low level", width="small"),
    "high_level": st.column_config.TextColumn("High level", width="small"),
    "verdict": st.column_config.TextColumn("Verdict", width="medium"),
    "n_seeds_equal": st.column_config.NumberColumn("Seeds with equal L*", width="small"),
    "note": st.column_config.TextColumn("Note from the CSV", width="medium"),
    "caveat": st.column_config.TextColumn("Caveat", width="large"),
}


def show_figure(figure_id: str, built: dict[str, tuple[go.Figure, dict]]) -> None:
    """Show one recorded figure at its own height."""
    st.plotly_chart(built[figure_id][0], width="stretch", key=f"fig_{figure_id}")


def show_verdicts() -> None:
    """Recorded verdicts, read from the CSV files (never recomputed)."""
    section("Hypothesis verdicts (recorded)")
    st.caption(live.GENERAL_VERDICT_NOTE)
    try:
        main, h3 = live.load_verdict_tables()
    except ValueError as error:
        st.error(str(error))
        return
    st.markdown("**H1a, H1b, H2, H4a, H4b**")
    st.dataframe(main, hide_index=True, width="stretch", column_config=VERDICT_COLUMNS)
    st.markdown("**H3 (volume, banks, arrival)**")
    st.dataframe(h3, hide_index=True, width="stretch", column_config=VERDICT_COLUMNS)
    section("Caveats", "Read every verdict together with its caveat.")
    st.markdown("\n".join(f"- **{row.hypothesis}**: {row.caveat}" for row in main.itertuples()))
    st.markdown(f"- **H3**: {live.VERDICT_NOTES['H3']}")
    st.markdown(f"- **H3 banks**: {live.BANKS_NOTE}")
    st.markdown(f"- **H3 arrival (A and C)**: {live.MODEL_RULES_NOTE}")


def show_recorded_tab() -> None:
    """Recorded results tab."""
    try:
        built = recorded_figures()
    except ValueError as error:  # includes FigureDataError
        st.error(f"Recorded figures could not be built: {error}")
    else:
        section("Main figures", "Built from the CSV files in results/ (30 seeds). No simulation runs here.")
        for figure_id in MAIN_FIGURES:
            show_figure(figure_id, built)
        section("Additional figures")
        for figure_id in EXTRA_FIGURES:
            show_figure(figure_id, built)
    show_verdicts()


# ------------------------------------------------------------------ main


def main() -> None:
    """Draw the page."""
    st.set_page_config(page_title="USD/JPY Settlement Lab", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.title("USD/JPY Tokenized Settlement Lab")
    st.caption("Independent research prototype using simulated data")
    try:
        current = sidebar_inputs()
    except ValueError as error:  # calibration file problem
        st.error(str(error))
        return
    handle_run(current)
    tab_live, tab_recorded, tab_limits = st.tabs(["Live simulation", "Recorded results", "Assumptions & limits"])
    with tab_live:
        show_live_tab(current)
    with tab_recorded:
        show_recorded_tab()
    with tab_limits:
        st.markdown("\n".join(f"- {line}" for line in ASSUMPTIONS))


main()
