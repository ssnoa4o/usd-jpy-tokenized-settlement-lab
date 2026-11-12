"""Streamlit dashboard (Day 15). A thin UI: every number comes from src/ (the real engine).

Run with: streamlit run dashboard/app.py
"""

import sys
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


def sidebar_inputs() -> live.LiveInputs | str:
    """Draw the sidebar widgets. Returns the inputs, or an error message if they are invalid."""
    ref_usd, ref_jpy = reference_balances()
    with st.sidebar:
        st.header("Inputs")
        fx_rate = st.number_input("USD/JPY", 50.0, 300.0, 150.0, key="fx_rate")
        count = st.slider("Transaction volume", 100, 1000, 500, step=100, key="count")
        n_banks = st.slider("Number of banks", 2, 10, 2, key="n_banks")
        arrival = st.selectbox("Arrival pattern", ["sequential", "burst"], key="arrival")
        usd_mult = st.number_input("Initial USD multiplier", 0.0, 4.0, 1.0, step=0.0125,
                                   format="%.5f", key="usd_mult")  # fmt: skip
        usd = round(ref_usd * usd_mult)
        st.caption(f"Initial USD per bank: {usd:,} (reference {ref_usd:,} x multiplier)")
        jpy_mult = st.number_input("Initial JPY multiplier", 0.0, 4.0, 1.0, step=0.0125,
                                   format="%.5f", key="jpy_mult")  # fmt: skip
        jpy = round(ref_jpy * jpy_mult)
        st.caption(f"Initial JPY per bank: {jpy:,} (reference {ref_jpy:,} x multiplier)")
        chosen = st.multiselect("Settlement models", list(NAME_TO_MODEL),
                                default=list(NAME_TO_MODEL), key="models")  # fmt: skip
        failure_pct = st.slider("Failure probability (%)", 0, 20, 1, step=1, key="failure_pct")
        delay = st.slider("Settlement delay (seconds)", 0, 600, 60, step=30, key="delay")
        first_seed = st.number_input("First seed", min_value=0, value=1, step=1, key="first_seed")
        n_seeds = st.slider("Number of seeds", 1, 30, 5, key="n_seeds")
        st.button("Run Simulation", type="primary", key="run")
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


# ------------------------------------------------------------------ tab 1


def inputs_text(inputs: live.LiveInputs) -> str:
    """One-line description of the inputs used."""
    seeds = f"seeds {inputs.first_seed}-{inputs.first_seed + inputs.n_seeds - 1}"
    models = ", ".join(figures.MODEL_SHORT[m] for m in figures.MODEL_ORDER if m in inputs.models)
    return (
        f"Inputs used: USD/JPY {inputs.fx_rate:g}; {inputs.count} transactions; {inputs.n_banks} banks; "
        f"{inputs.arrival} arrival; initial USD {inputs.initial_usd:,.0f} and JPY {inputs.initial_jpy:,.0f} "
        f"per bank; models {models}; failure probability {inputs.failure_probability:.0%}; "
        f"delay {inputs.delay_seconds:g} s; {seeds} ({inputs.n_seeds} seeds)."
    )


def show_live_tab(current: live.LiveInputs | str) -> None:
    """Live simulation tab."""
    if "runs" not in st.session_state:
        st.info("Set the inputs in the sidebar and press Run Simulation.")
        return
    used: live.LiveInputs = st.session_state["inputs"]
    runs: pd.DataFrame = st.session_state["runs"]
    if current != used:
        st.warning("The inputs have changed since the last run. The results below belong to the "
                   "previous inputs; press Run Simulation to update.")  # fmt: skip
    st.caption(inputs_text(used))
    summary = live.summarize_live(runs)
    st.subheader("Summary (mean over seeds)")
    st.dataframe(live.summary_table(summary), hide_index=True, width="stretch")
    st.plotly_chart(live.build_live_figure(summary), width="stretch")
    with st.expander("Min - max over seeds"):
        st.dataframe(live.range_table(summary), hide_index=True, width="stretch")
    st.subheader("Status and failure reasons (sum over seeds)")
    st.dataframe(live.reason_table(runs), hide_index=True, width="stretch")
    with st.expander("Per-run rows"):
        st.dataframe(runs, hide_index=True, width="stretch")
    for note in live.LIVE_NOTES:
        st.caption(note)


# ------------------------------------------------------------------ tab 2


def show_figure(figure_id: str, built: dict[str, tuple[go.Figure, dict]]) -> None:
    """Show one recorded figure at its own height."""
    st.plotly_chart(built[figure_id][0], width="stretch", key=f"fig_{figure_id}")


def show_verdicts() -> None:
    """Recorded verdicts, read from the CSV files (never recomputed)."""
    st.subheader("Hypothesis verdicts (recorded)")
    st.caption(live.GENERAL_VERDICT_NOTE)
    try:
        main, h3 = live.load_verdict_tables()
    except ValueError as error:
        st.error(str(error))
        return
    st.dataframe(main, hide_index=True, width="stretch")
    st.markdown("**H3 (volume, banks, arrival)**")
    st.dataframe(h3, hide_index=True, width="stretch")
    st.markdown("**Caveats**")
    st.markdown("\n".join(f"- **{row.hypothesis}**: {row.caveat}" for row in main.itertuples()))
    st.markdown(f"- **H3**: {live.VERDICT_NOTES['H3']}")
    st.markdown(f"- **H3 arrival (A and C)**: {live.MODEL_RULES_NOTE}")
    st.markdown(f"- **H3 banks**: {live.BANKS_NOTE}")


def show_recorded_tab() -> None:
    """Recorded results tab."""
    try:
        built = recorded_figures()
    except ValueError as error:  # includes FigureDataError
        st.error(f"Recorded figures could not be built: {error}")
    else:
        st.subheader("Main figures")
        for figure_id in MAIN_FIGURES:
            show_figure(figure_id, built)
        st.subheader("Additional figures")
        for figure_id in EXTRA_FIGURES:
            show_figure(figure_id, built)
    show_verdicts()


# ------------------------------------------------------------------ main


def main() -> None:
    """Draw the page."""
    st.set_page_config(page_title="USD/JPY Settlement Lab", layout="wide")
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
