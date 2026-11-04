# USD/JPY Tokenized Settlement Lab

Open-source research and simulation framework for tokenized USD/JPY foreign exchange settlement.

> **Status: early draft (Day 8 of a 21-day plan).** The synthetic transaction generator, the bank ledger and the three settlement models (A: Sequential, B: Prefunded Tokenized, C: Atomic PvP) work, and each model is checked against an independent plain-Python reference implementation in the tests. Experiments and the dashboard are planned and not yet implemented. No experiments have been run, and this repository reports no results yet.

## Project overview

This project is an independent research prototype. It models three simplified ways of settling a USD/JPY trade, runs them on the same synthetic transaction data under stated assumptions, and compares them on principal settlement risk, liquidity requirements, settlement time and operational resilience.

It is not a blockchain transfer demo. The aim is a transparent, reproducible comparison of trade-offs. Any finding will apply only to the simplified models implemented here, under the stated assumptions. It will not show that the same effects occur in real markets.

Planned outputs: a Python simulator, experiment CSVs and figures, a Streamlit dashboard, a research report, a policy brief and a presentation.

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

These are questions the experiments will examine. None is assumed to be true. Each will be recorded as supported, not supported, or inconclusive.

- **H1.** Does Atomic PvP reduce principal exposure from settlement where only one currency leg completes?
- **H2.** Does PvP or prefunding require a certain amount of liquidity to be set aside or tied up?
- **H3.** When transaction count, number of banks or arrival pattern change, does the relationship between liquidity demand and settlement success rate change?
- **H4.** Do stress conditions such as liquidity shortage or settlement delay affect the three models differently?

## Methodology

Inputs are synthetic and illustrative. They do not represent real bank liquidity levels or real failure rates.

- **Input variables (planned):** FX rate, transaction size, number of banks, initial liquidity per bank and currency, settlement delay, transaction arrival pattern, failure probability, transaction volume, random seed.
- **Metrics (planned):** principal exposure, success rate, partial settlement rate, failure rate (insufficient funds and technical failure reported separately), gross prefunding, peak liquidity (reported as a proxy where approximated), average settlement time, liquidity utilization, operational delay.
- **Gross Prefunding is not Peak Liquidity.** Gross prefunding is the currency-specific funds that must be secured before settlement. Peak liquidity is the maximum funding need during the simulation. Because the first version has no netting, fund reuse or credit, peak liquidity will be labelled a proxy.
- **Planned experiments:** (1) baseline, (2) volume stress, (3) liquidity stress, (4) delay and failure stress. Conditions will be repeated over several random seeds to show variation, not only averages.
- **Reproducibility:** all data is simulated. Random seeds are configurable, and each run saves its seed, input data and parameters with its output.

## Installation

Requires Python 3 (developed and tested on macOS with Python 3.14). From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Only the transaction generator is available today.

```bash
python -m src.transactions
```

This writes two files:

- `data/sample_transactions.csv`: 100 synthetic USD/JPY transactions (seed 42, 2 banks, one arrival every 10 seconds). Columns: `transaction_id`, `arrival_time`, `usd_payer`, `jpy_payer`, `usd_amount`, `jpy_amount`, `fx_rate`, `failure_draw`.
- `data/sample_transactions_meta.json`: the parameters used to generate them.

The data uses a fixed USD/JPY rate of 150.00. This is an illustrative simplification, not a market observation or forecast.

## Project status

| Component | Status |
|---|---|
| Synthetic transaction generator (`src/transactions.py`) | Implemented (Day 1, extended Day 5) |
| Settlement simulator (`src/simulator.py`) | Models A (Day 6), B and C (Day 7) implemented |
| Metrics and experiments | Planned |
| Streamlit dashboard | Planned |
| Research report, policy brief, presentation | Planned |

The plan runs for 21 days. This README will be updated as components are added.

## Results

No experiments have been run yet. This section will be filled in only from CSV files generated by the code in this repository.

## Limitations

- The models are simplified. They are not replicas of correspondent banking, tokenized bank deposits, CLS, RTGS systems or any other production infrastructure.
- All data is synthetic. Parameters are illustrative and are not calibrated to real markets, banks or failure rates.
- Smart-contract-style completion in a simulation is not legal settlement finality. Legal finality depends on legal and regulatory frameworks that this project does not model.
- Atomic PvP can reduce principal risk, meaning the risk that one leg settles and the other does not. It does not remove liquidity risk, because participants still need funds available to settle.
- The first version excludes netting, credit, intraday liquidity facilities, multi-currency routing and market-price movement.
- Any finding will hold only under the implemented models and assumptions.

## Disclaimer

This is an independent, unofficial research prototype using simulated data. It is not affiliated with, endorsed by, or produced in collaboration with any central bank, international organisation, settlement system operator or financial institution. It connects to no real funds, bank accounts or bank APIs, wallets, Ethereum or other blockchain networks, or production tokens. Nothing here is financial, legal or policy advice.

Related public work, such as BIS Project Agora, is cited for context only. This project does not reproduce it or claim any connection to it.

## License

MIT
