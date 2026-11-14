# USD/JPY Tokenized Settlement Lab

Open-source research and simulation framework for tokenized USD/JPY foreign exchange settlement.

> **Status: version 1.0 (2026-11-14).** The repository contains a simulator with three settlement models, the experiments and their hypothesis verdicts, seven figures, a Streamlit dashboard, a research report, a policy brief and a 12-slide deck. Everything runs on synthetic data. This is an independent research prototype. Start reading with `research/report.pdf`. Full results are in `research/findings.md`.

## Where to start

1. **Research report (PDF):** `research/report.pdf`
2. **Policy brief (PDF):** `policy/policy_brief.pdf`
3. **Slides (PDF, 12 slides):** `presentation/slides.pdf`
4. **Full results and reading notes:** `research/findings.md`
5. **Dashboard:** `streamlit run dashboard/app.py` (see Quick start)

## Project overview

This project is an independent research prototype. It models three simplified ways of settling a USD/JPY trade, runs them on the same synthetic transaction data under stated assumptions, and compares them on principal settlement risk, liquidity requirements, settlement time and operational resilience.

It is not a blockchain transfer demo. The aim is a transparent, reproducible comparison of trade-offs. Any finding applies only to the simplified models implemented here, under the stated assumptions. It does not show that the same effects occur in real markets.

## Research question

> How do tokenized settlement mechanisms affect liquidity requirements, principal settlement risk, and operational performance in USD/JPY foreign exchange transactions?

## Three settlement models

Each model is a deliberate simplification built for comparison. None is a replica of a real system.

| Model | Name | Definition | Explicit simplification |
|---|---|---|---|
| A | Sequential | The USD leg and the JPY leg are processed independently, with a time gap between them. | Not a full correspondent-banking replica. It is a comparison baseline for "independent settlement with a time gap". |
| B | Prefunded Tokenized | The currency-specific funds needed are reserved before settlement, and legs are then processed using tokenized (virtual) assets. | Does not reproduce the legal or operational structure of tokenized bank deposits or central bank reserves. |
| C | Atomic PvP | Both legs are treated as one indivisible unit: both settle or neither does. | Research logic only. It is not CLS's algorithm and does not model legal settlement finality. |

Prefunding and Atomic PvP are different concepts. Prefunding is a funding condition: funds are secured before settlement. Atomic PvP is an execution condition: two currency legs commit together or not at all. Checking balances in advance does not by itself make a settlement atomic.

Settlement outcomes use three states: `settled`, `partial` (one leg only) and `failed`. A `partial` outcome never counts toward the success rate.

## Hypotheses under test

These are questions the experiments examine. None is assumed to be true. Each is recorded as supported, not supported, or inconclusive, under rules fixed before the runs (`research/hypotheses.md`).

The research question is broken into four themes. Each theme has one or two hypotheses with a primary metric and comparison fixed in `research/hypotheses.md`:

- **H1. Principal exposure.** H1a (descriptive, no verdict): how Principal Exposure in A and B responds as the injected failure probability rises. H1b: B has lower Principal Exposure than A under liquidity stress.
- **H2. Liquidity and funding.** The gap in the Peak Liquidity Proxy between B and A is larger at a 300 s settlement delay than at 0 s.
- **H3. Scale, participants and arrival pattern.** The lowest initial-liquidity level at which Success Rate reaches 95% (L\*) differs between factor levels (transaction volume, number of banks, arrival pattern). There are nine separate verdicts (three factors x three models) and no combined verdict.
- **H4. Stress affects models differently.** H4a: under liquidity stress, the change in Success Rate differs between A and C. H4b: under delay stress, the change in Principal Exposure differs between A and B.

Some outcomes follow from the model design. For example, Model C has no `partial` outcomes and zero principal exposure by construction. These are correctness checks on the code. They are not evidence for a hypothesis.

## Methodology

Inputs are synthetic and illustrative. They do not represent real bank liquidity levels or real failure rates.

- **Input variables:** FX rate (fixed at 150.00 in every run), transaction size, number of banks, initial liquidity per bank and currency, settlement delay, transaction arrival pattern, failure probability, transaction volume, random seed.
- **Metrics:** principal exposure, success rate, partial settlement rate, failure rate (insufficient funds and technical failure reported separately), gross prefunding, peak liquidity (reported as a proxy where approximated), average settlement time, liquidity utilization, operational delay.
- **Gross Prefunding is not Peak Liquidity.** Gross prefunding is the currency-specific funds that must be secured before settlement. Peak liquidity is the maximum funding need during the simulation. Because the first version has no netting, fund reuse or credit, peak liquidity is labelled a proxy.
- **Experiments:** (1) baseline, (2) sensitivity to transaction volume, number of banks and arrival pattern, crossed with the liquidity grid, (3) liquidity stress (JPY balances only), (4) delay and failure stress. Each condition is repeated over 30 random seeds (1 to 30) to show variation, not only averages. Details are in `research/methodology.md`.
- **Reproducibility:** all data is simulated. Random seeds are configurable, and each run saves its seed, input data and parameters with its output.
- **Protocol history that matters.** The liquidity calibration was run twice. Attempt 1 (2026-11-09) did not meet its grid condition. The grid was then revised to lower JPY balances only, before any main run. Attempt 2 (2026-11-10) met its conditions. The verdict code was committed before each main run.

## Results

Tables and reading notes are in `research/findings.md`. This README does not repeat them. All values come from the CSV files in `results/`.

- **Exp1 baseline** (`results/baseline_results.csv`): descriptive only, with no hypothesis verdict. Several outcomes follow from the model design and are correctness checks, not evidence (findings sec. 3).
- **Exp3 and Exp4 stress runs** (1,170 runs; `results/stress_test_results.csv`, `results/verdicts.csv`): hypothesis tests under pre-fixed rules in a simplified synthetic model. Some follow largely from the model design (findings sec. 4).
- **Exp2 x Exp3 sensitivity run** (2,700 runs; `results/sensitivity_results.csv`, `results/lstar_by_seed.csv`, `results/h3_verdicts.csv`): nine H3 verdicts: 0 supported, 2 not supported, 7 inconclusive, on a coarse JPY-only liquidity grid. There is no single combined H3 verdict. The two not supported verdicts (arrival pattern, Models A and C) may follow largely from the model rules and are not independent evidence (findings sec. 5).
- **Other files:** the calibration record (`results/calibration*.csv`) and a diagnostic on test seeds (`results/diagnostic_two_bank_mirror.csv`). Neither is a result about the settlement models.

## Limitations

- The models are simplified. They are not replicas of correspondent banking, tokenized bank deposits, CLS, RTGS systems or any other production infrastructure.
- All data is synthetic. Parameters are illustrative and are not calibrated to real markets, banks or failure rates.
- Smart-contract-style completion in a simulation is not legal settlement finality. Legal finality depends on legal and regulatory frameworks that this project does not model.
- Atomic PvP can reduce principal risk, meaning the risk that one leg settles and the other does not. It does not remove liquidity risk, because participants still need funds available to settle.
- The first version excludes netting, credit, intraday liquidity facilities, multi-currency routing and market-price movement.
- Any finding holds only under the implemented models and assumptions.

## Quick start

Requires Python 3 (developed and tested with Python 3.14 on macOS). PNG figure export and the PDF build scripts need Google Chrome or Chromium.

```bash
git clone https://github.com/ssnoa4o/usd-jpy-tokenized-settlement-lab.git
cd usd-jpy-tokenized-settlement-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
streamlit run dashboard/app.py
```

All tests should pass (1505 tests; about 1 minute on a MacBook Air). The dashboard opens in a browser. Run both from the repository root, inside the `.venv`.

## Reproducing the results

Verified on 2026-11-14 from a fresh clone at commit 7f5d8a3 (Python 3.14.6, MacBook Air). Later commits changed only documentation and PDFs, not code or results. Run these commands in this order:

```bash
python -m src.experiments baseline --force      # 180 runs, about 2 s
python -m src.experiments stress --force        # 1,170 runs, about 12 s
python -m src.experiments sensitivity --force   # 2,700 runs, about 23 s
python -m src.verdicts --force
python -m src.verdicts h3 --force
python -m src.figures --force                   # about 14 s
```

`python -m src.calibration --force` reruns the liquidity calibration (about 5 s). The experiments read the stored `results/calibration.csv`, not a fresh calibration.

`--force` is needed because the outputs already exist.

**Clean working tree.** The experiment and figure commands record the git commit, so they refuse to run if the working tree has uncommitted changes. Every run rewrites files in `results/`, so the tree is not clean after one command. For each command:

1. Run it on a clean checkout.
2. Inspect `git diff --stat results/` and `git diff results/`.
3. Run `git checkout -- results/` before the next command.

`python -m src.verdicts` and `python -m src.calibration` do not refuse on a dirty tree: the verdict commands print a warning, and the calibration adds `-dirty` to the commit it records. `--allow-dirty` exists for test runs only. A run made with it is not a recorded run.

**What to expect** (when `results/` is restored between commands as above):

- Every result value is identical to the stored CSVs.
- Only record columns change: `git_commit` and `run_utc` in the run-level CSVs and `calibration.csv`; `figure_code_commit` and `generated_utc` in `results/figures/figures_manifest.csv`.
- The figure HTML files differ only in generated ids and metadata.
- The PNG files and the aggregated CSVs were byte-identical (`baseline_results.csv`, `stress_test_results.csv`, `sensitivity_results.csv`, `verdicts.csv`, `h3_verdicts.csv`, `lstar_by_seed.csv`). The verdict files copy the `git_commit` of their input runs, so they also change if you rerun the experiments without restoring `results/` first.
- `experiment_log.csv` is append-only, so a rerun adds rows (180, 1,170 and 2,700).
- `summary.csv`: `baseline` rewrites it with baseline rows only. `stress` and `sensitivity` rebuild it from all experiment outputs. If you run the commands without restoring `results/` in between, keep the order above so that it ends up complete.

**PDFs.**

```bash
python scripts/build_report_pdf.py --force
python scripts/build_report_pdf.py --input policy/policy_brief.md --output policy/policy_brief.pdf --force
python scripts/build_slides_pdf.py --force
```

These need Google Chrome or Chromium. `--force` is needed because the PDFs already exist.

## Command reference

**Transaction generator.** `python -m src.transactions` writes two files:

- `data/sample_transactions.csv`: 100 synthetic USD/JPY transactions (seed 42, 2 banks, one arrival every 10 seconds). Columns: `transaction_id`, `arrival_time`, `usd_payer`, `jpy_payer`, `usd_amount`, `jpy_amount`, `fx_rate`, `failure_draw`.
- `data/sample_transactions_meta.json`: the parameters used to generate them.

The data uses a fixed USD/JPY rate of 150.00. This is an illustrative simplification, not a market observation or forecast.

**Calibration.** `python -m src.calibration` runs the liquidity calibration (methodology sec. 6). It refuses to overwrite existing outputs unless `--force` is given.

**Experiments.** `python -m src.experiments baseline` runs Exp1 (seeds 1 to 30). It writes `results/run_metrics.csv` (one row per run), `results/baseline_results.csv` (mean, min, max across seeds per condition and model) and `results/summary.csv`, and appends to `results/experiment_log.csv`. `stress` (Exp3 and Exp4) writes `results/stress_run_metrics.csv` and `results/stress_test_results.csv`. `sensitivity` (Exp2 x Exp3) writes `results/sensitivity_run_metrics.csv` and `results/sensitivity_results.csv`. All three refuse to run on uncommitted code unless `--allow-dirty` is given, and refuse to overwrite outputs unless `--force` is given.

**Verdicts.** `python -m src.verdicts` applies the pre-fixed rules in `research/hypotheses.md` to the stress results and writes `results/verdicts.csv`. `python -m src.verdicts h3` does the same for H3 and writes `results/lstar_by_seed.csv` and `results/h3_verdicts.csv`.

**Figures.** `python -m src.figures` builds the seven main figures (`f1_baseline`, `f2_liquidity_stress`, `f3_delay_failure`, `f4_h4b`, `f5_lstar`, `f6_exposure_liquidity`, `f7_proxy_delay`) from the CSVs in `results/`. No simulation is run. It writes an HTML and a PNG file per figure, plus `plotly.min.js` and `figures_manifest.csv`, into `results/figures/`.

- Same guards as the experiments (`--force`, `--allow-dirty`). With `--force`, old PNGs the run did not write are removed.
- The HTML files load the local `plotly.min.js` next to them, so they open without internet. It is a third-party file, not stored in this repository (it is in `.gitignore`). `python -m src.figures --force` creates it when missing; if it is damaged, delete it and rerun. The PNG files can be viewed directly.
- PNG export uses `kaleido`, which needs Google Chrome or Chromium. If Chrome is not found, the HTML files and manifest are still written, an error is printed and the exit code is 1. Install Chrome, or run `plotly_get_chrome` inside the `.venv`, then rerun with `--force`. `--no-png` skips PNG export.

**Dashboard.** `streamlit run dashboard/app.py` has three tabs.

- "Live simulation" runs the real engine with the sidebar inputs and shows metrics per model. A live run is exploratory: it is not a recorded experiment, nothing is saved to `results/`, and no verdict is computed from it.
- "Recorded results" shows the seven figures and the verdicts read from `results/verdicts.csv` and `results/h3_verdicts.csv`, each with its caveat. Verdicts are not recomputed.
- "Assumptions & limits" lists the main simplifications.

## Repository contents

| Folder | What it holds |
|---|---|
| `src/` | Generator, simulator (Models A, B, C), metrics, calibration, experiments, verdicts, figures |
| `tests/` | Tests, including each model against an independent plain-Python reference |
| `dashboard/` | Streamlit dashboard |
| `data/` | Sample synthetic transactions |
| `results/` | Result CSVs, calibration record, experiment log; `figures/` holds the seven figures and manifest |
| `research/` | Research question, literature review, hypotheses, methodology, findings, report |
| `policy/` | Policy brief (md, pdf) |
| `presentation/` | `slides.md` (with speaker notes), `slides.pdf` |
| `scripts/` | PDF build scripts |

## Disclaimer

This is an independent, unofficial research prototype using simulated data. It is not affiliated with, endorsed by, or produced in collaboration with any central bank, international organisation, settlement system operator or financial institution. It connects to no real funds, bank accounts or bank APIs, wallets, Ethereum or other blockchain networks, or production tokens. Nothing here is financial, legal or policy advice.

Related public work, such as BIS Project Agora, is cited for context only. This project does not reproduce it or claim any connection to it.

## License

MIT
