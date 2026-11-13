# Literature Review (first draft)

Status: Day 2 draft (2026-11-02), external claims verified against the original sources on Day 16 (2026-11-13). Source IDs refer to `sources.md`. On Day 16 the PDF claims were re-checked against the page images of the local PDFs, and the web claims against the official pages as returned by a fetch tool (a model-made summary of each page, not raw HTML). Claims marked "Verified" below were checked that way. Exact wording of web quotes should still be compared in a browser before the final report quotes them verbatim. Claims we could not verify are marked "NOT VERIFIED" or were removed. Keyword searches over whole PDFs (for example "no USD/JPY test") were done on Day 2 and were not re-run on Day 16; they are marked as such. This is an independent research prototype using synthetic data. No institution named here has reviewed, approved, or endorsed it.

In each section we try to keep apart: (a) what a source says, (b) what our simplified model does, and (c) our own interpretation.

## 1. FX settlement risk concepts

An FX trade has two payment legs, for example USD and JPY. Settlement risk arises when one leg can settle without the other.

CLS describes Herstatt risk, named after the 1974 failure of Herstatt Bank, as the risk of paying the currency sold without receiving the currency bought (CLS-4; CLS's own description).

Verified against CLS-4, PDF p.2 / printed p.2, checked 2026-11-13.

Three risk terms are used in this study. The wording below is OSFI's glossary (OSFI-1), which says it is based on a Basel Committee paper (BCBS-1):

- Principal risk (OSFI): "The risk of outright loss of the full value of a transaction resulting from the counterparty's failure to settle."
- Replacement cost risk (OSFI): "The risk of loss due to unsettled transactions with a counterparty." The exposure is the cost of replacing the original transaction at current market prices.
- Liquidity risk (OSFI): "The risk that a bank is unable to make payments due to a shortage of liquidity arising from a counterparty (or participant in a settlement system) not settling an obligation for full value when due." OSFI notes this does not imply insolvency, because the counterparty may settle later.

OSFI says PvP ensures the final transfer of a payment in one currency if, and only if, a final transfer in the other currency occurs (OSFI-1, Annex para. 24 and Glossary). It says PvP arrangements are designed to eliminate principal risk but "will not eliminate a bank's replacement cost risk or liquidity risk" (OSFI-1, sec. 2.1), and that "PVP arrangements do not guarantee settlement" (OSFI-1, Annex para. 24). It adds that some trades cannot use PvP, such as trades in certain products or currencies, certain same-day trades, and trades with counterparties not eligible for PvP (sec. 2.2).

The Basel Committee guidance (2013) says banks should eliminate principal risk by using PvP "where practicable", and use netting and collateral to reduce replacement cost risk (BCBS-1, PDF p.9 / printed p.3; Guideline 2, para. 3.2.1, PDF p.17 / printed p.11). The sentence that PvP "will not eliminate a bank's replacement cost risk or liquidity risk" also appears there (para. 3.2.1), and para. 24 of the Annex says PvP arrangements do not guarantee settlement (PDF p.37 / printed p.31). The glossary definitions of principal risk, replacement cost risk and liquidity risk match the OSFI wording quoted above (BCBS-1, PDF pp.40-42 / printed pp.34-36; the BCBS principal risk entry adds a further sentence).

Verified on 2026-11-13: BCBS-1 against the local PDF (pages above). OSFI-1 against the official page (published 2013-06-30, modified 2018-11-07; the Basel basis is stated in its Introduction). Correction made on Day 16: the earlier text cited "do not guarantee settlement" and the "if and only if" wording to OSFI sec. 2.1; they are in the Annex (para. 24), and only the "will not eliminate" sentence is in sec. 2.1. Not verified: the OSFI guideline label "E-24" (not used).

(b) Our model: principal exposure and the liquidity measures are defined in the methodology (Day 3). The MVP does not model replacement cost risk or market prices.

(c) Our interpretation: because OSFI says PvP leaves liquidity risk in place, a liquidity-demand metric belongs in the comparison next to principal exposure.

## 2. Existing infrastructure

### CLS (PvP)

CLS says it settles trades "simultaneously" using a "unique payment-versus-payment system (PvP)" with multilateral netting (CLS-3). OSFI calls CLS "the industry standard for PvP settlement of FX-related trades" (OSFI-1, footnote to sec. 7.2). CLS lists 18 eligible currencies, including USD (central bank: Federal Reserve Bank of New York) and JPY (Bank of Japan) (CLS-2).

Verified 2026-11-13: CLS-3 and CLS-2 on the official CLS pages (CLS-2 lists 18 currencies, each with its central bank); OSFI-1 on the official page. The CLS-4 footnote 18 (PDF p.6) lists the same 18 currency codes, including JPY and USD.

CLS's own claims, not independently verified by us:
- Funding requirements are cut by more than 96% (CLS-3; no method shown).
- Reliance on non-PvP settlement fell from 85% to 22% of FX traffic over 25 years, which CLS attributes mainly to CLS, and its PvP share has levelled off at about one third (CLS-4, PDF p.3). The sentence has no citation of its own; Figure 1 has a source note naming the BIS Triennial Survey and Kos / Levich (2016), and CLS attributes the 22% to the 2022 Triennial Survey (PDF p.7).
- More than USD 8 trillion settled on an average day (CLS-1; the home page shows "8.0+" USD trillion "settled on average every day" with no reference date or period; the page footer's 2026 is a copyright year, not a data date).

Verified 2026-11-13: CLS-3 "shrinks funding requirements by over 96%" and CLS-1 "8.0+ USD trillion" against the official pages; CLS-4 85%-to-22%, "stabilized at around one third", Figure 1 source note and the 22% / USD 1.6 trillion attribution against the local PDF (PDF pp.3, 7). The CLS-4 text says "over the past 25 years", "primarily because of CLS". These are CLS's claims, not tested by us.

(c) Our inference: a funding reduction below 100% suggests funding is reduced, not removed. We do not use any CLS figure as an input or a validation target.

### BOJ-NET and FXYCS

The most relevant opened BOJ item is a 2007 BOJ Review article on Japan's experience since 2002 (BOJ-8). With data to 2006, BOJ authors say a significant portion of yen FX payments moved from FXYCS to CLS after September 2002 (BOJ-8, PDF p.1), and that the RTGS share in FXYCS rose from less than 2% in 2001 to nearly 30% in 2006 (PDF p.4). They say CLS yen pay-ins and pay-outs go through BOJ-NET (PDF pp.2, 4). These figures describe 2006, not current operations.

BOJ says CLS yen settlements go through BOJ-NET (BOJ-10, PDF pp.4, 15). BOJ-10 (July 2025) names the Japanese Bankers Association as FXYCS operator (PDF p.9) and says FXYCS moved to RTGS on BOJ-NET in 2008 (PDF p.15). BOJ-10 was read in part. The March 2026 announcement remains UNVERIFIED.

Verified 2026-11-13 against the local PDFs: BOJ-8 PDF pp.1, 2, 4 (the FXYCS and CLS statements above; the 2% and nearly 30% RTGS share is Chart 3 text on p.4); BOJ-10 cover (July 2025), PDF p.4 / printed p.3 (home accounts used for CLS yen settlement), PDF p.9 / printed p.8 (Japanese Bankers Association operates FXYCS; note under Chart 3-1), PDF p.15 / printed p.14 (FXYCS and Zengin large-value payments shifted to BOJ-NET RTGS "in 2008 and 2011, respectively"). Note that BOJ-8 (2007) names the Tokyo Bankers Association as FXYCS owner and operator, and BOJ-10 (2025) names the Japanese Bankers Association; give the year with the name. The March 2026 announcement: the only support is the sentence in BOJ-6 (Kamiyama), see section 3.

(c) Our interpretation: the 2007 article gives a Japan-specific reason to track yen liquidity demand, in addition to risk. It does not test our hypotheses.

## 3. Tokenization initiatives

### BIS Project Agorá

What the sources say (BIS-1, BIS-2, BIS-3). The stated objective is to test whether a shared, programmable platform for multi-currency wholesale cross-border payments is desirable, feasible, and viable. The report summary describes tokenised commercial bank deposits combined with tokenised central bank reserves, atomic multi-currency settlement that could run around the clock, and smart contracts. The convenors are the BIS and the Institute of International Finance (BIS-2, Executive summary, PDF p.6 / printed p.1; the BIS-1 page text itself says "convened by the Institute of International Finance"). The media release of 27 May 2026 lists seven central banks (Bank of England, Federal Reserve Bank of New York, Bank of France for the Eurosystem, Bank of Japan, Bank of Korea, Bank of Mexico, Swiss National Bank) and more than 40 private financial institutions, says the Bank of Canada has since joined, and says work will advance to real-value testing. It says atomic ("all-or-nothing") settlement "is achievable securely across currencies and jurisdictions"; this is BIS's own claim. BIS says Innovation Hub projects are experimental (media release, notes to editors). BIS-1 says Project Agorá "is not about building a finished product but rather has delivered a prototype"; no production launch is stated.

Verified 2026-11-13: BIS-3 (media release, also at bis.org/press/p260527.htm), BIS-1 (https://www.bis.org/about/bisih/topics/fmis/agora.htm), the report landing page othp110 (dated 27 May 2026, "seven central banks and more than 40 regulated financial institutions"), and BIS-2 PDF p.6 / printed p.1.

Claims from the BIS Project Agorá web pages only (BIS-1 and its real-value testing sub-page https://www.bis.org/about/bisih/topics/fmis/agora/rvt.htm, which show the same content), not backed by a second primary document we opened: real-value testing (RVT) took place in July 2026, with approximately CHF 800,000 across 30 transactions in 17 scenarios and an average time from payment initiation to settlement of approximately 80 seconds. BIS-1 lists JPY among the six currencies used (CHF, EUR, GBP, JPY, KRW, USD), and the Bank of Japan among five testing central banks. It says two PvP scenarios were tested (CHF-GBP and GBP-USD), so no JPY PvP scenario is listed. BIS-1 says funds were locked before atomic settlement ("This triggered the locking of funds and the subsequent atomic settlement"), and that for dual-currency transactions "the cross-currency provider manually confirmed the corresponding amount". It says 28 financial institutions and central banks took part, but the table lists 22 institutions plus five central banks, so we do not quote a participant count. Its header "last updated 27 May 2026" is older than its own July 2026 content and a video dated 29 Oct 2026, so we treat these as that page's claims.

Correction made on Day 16: the earlier text listed "no integration with RTGS or core banking systems" as an RVT finding. BIS-1 says that "despite the prototype not being integrated with existing RTGS and core banking systems" settlement took about 80 seconds, but also says "Testing in the RVT environment incorporated central banks' RTGS systems and participants' core banking systems". The BIS-1 page is therefore inconsistent on this point, and the report says interoperability with external infrastructures such as domestic RTGS systems and core banking was not tested for the prototype (BIS-2 PDF p.87 / printed p.82). We no longer state RTGS integration either way for the RVT. The earlier phrase "manually confirm converted amounts" was also changed to the page's wording, "corresponding amount".

The 97-page report and the FAQ were checked against the local PDFs, the report only in part. The report's landing-page date (27 May 2026) is before the July 2026 testing that BIS-1 describes, so the absence of these figures from the report neither confirms nor contradicts them. They remain single-source (BIS web pages only). We do not use these figures as inputs to, or validation of, our results; the setting is different.

Time-dependent status, from the official BIS pages checked 2026-11-13: Project Agorá is listed as an ongoing BIS Innovation Hub project; the report was published 27 May 2026; the BIS-1 page says eight central banks (the seven above plus the Bank of Canada) and over 40 financial institutions are involved, that real-value testing was conducted in July 2026, and that "testing will continue". The page does not give a commercial deployment date.

The report's summary says the legal analysis "highlighted settlement finality is achievable across all seven participating jurisdictions", with further work needed on requirements (BIS-2, PDF p.7 / printed p.2). The report says its legal analysis "does not make definitive legal determinations" (PDF p.61 / printed p.56), and that differences in legal effects across jurisdictions "could create operational risks" (PDF p.88 / printed p.83). The report says an operating model and its legal characterisation in each jurisdiction were out of scope (PDF p.71 / printed p.66). The phrase "under review" attributed to BIS-1 is NOT on the BIS-1 page as read on 2026-11-13 (the page says only that the project "is examining how tokenised central bank reserves and commercial bank deposits can comply with existing rules on issues like settlement finality" and reports no finding). The earlier mention of "under review" has therefore been removed from the BIS-1 description; there is nothing to compare.

Verified 2026-11-13 against BIS-2 PDF pp.7, 61, 71, 88 (page images re-read).

Not re-run on Day 16: the whole-report keyword searches. On Day 2 a search of the report (USD, JPY, yen, Japan, dollar) found no USD/JPY PvP test, and a separate search (terms in `sources.md`) found no quantified liquidity or settlement-risk result. On Day 16 I re-read the pages cited here and found nothing that contradicts this. BIS-1 lists two PvP scenarios in real-value testing (CHF-GBP and GBP-USD), neither USD/JPY. A GBP/JPY liquidity-balancing journey ("Journey 3", Crown Bank London) is an illustration, not a test; it prepares a PvP instruction in the Agorá prototype (PDF pp.85-87 / printed pp.80-82). BIS says benefits "will only be quantifiable when applied to more realistic conditions" (PDF p.81 / printed p.76).

The HANDOFF URL for the Agorá page (bis.org/project/agora.htm) returned 404 on 2026-11-13. The URL without ".htm" (https://www.bis.org/project/agora) shows the same Project Agorá page. We cite the URL in `sources.md`. The phrase "tokenised correspondent banking" was not found on any official page we opened, so we do not use it; the PDF search for it was done on Day 2. BIS writes "preserves correspondent banking as the backbone of global payments" (BIS-2, PDF p.6 / printed p.1, verified 2026-11-13).

### Bank of Canada

The Bank of Canada joined Agorá (BOC-1, 27 May 2026). Its release says "The global project involves seven other central banks", so the Bank of Canada makes eight; the release does not use the word "eighth". It describes "a multi-currency unified ledger that enables atomic settlement of cross-border wholesale transactions", says "The project will continue to test the prototype", and says the project will examine how such a platform can work within existing legal and regulatory frameworks, including settlement finality rules.

Verified 2026-11-13 against the official Bank of Canada release. BIS-1 also says eight central banks.

### Bank of Japan

BOJ materials we opened describe exploration, not production:
- 2020 to 2025 (BOJ-1 to BOJ-4): in October 2020 the Bank said it "currently has no plan to issue CBDC" (BOJ-1); staff papers survey foreign wholesale CBDC experiments (BOJ-2, 2023) and deposit tokenization, noting open private-law and smart-contract issues (BOJ-3, 2024); and a 2025 working paper says legal stability concerning rights is essential for tokenized assets (BOJ-4). The BOJ Review and Working Paper authors' views are their own, not necessarily the Bank's.

Verified 2026-11-13 against the abstracts on the official BOJ pages (BOJ-1 to BOJ-4). Only the abstracts were read; the full papers were not opened.
- 16 May 2026, Deputy Governor Himino: tokenized deposits plus tokenized central bank reserves presented as one option for the future monetary system, alongside stablecoins and CBDC (he calls them "candidates for foundations of the future monetary system"); the BOJ "has internally begun a sandbox project to explore the technical feasibility of tokenizing Bank of Japan reserves"; "The Bank of Japan and four Japanese commercial banks are participating" in Agorá (BOJ-5). Correction made on Day 16: the earlier text said "an alternative to CBDC or stablecoins"; the speech does not say that, it lists the options side by side.
- 29 May 2026, Executive Director Kamiyama (opening remarks at the 11th Meeting of the Liaison and Coordination Committee on CBDC): says "In March of this year, the Bank announced its plan to explore the possibilities of tokenized current account deposits at the Bank" (wholesale CBDC), that the Bank intends to advance discussions on the "DLT Sandbox Project" within the CBDC Forum, and that Agorá involves seven central banks and over 40 private institutions with real-value testing planned next (BOJ-6). The date is resolved: the speech page and the BOJ speeches index both show 29 May 2026. The URL file name (ko260611a) suggests 11 June; this was not explained, and we use the date shown on the page. BOJ-5 and BOJ-6 describe the sandbox differently (internal vs. in the CBDC Forum); we do not say which, or whether they are the same project.

Verified 2026-11-13 against the official BOJ pages (BOJ-5, BOJ-6, and the speeches index). Neither speech discusses FX settlement, CLS or PvP (checked on the pages). The March 2026 announcement itself (a primary BOJ release) was searched for and not found, so it is NOT VERIFIED beyond the Kamiyama sentence above. Project Stella and the CBDC pilot reports were not opened (NOT VERIFIED).

BOJ says FX is now settled with a relatively small amount of intraday liquidity because CLS Bank "provides a kind of multilateral netting effect", and that if liquidity needs increase substantially on a common platform, "market participants would likely avoid using the platform for foreign exchange settlement purposes" (BOJ-7, Chapter VII, PDF p.10). This is BOJ's view, not a test result. Verified 2026-11-13 against BOJ-7 PDF p.10 / printed p.10 (page image; both quoted phrases match, and the text says "at present" for the current situation and "after the transition to a common platform" for the second sentence). The report is dated 2024-09-10, so "now" means September 2024.

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

Verified 2026-11-13 against BIS-2 PDF pp.56-57 / printed pp.51-52 (commit-or-cancel, single PvP coordinator, locks, configured timeouts, "both legs commit together or both cancel together") and p.70 / printed p.65 (updates "may occur asynchronously, but all follow the issuance of the atomic settlement trigger"). PDF pp.48-55 were not re-read on Day 16 and rest on the Day 2 reading.

What we add, if anything: a transparent, reproducible comparison of trade-offs in principal exposure, liquidity needs, and delay under changing conditions, focused on USD/JPY. Whether this adds anything beyond existing work is still to be judged. Conclusions would apply only to the simplified model.

The hypotheses H1-H4 (see `hypotheses.md`) are things to test, not conclusions. Each result will be recorded as supported, not supported, or inconclusive.

## 5. Gaps and open items

Source gaps:
1. The Agorá report was read in part (see `sources.md`). BIS describes failure handling in the prototype workflow. Quantified liquidity or settlement-risk findings were not found.
2. Agorá July 2026 real-value testing claims rest on BIS web pages only (BIS-1 and its RVT sub-page), whose header date is stale. No second primary document was found on 2026-11-13. BIS-1 is also inconsistent about RTGS and core banking integration.
3. The BOJ-NET disclosure was read in part. The March 2026 BOJ announcement is still not verified (only Kamiyama's sentence supports it).
4. Resolved on Day 16: the Kamiyama speech date is 29 May 2026 (page and index). The URL file name is unexplained.
5. Whole-PDF keyword searches (no USD/JPY test, no quantified result) were not re-run on Day 16.

Closed on 2026-11-02:
- BCBS annex definitions: read (PDF pp.33-34, 40-42).
- Why trades are not PvP-settled: reasons given by CLS (CLS-4, PDF pp.5-7).
- FXYCS operation and CLS-JPY settlement via BOJ-NET: described in BOJ-8 and BOJ-10.
- BOJ-8 (2007): read; charts not read numerically.

Modelling gaps: no netting, credit lines, or fund reuse in the MVP, so peak liquidity is a proxy and not the same as gross prefunding; synthetic parameters do not represent real bank liquidity or failure rates; no replacement cost risk and no legal finality.

Future research (out of scope): compare Agorá's two-layer structure with our Models B and C; Project Stella findings on DvP/PvP; Cross-border DVP Link; ISO 20022 for BOJ-NET; other currency pairs; legal settlement finality; CPMI-IOSCO PFMI Principle 12 and BIS Triennial Survey data on FX volumes and non-PvP share.

BIS says netting and batch PvP are beyond the prototype (BIS-2, PDF p.57) and lists liquidity needs from gross settlement as a future topic (PDF p.91). Our own exclusion of netting is a design choice. Verified 2026-11-13 against BIS-2 PDF p.57 / printed p.52 and PDF p.91 / printed p.86 ("potential liquidity demands arising from gross settlement, particularly as volumes scale").
