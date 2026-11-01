# Literature Review (first draft)

Status: Day 2 draft, 2026-11-01. Source IDs refer to `sources.md`. Pages were read through summaries, so quotes must be re-checked before publication. This is an independent research prototype using synthetic data. No institution named here has reviewed, approved, or endorsed it.

In each section we try to keep apart: (a) what a source says, (b) what our simplified model does, and (c) our own interpretation.

## 1. FX settlement risk concepts

An FX trade has two payment legs, for example USD and JPY. Settlement risk arises when one leg can settle without the other.

CLS describes Herstatt risk, named after the 1974 failure of Herstatt Bank, as the risk of paying the currency sold without receiving the currency bought (CLS-4; CLS's own description).

Three risk terms are used in this study. The wording below is OSFI's glossary (OSFI-1), which says it is based on a Basel Committee paper (BCBS-1):

- Principal risk (OSFI): "The risk of outright loss of the full value of a transaction resulting from the counterparty's failure to settle."
- Replacement cost risk (OSFI): "The risk of loss due to unsettled transactions with a counterparty." The exposure is the cost of replacing the original transaction at current market prices.
- Liquidity risk (OSFI): "The risk that a bank is unable to make payments due to a shortage of liquidity arising from a counterparty (or participant in a settlement system) not settling an obligation for full value when due." OSFI notes this does not imply insolvency, because the counterparty may settle later.

OSFI says PvP ensures final transfer in one currency if and only if final transfer in the other occurs. It says PvP arrangements "are designed to eliminate principal risk, but will not eliminate a bank's replacement cost risk or liquidity risk," and that PvP arrangements "do not guarantee settlement" (OSFI-1, sec. 2.1). It adds that some trades cannot use PvP, such as trades in certain products or currencies, certain same-day trades, and trades with ineligible counterparties (sec. 2.2).

The Basel Committee guidance (2013) says banks should use PvP "where practicable" to reduce principal risk, and use netting and collateral to reduce replacement cost risk (BCBS-1). We did not read its annex, so we use OSFI's glossary for definitions.

(b) Our model: principal exposure and the liquidity measures are defined in the methodology (Day 3). The MVP does not model replacement cost risk or market prices.

(c) Our interpretation: because OSFI says PvP leaves liquidity risk in place, a liquidity-demand metric belongs in the comparison next to principal exposure.

## 2. Existing infrastructure

### CLS (PvP)

CLS says it settles trades "simultaneously" using a "unique payment-versus-payment system (PvP)" with multilateral netting (CLS-3). OSFI calls CLS "the industry standard for PvP settlement of FX-related trades" (OSFI-1). CLS lists 18 eligible currencies, including USD (central bank: Federal Reserve Bank of New York) and JPY (Bank of Japan) (CLS-2).

CLS's own claims, not independently verified by us:
- Funding requirements are cut by more than 96% (CLS-3; no method shown).
- Reliance on non-PvP settlement fell from 85% to 22% of FX traffic over 25 years, "primarily because of CLS", and CLS PvP share has stabilized at around one third of traded gross notional (CLS-4; no external source cited).
- More than USD 8 trillion settled on an average day (CLS-1; undated).

(c) Our inference: a funding reduction below 100% suggests funding is reduced, not removed. We do not use any CLS figure as an input or a validation target.

### BOJ-NET and FXYCS

The most relevant opened BOJ item is a 2007 BOJ Review article on Japan's experience since 2002 (BOJ-8). From its abstract only: after CLS launched in September 2002, a large value of yen payments moved from FXYCS to CLS; the liquidity needed to settle FXYCS rose; and the CLS design created time-critical payments in BOJ-NET and more interdependence among RTGS systems. We read the abstract only.

Current FXYCS operation, how CLS settles JPY through BOJ-NET, and BOJ-NET operating details are UNVERIFIED. A search summary mentioned them, but we did not open a page that confirms them, so we make no claim. The BOJ-NET PFMI disclosure (31 Jul 2025 edition) is listed on a BOJ page but was not opened (BOJ-10).

(c) Our interpretation: the 2007 abstract gives a Japan-specific reason to track yen liquidity demand, in addition to risk. It does not test our hypotheses.

## 3. Tokenization initiatives

### BIS Project Agorá

What the sources say (BIS-1, BIS-2, BIS-3). The stated objective is to test whether a shared, programmable platform for multi-currency wholesale cross-border payments is desirable, feasible, and viable. The report summary describes tokenised commercial bank deposits combined with tokenised central bank reserves, atomic multi-currency settlement, possible 24/7 operation, and smart contracts. The convenors are the BIS and the Institute of International Finance. The media release of 27 May 2026 lists seven central banks, including the Bank of Japan, and more than 40 private financial institutions, and says work will advance to real-value testing. It says all-or-nothing settlement "is achievable securely across currencies and jurisdictions"; this is BIS's own claim. BIS says Innovation Hub projects are experimental, and no production launch is stated.

Claims from one BIS page only (BIS-1), not backed by a second source we opened: real-value testing was completed in July 2026, with about CHF 800,000 across 30 transactions in 17 scenarios, an average initiation-to-settlement time of about 80 seconds, and no integration with RTGS or core banking systems. BIS-1 also says two PvP scenarios were tested (CHF-GBP and GBP-USD), that funds are locked before settlement (our paraphrase), and that a cross-currency provider had to manually confirm converted amounts in dual-currency payments. Its header date (27 May 2026) conflicts with its content, so we treat these as that page's claims. The 97-page report and the FAQ were not readable (UNVERIFIED). We do not use these figures as inputs to, or validation of, our results; the setting is different.

Discrepancy on finality: BIS-1 says settlement finality is "under review", while BIS-3 says finality is achievable in all seven participating jurisdictions, with technical, operational, and contractual requirements still to be defined. We do not reconcile the two.

No Agorá test of USD/JPY PvP is reported on the pages we read. We found no quantitative settlement-risk or liquidity results there. Whether the full report has any is UNVERIFIED.

The HANDOFF URL for the Agorá page (bis.org/project/agora.htm) returned 404; we use the URL in `sources.md`. The phrase "tokenised correspondent banking" was not found on any official page we opened, so we do not use it.

### Bank of Canada

The Bank of Canada joined Agorá as the eighth central bank (BOC-1, 27 May 2026). It describes "a multi-currency unified ledger that enables atomic settlement of cross-border wholesale transactions", says it will keep testing the prototype, and will examine how such a platform fits legal and regulatory frameworks, including settlement finality.

### Bank of Japan

BOJ materials we opened describe exploration, not production:
- 2020 to 2025 (BOJ-1 to BOJ-4): no CBDC issuance plan in 2020; staff papers survey foreign wholesale CBDC experiments and deposit tokenization; open private-law and smart-contract issues; legal certainty is a prerequisite for tokenized assets.
- May 2026, Deputy Governor Himino: tokenized deposits plus tokenized central bank reserves as an alternative to CBDC or stablecoins; a BOJ sandbox on tokenizing reserves; BOJ and four Japanese commercial banks join Agorá (BOJ-5).
- Executive Director Kamiyama: March 2026 BOJ plan to explore tokenized current account deposits at BOJ, and a DLT Sandbox Project in the CBDC Forum (BOJ-6). Its date is inconsistent (index page 29 May 2026; URL suggests 11 June 2026), so it needs checking. BOJ-5 and BOJ-6 describe the sandbox differently (internal vs. in the CBDC Forum); we do not say which.

Neither speech, as summarized, discusses FX settlement or CLS. Project Stella and the CBDC pilot reports were not opened (UNVERIFIED).

## 4. How this study differs from existing infrastructure and initiatives

Existing systems and projects (CLS, BOJ-NET and FXYCS, Agorá, BOJ and BoC work) are real institutional arrangements or experiments. Our study is a small Python simulation on synthetic USD/JPY data. It does not connect to any real platform, reproduce CLS algorithms, model legal settlement finality, or replicate Agorá.

Our three models:

| Model | What our model does |
|---|---|
| A: Sequential | Processes the USD and JPY legs independently with a time gap, so one leg can settle alone. |
| B: Prefunded Tokenized | Reserves each currency before settlement, then processes tokenized assets. |
| C: Atomic PvP | Validates both legs, then commits them together. Either both settle or neither does. |

Mapping to real-world concepts. We read Model A as similar in spirit to non-PvP settlement, Model B as similar to prefunding or locking funds, and Model C as similar to PvP or atomic settlement. This mapping is OUR interpretation. No institution states it. Several points limit it:
- Model A is an abstraction ("time-gapped independent settlement"), not a reproduction of correspondent banking.
- Model B does not reproduce the legal or operational structure of tokenized deposits or central bank reserves.
- Prefunding and atomicity are separate ideas in our model. A balance check does not make Model C atomic; the commit must be all-or-nothing.
- The Agorá pages we read describe locked funds and atomic settlement only briefly, so any resemblance to our Models B and C is our reading.

What we add, if anything: a transparent, reproducible comparison of trade-offs in principal exposure, liquidity needs, and delay under changing conditions, focused on USD/JPY. Whether this adds anything beyond existing work is still to be judged. Conclusions would apply only to the simplified model.

The hypotheses H1-H4 (see `hypotheses.md`) are things to test, not conclusions. Each result will be recorded as supported, not supported, or inconclusive.

## 5. Gaps and open items

Source gaps:
1. The Agorá 97-page report and FAQ were not read; failure handling, rollback, and any quantified liquidity or settlement-risk findings are UNVERIFIED.
2. Agorá July 2026 real-value testing claims rest on one BIS page with an inconsistent header date. Find a second official source.
3. BCBS annex definitions (p.33) not read.
4. Why trades are not PvP-settled (CLS-4 PDF) not obtained.
5. FXYCS operation, CLS-JPY settlement via BOJ-NET, the BOJ-NET PFMI disclosure, and the March 2026 BOJ announcement were not verified.
6. The Kamiyama speech date needs resolving.
7. Full text of BOJ-8 (2007) not read.

Modelling gaps: no netting, credit lines, or fund reuse in the MVP, so peak liquidity is a proxy and not the same as gross prefunding; synthetic parameters do not represent real bank liquidity or failure rates; no replacement cost risk and no legal finality.

Future research (out of scope): compare Agorá's two-layer structure with our Models B and C; Project Stella findings on DvP/PvP; Cross-border DVP Link; ISO 20022 for BOJ-NET; other currency pairs; legal settlement finality; CPMI-IOSCO PFMI Principle 12 and BIS Triennial Survey data on FX volumes and non-PvP share.
