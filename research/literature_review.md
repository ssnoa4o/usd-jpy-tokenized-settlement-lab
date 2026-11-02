# Literature Review (first draft)

Status: Day 2 draft, updated 2026-11-02. Source IDs refer to `sources.md`. HTML pages were read through summaries and must be re-checked before quoting. Seven PDFs were read from extracted text on 2026-11-02, some only in part; pages are listed in `sources.md`. This is an independent research prototype using synthetic data. No institution named here has reviewed, approved, or endorsed it.

In each section we try to keep apart: (a) what a source says, (b) what our simplified model does, and (c) our own interpretation.

## 1. FX settlement risk concepts

An FX trade has two payment legs, for example USD and JPY. Settlement risk arises when one leg can settle without the other.

CLS describes Herstatt risk, named after the 1974 failure of Herstatt Bank, as the risk of paying the currency sold without receiving the currency bought (CLS-4; CLS's own description).

Three risk terms are used in this study. The wording below is OSFI's glossary (OSFI-1), which says it is based on a Basel Committee paper (BCBS-1):

- Principal risk (OSFI): "The risk of outright loss of the full value of a transaction resulting from the counterparty's failure to settle."
- Replacement cost risk (OSFI): "The risk of loss due to unsettled transactions with a counterparty." The exposure is the cost of replacing the original transaction at current market prices.
- Liquidity risk (OSFI): "The risk that a bank is unable to make payments due to a shortage of liquidity arising from a counterparty (or participant in a settlement system) not settling an obligation for full value when due." OSFI notes this does not imply insolvency, because the counterparty may settle later.

OSFI says PvP ensures final transfer in one currency if and only if final transfer in the other occurs. It says PvP arrangements "are designed to eliminate principal risk, but will not eliminate a bank's replacement cost risk or liquidity risk," and that PvP arrangements "do not guarantee settlement" (OSFI-1, sec. 2.1). It adds that some trades cannot use PvP, such as trades in certain products or currencies, certain same-day trades, and trades with ineligible counterparties (sec. 2.2).

The Basel Committee guidance (2013) says banks should use PvP "where practicable" to reduce principal risk, and use netting and collateral to reduce replacement cost risk (BCBS-1). The opening definitions in the Basel Committee glossary match the OSFI wording quoted above (BCBS-1, PDF pp.40-42 / printed pp.34-36).

(b) Our model: principal exposure and the liquidity measures are defined in the methodology (Day 3). The MVP does not model replacement cost risk or market prices.

(c) Our interpretation: because OSFI says PvP leaves liquidity risk in place, a liquidity-demand metric belongs in the comparison next to principal exposure.

## 2. Existing infrastructure

### CLS (PvP)

CLS says it settles trades "simultaneously" using a "unique payment-versus-payment system (PvP)" with multilateral netting (CLS-3). OSFI calls CLS "the industry standard for PvP settlement of FX-related trades" (OSFI-1). CLS lists 18 eligible currencies, including USD (central bank: Federal Reserve Bank of New York) and JPY (Bank of Japan) (CLS-2).

CLS's own claims, not independently verified by us:
- Funding requirements are cut by more than 96% (CLS-3; no method shown).
- Reliance on non-PvP settlement fell from 85% to 22% of FX traffic over 25 years, which CLS attributes mainly to CLS, and its PvP share has levelled off at about one third (CLS-4, PDF p.3). The sentence has no citation of its own; Figure 1 has a source note naming the BIS Triennial Survey and Kos / Levich (2016), and CLS attributes the 22% to the 2022 Triennial Survey (PDF p.7).
- More than USD 8 trillion settled on an average day (CLS-1; undated).

(c) Our inference: a funding reduction below 100% suggests funding is reduced, not removed. We do not use any CLS figure as an input or a validation target.

### BOJ-NET and FXYCS

The most relevant opened BOJ item is a 2007 BOJ Review article on Japan's experience since 2002 (BOJ-8). With data to 2006, BOJ authors say a significant portion of yen FX payments moved from FXYCS to CLS after September 2002 (BOJ-8, PDF p.1), and that the RTGS share in FXYCS rose from less than 2% in 2001 to nearly 30% in 2006 (PDF p.4). They say CLS yen pay-ins and pay-outs go through BOJ-NET (PDF pp.2, 4). These figures describe 2006, not current operations.

BOJ says CLS yen settlements go through BOJ-NET (BOJ-10, PDF pp.4, 15). BOJ-10 (July 2025) names the Japanese Bankers Association as FXYCS operator (PDF p.9) and says FXYCS moved to RTGS on BOJ-NET in 2008 (PDF p.15). BOJ-10 was read in part. The March 2026 announcement remains UNVERIFIED.

(c) Our interpretation: the 2007 article gives a Japan-specific reason to track yen liquidity demand, in addition to risk. It does not test our hypotheses.

## 3. Tokenization initiatives

### BIS Project Agorá

What the sources say (BIS-1, BIS-2, BIS-3). The stated objective is to test whether a shared, programmable platform for multi-currency wholesale cross-border payments is desirable, feasible, and viable. The report summary describes tokenised commercial bank deposits combined with tokenised central bank reserves, atomic multi-currency settlement, possible 24/7 operation, and smart contracts. The convenors are the BIS and the Institute of International Finance. The media release of 27 May 2026 lists seven central banks, including the Bank of Japan, and more than 40 private financial institutions, and says work will advance to real-value testing. It says all-or-nothing settlement "is achievable securely across currencies and jurisdictions"; this is BIS's own claim. BIS says Innovation Hub projects are experimental, and no production launch is stated.

Claims from one BIS page only (BIS-1), not backed by a second source we opened: real-value testing was completed in July 2026, with about CHF 800,000 across 30 transactions in 17 scenarios, an average initiation-to-settlement time of about 80 seconds, and no integration with RTGS or core banking systems. BIS-1 also says two PvP scenarios were tested (CHF-GBP and GBP-USD), that funds are locked before settlement (our paraphrase), and that a cross-currency provider had to manually confirm converted amounts in dual-currency payments. Its header date (27 May 2026) conflicts with its content, so we treat these as that page's claims. The 97-page report and the FAQ were read from extracted text, the report only in part. The report's landing-page date (27 May 2026) is before the July 2026 testing that BIS-1 describes, so the absence of these figures from the report neither confirms nor contradicts them. They remain single-source. We do not use these figures as inputs to, or validation of, our results; the setting is different.

The report's summary says finality "is achievable across" all seven jurisdictions, with further work needed on requirements (BIS-2, PDF p.7); this resembles our summary-based note of BIS-3. The report says its legal analysis "does not make definitive legal determinations" (PDF p.61), and that differences in legal effects across jurisdictions "could create operational risks" (PDF p.88). The report says an operating model and its legal characterisation were out of scope (PDF pp.70-71). The phrase "under review" (BIS-1) was not found in the report. We do not call the two pages contradictory.

A search of the report (USD, JPY, yen, Japan, dollar) found no USD/JPY PvP test. A separate search (terms in `sources.md`) found no quantified liquidity or settlement-risk result. A GBP/JPY liquidity-balancing journey is an illustration, not a test (PDF pp.85-87). BIS says benefits "will only be quantifiable when applied to more realistic conditions" (PDF p.81).

The HANDOFF URL for the Agorá page (bis.org/project/agora.htm) returned 404; we use the URL in `sources.md`. The phrase "tokenised correspondent banking" was not found on any official page we opened, so we do not use it. The phrase was also not found in the seven PDFs. BIS writes "preserves correspondent banking as the backbone of global payments" (BIS-2, PDF p.6).

### Bank of Canada

The Bank of Canada joined Agorá as the eighth central bank (BOC-1, 27 May 2026). It describes "a multi-currency unified ledger that enables atomic settlement of cross-border wholesale transactions", says it will keep testing the prototype, and will examine how such a platform fits legal and regulatory frameworks, including settlement finality.

### Bank of Japan

BOJ materials we opened describe exploration, not production:
- 2020 to 2025 (BOJ-1 to BOJ-4): no CBDC issuance plan in 2020; staff papers survey foreign wholesale CBDC experiments and deposit tokenization; open private-law and smart-contract issues; legal certainty is a prerequisite for tokenized assets.
- May 2026, Deputy Governor Himino: tokenized deposits plus tokenized central bank reserves as an alternative to CBDC or stablecoins; a BOJ sandbox on tokenizing reserves; BOJ and four Japanese commercial banks join Agorá (BOJ-5).
- Executive Director Kamiyama: March 2026 BOJ plan to explore tokenized current account deposits at BOJ, and a DLT Sandbox Project in the CBDC Forum (BOJ-6). Its date is inconsistent (index page 29 May 2026; URL suggests 11 June 2026), so it needs checking. BOJ-5 and BOJ-6 describe the sandbox differently (internal vs. in the CBDC Forum); we do not say which.

Neither speech, as summarized, discusses FX settlement or CLS. Project Stella and the CBDC pilot reports were not opened (UNVERIFIED).

BOJ says FX is now settled with a relatively small amount of intraday liquidity because CLS Bank "provides a kind of multilateral netting effect", and that if liquidity needs increase substantially on a common platform, "market participants would likely avoid using the platform for foreign exchange settlement purposes" (BOJ-7, Chapter VII, PDF p.10). This is BOJ's view, not a test result.

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
- BIS describes lock, commit and cancel steps for the prototype, including timeouts and a PvP coordinator (BIS-2, PDF pp.48-57). BIS notes that not all ledger updates occur simultaneously (PDF p.70). Any resemblance to our Models B and C is our own reading.

What we add, if anything: a transparent, reproducible comparison of trade-offs in principal exposure, liquidity needs, and delay under changing conditions, focused on USD/JPY. Whether this adds anything beyond existing work is still to be judged. Conclusions would apply only to the simplified model.

The hypotheses H1-H4 (see `hypotheses.md`) are things to test, not conclusions. Each result will be recorded as supported, not supported, or inconclusive.

## 5. Gaps and open items

Source gaps:
1. The Agorá report was read in part (see `sources.md`). BIS describes failure handling in the prototype workflow. Quantified liquidity or settlement-risk findings were not found.
2. Agorá July 2026 real-value testing claims rest on one BIS page with an inconsistent header date. Find a second official source.
3. The BOJ-NET disclosure was read in part. The March 2026 BOJ announcement is still not verified.
4. The Kamiyama speech date needs resolving.

Closed on 2026-11-02:
- BCBS annex definitions: read (PDF pp.33-34, 40-42).
- Why trades are not PvP-settled: reasons given by CLS (CLS-4, PDF pp.5-7).
- FXYCS operation and CLS-JPY settlement via BOJ-NET: described in BOJ-8 and BOJ-10.
- BOJ-8 (2007): read; charts not read numerically.

Modelling gaps: no netting, credit lines, or fund reuse in the MVP, so peak liquidity is a proxy and not the same as gross prefunding; synthetic parameters do not represent real bank liquidity or failure rates; no replacement cost risk and no legal finality.

Future research (out of scope): compare Agorá's two-layer structure with our Models B and C; Project Stella findings on DvP/PvP; Cross-border DVP Link; ISO 20022 for BOJ-NET; other currency pairs; legal settlement finality; CPMI-IOSCO PFMI Principle 12 and BIS Triennial Survey data on FX volumes and non-PvP share.

BIS says netting and batch PvP are beyond the prototype (BIS-2, PDF p.57) and lists liquidity needs from gross settlement as a future topic (PDF p.91). Our own exclusion of netting is a design choice.
