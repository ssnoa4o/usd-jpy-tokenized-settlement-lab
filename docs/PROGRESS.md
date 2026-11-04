# Progress Log

毎日の終わりに Claude が追記する（やったこと / 未完了 / 次にやること / 気づき）。

## Day 0 — setup
- Claude Code 用スターターキット（CLAUDE.md, .claude/agents, .claude/skills）を配置。

## Day 1 — project setup
- 完了: `.venv`（Python 3.14.6）作成、依存導入（numpy/pandas/plotly/streamlit/pytest、requirements.txt はバージョン固定）。
- 完了: フォルダ構成、`.gitignore`、MIT `LICENSE`、英語 README 初版。
- 完了: `src/transactions.py` と `data/sample_transactions.csv`（100 件、seed 42、シードは `*_meta.json` に保存）。`tests/test_transactions.py`（16 件パス）。
- 完了: git 初期化、最初のコミット、GitHub に public で公開（`ssnoa4o/usd-jpy-tokenized-settlement-lab`、17 ファイル）。
- 判断: リポジトリは public / MIT。`CLAUDE.md`・`.claude/`・`*.docx`・`docs/HANDOFF.md`・`notes_ja/` は公開しない（作業用の内部資料のため）。
- 完了（公開後の追加作業）: `.gitignore` の見直し（鍵・シークレット・一時ファイル・個人用メモなどを追加）、`scripts/precommit_check.sh`（push 前の確認スクリプト）。
  - スクリプトは、禁止ファイル、各種キーや認証情報、暗号資産の鍵、メールアドレス、電話番号などを調べ、1 件でもあれば終了コード 1 で止まる。
  - 検証: 「止めるべきもの 11 種」「止めなくてよいもの 4 種（CSV の数字、短い `sk-`、コミット ID、日付つき数字）」の計 15 ケースが期待どおり。実リポジトリでは問題なし。
  - reviewer の指摘（ステージ済み内容が未検査、大文字小文字違いやネストしたパスの見逃し、git 管理外で OK になる等）は修正済み。
- 完了: `CLAUDE.md` に「日本語レポート」の節を追加。`notes_ja/day01.md`（個人用、非公開）を作成。
- 未完了 / 既知の制限:
  - 電話番号の検査は `=` の直後（例: `tel=090-...`）を見逃す。
  - スクリプトは既知のパターンだけを調べる安全網であり、保証ではない。push 前に `git status` も目で確認する。
  - `scripts/precommit_check.sh` は手動実行のみ（git の pre-commit フックにはしていない）。
- 次の日（Day 2）: BIS Project Agorá・日銀・CLS・OSFI の一次資料を読み、literature_review.md の初版と出典一覧を作る。

## Day 2 — literature review (first draft)
- 完了: 公式ページ（BIS Agorá / Bank of Canada / 日本銀行 / CLS / OSFI）を 3 並列で調査し、`research/research_question.md`・`research/literature_review.md`（約 1,830 語）・`research/sources.md` を作成。
- 完了: `integrity-checker` で検査。承認と読める表現・結果の先取りはなし。指摘 7 点（出典 ID の食い違い、語数、引用符、H1/H2 の書き方など）を修正済み。
- 判断: A/B/C と「非 PvP／事前資金／PvP」の対応づけは自分たちの解釈と明記。CLS・Agorá の数値は各機関の主張として扱い、入力にも検証にも使わない。
- 発見: HANDOFF の Agorá URL は 404（正しい URL は sources.md）。公式ページに "tokenised correspondent banking" の表現は見つからず、使わない。OSFI の FX 決済リスク指針（2013）は実在した。
- 未完了 / 未確認: Agorá 報告書（97 ページ）・FAQ・BCBS 付録・日銀の PDF 類は読めず UNVERIFIED。日銀 神山氏の講演の日付（5/29 か 6/11）、BIS-3 の URL の切れ、日銀の 2026 年 3 月発表の原典。Agorá の 7 月テスト結果は BIS の 1 ページのみで裏取りなし。
- 語数: literature_review.md は `wc -w` で 1,828（目標 1,800 をわずかに超過。表記号を含む）。
- 完了: `notes_ja/day02.md`（個人用・非公開。用語のたとえ話、ファイルの役割、確認クイズ 3 問つき）。
- 環境: ユーザーが `brew install poppler` を実施。`pdftotext`（`/opt/homebrew/bin/pdftotext`）を確認済み。PDF はまだ読んでいないので、UNVERIFIED の項目は変更なし（読んだら `sources.md` を更新する）。
- 次の日（Day 3）: H1〜H4 を確定し、`research/hypotheses.md`・`research/methodology.md` の初版を作る。余裕があれば poppler で Agorá 報告書・BCBS 付録などの PDF を読み、`sources.md` の UNVERIFIED を減らす。

## Day 3 — hypotheses and methodology (first draft)
- 完了: `research/hypotheses.md`（H1〜H4。冒頭に「仮説は検証対象であり結論ではない」を明記。各仮説に Supported if / Not supported if / Inconclusive if。実験前に判定ルールを固定）と `research/methodology.md`（3 モデル定義、指標の分母・分子、Exp1〜4 設計、除外範囲、未決事項）。数値はすべて (DV)＝設計値で、結果は書いていない。
- 完了: `integrity-checker` を 2 回実施。1 回目の重大指摘（Exp4 で B と A が設計上同一／H1a・H2 が定義由来／H3・H4 の判定が緩い／遅延が exposure に効かない）を修正。2 回目の指摘（範囲ルールが厳しすぎる、「同一値」の優先順位、H3 の書き方）も修正:
  - 判定は「同一シード内の差（paired）」を主にし、同一値の判定を先に行う。範囲は併記。
  - H1a（失敗確率が上がっても exposure が減らない）は設計上かならず成り立つので、必須テストに降ろした（判定対象外）。
  - H1b / H4b は、`insufficient_funds` が実際に起きる水準だけを数える。起きなければ「検証不能（Inconclusive）」。
- 完了（追加依頼）: `research_question.md` を hypotheses.md に合わせて更新。`literature_review.md` の古い 1 行を修正（仮説を結論のように書いた箇所は他になし）。`CLAUDE.md` の「制約」に仮説の扱い（結論ではない／判定ルールは実験前に固定／設計上の保証は証拠にしない）を追記。
- 完了: `notes_ja/day03.md`（個人用・非公開。ファイルを読み直して全面的に書き直し。用語のたとえ話、各ファイルの目的、確認クイズ 3 問つき）。pytest 16 件パス、`scripts/precommit_check.sh` 問題なし（src/・tests/ は未変更）。
- 判断: 判定ルールの閾値は「全 30 シード（DV）で差の符号が一致」。範囲重なりだけでは Inconclusive にしない。
- 判断（ユーザー承認）: Exp4 に H4b 用のセルを追加。資金水準はエンジン完成後に、本番と別のシード（101〜110、DV）・Model A・失敗率 0% の較正で決め、`insufficient_funds` の数だけを見る。崩れた場合は記録して基準を上げ、やり直す。
- 完了: 2 文書の重複を整理。定義は `methodology.md` に集約し、`hypotheses.md` は参照にした。`integrity-checker` で修正前のコピーと比較し、内容の欠落なし。弱くなっていた 3 点（ample が崩れたときの手順、格子の選び方、バグ検知テスト）を修正。
- 語数（`wc -w`）: 修正前 hypotheses 1,791 / methodology 2,271。整理後 hypotheses 1417 / methodology 2517（較正と必須テストの節を追加したため methodology は増加）。methodology は目標 1,500 語の対象から外す（ユーザー承認）。
- 判断（要確認）: 較正の数値「低い水準のうち 2 つ以上で不足が出る」「H4b はシードの半数以上で不足が出る最も高い水準」は Claude の提案（DV）。
- 未完了 / 既知の制限:
  - Day 4 で決める未決事項: timeout の起こし方、バースト到着の定義、予約の解除タイミング、W（未回復 partial の打ち切り時間）、N=0 のとき NaN にするか、Peak Liquidity Proxy の実装可否、3 行以上のときの銀行の組み合わせ方。
  - エンジン完成後（Day 6〜7）: 流動性の較正を実行し、「十分な資金（ample）」の基準と格子の水準を確定する。実験はまだしていない。
  - 3 点を修正したあと、`integrity-checker` は再実行していない（pytest と precommit_check は再実行済み）。
  - `research_question.md` の H2 は Gross Prefunding を Model A と比べるように読めるが、A では not applicable。Day 4 に文を直す。
  - Step 6（PDF 読み、`sources.md` の UNVERIFIED 削減）は未実施。
  - 検査役の再チェックで残った軽微な指摘（H2 の「B ≥ A」の根拠、H4b が W に依存すること）は文書に注記したのみ。
- 次の日（Day 4）: import 構成・データ型・銀行残高構造・結果レコード形式を決め、最小の pytest を作る。methodology.md の未決事項を決める。

## Day 4 — development and test skeleton
- 完了: `src/simulator.py`（`Status` / `FailureReason` / `Model` / `Currency`、`SimulationParams`、`SettlementResult`、`Leg`、`Ledger`。`run_model` は引数のみで本体は未実装）、`src/metrics.py`（`safe_ratio` のみ）、`tests/test_simulator.py`、`tests/test_metrics.py`。pytest は 67 passed / 7 skipped。skip は `methodology.md` sec. 7 の必須テスト 7 項目で、Day 6〜8 に実装する。
- 完了: `methodology.md` sec. 11 の Day 4 未決事項をすべて決定。`research_question.md` の H2 を修正。
- 判断（ユーザー承認）: Model C は到着 + 遅延で 1 回コミットする。到着は sequential 10 秒間隔、burst 100 秒ごとに 10 件。`timeout` は予約のみで発生させない。待ち行列なし。金額は整数（1/100 単位）。
- 判断（ユーザー承認、検査後の変更、実験前）: H2 の主比較を「B−A の Proxy の差、遅延 300 秒 vs 0 秒」に変更（C vs A は十分な資金のもとで障害以外では差が出ないため探索扱い）。H4b の主指標を金額ベースの Principal Exposure に変更（期間加重は W の影響が大きいため参考値）。
- 判断（Claude、検査指摘の修正）: H1b の active 条件を「全シードで A に第 2 レッグ資金不足の partial」に厳格化。H3 はグリッド端の L* を Inconclusive に。較正は A/B/C を読み、基準の倍増は最大 5 回、下側倍率の半減は最大 3 回（DV）。`run_metrics.csv` を追加。W は write-off ではなく cut-off と呼ぶ（コードは `cutoff_seconds`）。
- 検査: `reviewer` 1 回（numpy の真偽値が状態検査をすり抜ける問題などを修正）。`integrity-checker` 2 回。2 回目は高の指摘なし。
- 判断: 2 回目の「A と C の Proxy の差」の指摘は採用せず。全 USD 支払いが同じ遅延だけずれ、通貨内の順序は変わらないため。Day 7〜8 に実装で確認できる。
- 未完了 / 既知の制限:
  - 2 回目の検査後の修正（較正の上限、H4b の読み替えなど）に、`integrity-checker` は再実行していない。Week 1 ゲートで確認する。
  - 較正は失敗率 0%、本番は 1% なので、本番で ample が崩れる可能性は残る（sec. 6 のやり直し手順で扱う）。
  - 較正の上限（5 回、3 回）と「全シード」の条件は Claude の提案（DV）。
  - H4b は遅延の効果が残高経由でしか出ないので、差がほとんど出ない可能性がある。
  - PDF 読みと `sources.md` の UNVERIFIED 削減は未実施。
  - `Ledger` に両通貨を一度に予約する操作はない。Day 7 の Model B で、片方の予約失敗時に解除し忘れないよう、「失敗後は予約 0」をテストする。
- 次の日（Day 5）: `transactions.py` に `arrival_time`, `usd_payer`, `jpy_payer`, `failure_draw` を追加し、`direction` を置き換える。乱数は用途別に分ける。`Ledger` は Python の int のみ受け付けるので、numpy の整数は `to_minor` / `int()` で変換する。fx 150.00 以外では JPY の丸めに注意する。

## Day 5 — synthetic transaction data
- 完了: `src/transactions.py` を拡張。列は `transaction_id, arrival_time, usd_payer, jpy_payer, usd_amount, jpy_amount, fx_rate, failure_draw`（`direction` は削除）。引数 `n_banks`（2〜10、銀行名 A〜J）と `arrival`（sequential / burst）を追加。`bank_names()` を公開。
- 完了: `data/sample_transactions.csv` と `_meta.json` を再生成（100 件、seed 42、2 行、sequential）。乱数の取り方を変えたので値は Day 1 版からすべて変わった。これに依存する実験結果はない。
- 完了: `tests/test_transactions.py` を更新。pytest は 98 passed / 7 skipped。skip は Day 6〜8 の必須テストで変更なし。CSV は 2 回生成しても同じ。`scripts/precommit_check.sh` は問題なし。
- 完了: `methodology.md`（sec. 3 の入力形式、到着時刻は乱数なし、sec. 9 の古い `direction` の表現）と `README.md` を更新。
- 判断: 乱数は金額・銀行・失敗の 3 本。到着時刻は決定的なので乱数を使わない（`methodology.md` の「arrival も別の乱数」を修正）。
- 判断: 銀行の組は 1 回の呼び出しでまとめて引く。2 回に分けると `count` を増やしたときに先頭の行の JPY 支払行が変わるため。
- 検査: `reviewer` 1 回。高の指摘なし。弱いテストの指摘を修正（厳密比較、`failure_draw` の分布、乱数の相関、組の一様性を ±15% に、丸めの許容を 0.5 単位に）。修正後、「3 本の乱数が同じシード」「`failure_draw` が全部 0」の 2 種類のわざと壊したコードを、新しいテストが検知することを確認（コードは元に戻した）。
- 検査: `integrity-checker` 1 回。高の指摘なし。`README.md` の古い状態表示と `methodology.md` の時制を修正。`docs/HANDOFF.md` の参考コードには `direction` が残るが、当初の資料なので変更しない。
- 未完了 / 既知の制限:
  - `save_transactions` は、引数の `n_banks` / `arrival` が渡されたデータと一致するかを確認しない。numpy の整数を渡すと JSON 書き込みでエラーになる。今の呼び出し元は `__main__` のみで実害なし。
  - `reviewer` の指摘を直したあと、`reviewer` は再実行していない（pytest とわざと壊す確認は実施）。
  - Step 6（PDF 読み、`sources.md` の UNVERIFIED 削減）は、Day 5 の実装の時点では未実施（下の「追加作業」で実施）。
  - Day 10 の注意: Gross Prefunding の `jpy_amount / fx_rate` は、fx 150 以外では丸め誤差が出る。
  - Day 6 の注意: `Ledger` の銀行一覧は CSV の列からではなく `bank_names(n_banks)` から作る。取引に出ない銀行が抜けると、総流動性がずれるため。
- 完了（追加作業）: 公式 URL から PDF 7 点（BIS-2、BIS-FAQ、BCBS-1、CLS-4、BOJ-7 第 VII 章、BOJ-8、BOJ-10）を `research/pdfs/` に保存（git 管理外）。ページごとに文字を取り出して `researcher` が読み、`sources.md` を更新。ページ番号、「Local PDF copies」（URL とハッシュ値）、「Notes on BIS-2-PDF」を追加。BOJ-X を X1〜X3 に分割。
- 検査（追加作業）: 引用 18 件とハッシュ値 7 件を原文と照合して一致。`integrity-checker` 1 回、高の指摘なし。`sources.md` 内の指摘を修正（修正後の再検査はしていない）。
- 未完了（追加作業）: `literature_review.md` の修正案 13 件はユーザー承認のうえ適用済み。再検査で高の指摘なし。追加の修正案もユーザー承認のうえ適用済み（最終の文面には `integrity-checker` を再実行していない）。CLS-4 の引用は言い換えに変更。HTML 要約由来の逐語引用は、Day 20 までに原文で再確認が必要。BIS-2 と BOJ-10、BCBS-1 は一部のみ読了。BOJ-7 は第 VII 章のみ。BOJ-X3（2026 年 3 月の発表）と BIS-FAQ の日付は UNVERIFIED のまま。CLS-4 には複写や共有を制限する権利表示がある（PDF p.8）。引用は短くし、PDF は再配布しない。
- 次の日（Day 6）: Model A Sequential を実装する。2 レッグの時間差、partial、元本エクスポージャー、残高更新。

## Day 6 — Model A (Sequential)
- 完了: `src/simulator.py` の `run_model` に Model A を実装。`heapq` のイベントループ（時刻、種類、`transaction_id` の順）、USD レッグは到着時、JPY レッグは到着 + 遅延。第 2 レッグは障害判定を資金より先に見る。Model B / C は `NotImplementedError` のまま。
- 完了: `tests/test_simulator.py` に Model A のテストを追加。pytest は 187 passed / 7 skipped。skip は B / C も対象の必須テストで、Day 7〜8 に実装する。`scripts/precommit_check.sh` は問題なし。
- 完了: `research/methodology.md`（状態行、sec. 3 の `end_time`、sec. 11）と `README.md` の状態表示を更新。
- 判断（Claude）: `SimulationParams` に `n_banks`（既定 2）を追加し、銀行一覧はここから作る。`end_time` は `failed` なら到着時刻、`partial` / `settled` なら第 2 レッグの処理時刻。`start_time` は到着時刻。実行全体の集計は Day 9。`failure_draw` / `arrival_time` が NaN や inf なら `ValueError`。
- 発見: 同時刻の「第 2 レッグ」と「新しい到着」の順序は、Model A では結果を変えない。第 2 レッグは JPY だけ、到着は USD だけを動かすため。`reviewer` が順序を逆にしたコピーで比較し、差は 0 件。今はこの順序を定数の比較でしか確かめていないので、Day 7 に Model B で動作として確かめる。
- 検査: わざと壊す確認（判定順、`<` と `<=`、受取先、同時刻の順序、遅延の削除、第 2 レッグの資金判定）はすべてテストが検知し、コードは元に戻した。ただし第 2 レッグと到着の順序を逆にする変更は、定数を比べるテストでしか検知できない。
- 検査: `reviewer` 1 回。高の指摘なし。中 2 件（資金やレッグの判定を独立に確かめていない、エクスポージャーが単調性のみ）と低 3 件（誤解を招くコメント、ピーク値の手計算テスト、NaN）を修正。独立に書いた素朴な Model A との比較テストを追加した。
- 未完了 / 既知の制限:
  - 修正後に `reviewer` は再実行していない（pytest とわざと壊す確認は実施）。`integrity-checker` は Day 6 の文書変更に未実施で、Week 1 ゲートで確認する。
  - Day 7: `_sequential_result` は Model A 専用。イベントループも `_run_sequential` の中にある。B / C を足すときに一般化する。
  - Day 9: `principal_exposure_usd` は入力の浮動小数のままで、小数 3 桁以上の手書きデータでは台帳の移動額とずれる。生成データは 2 桁なので今は一致する。
  - 小数の遅延（例: 0.1 秒）では同時刻の判定に浮動小数の誤差が入る。実験の水準（0, 60, 300 秒）では起きない。
  - 流動性の較正は 3 モデルが必要なので未実施。実験も未実施で、`results/` に CSV はない。
- 次の日（Day 7）: Model B（事前資金確保）と Model C（両レッグの一括コミット）を実装する。同時刻の順序を Model B の動作テストで確かめる。

## Day 7 — Model B (Prefunded) and Model C (Atomic PvP)
- 完了: `src/simulator.py` に Model B と Model C を実装。イベントループは `_run_events` に、結果の作成は `_make_result` にまとめ、3 モデルで共通にした。モデルごとの処理は「到着時」と「遅延後」の 2 つの関数に分けた（`_HANDLERS`）。`run_model` は 3 モデルすべてを動かす（`NotImplementedError` は削除）。
  - Model B: 到着時に両レッグの予約ができるかを `Ledger.can_reserve_both` で先に確かめ、両方できるときだけ予約する。USD レッグはすぐ予約分から払う。到着 + 遅延で障害に当たれば JPY の予約を解除して `partial / technical_failure`、当たらなければ JPY を予約分から払って `settled`。
  - Model C: 到着時は何もしない。到着 + 遅延に 1 回だけ、① `Ledger.can_commit_both` で両レッグの資金を確認 ② 障害の判定 ③ `commit_both` で一括反映、の順。失敗したときは残高・予約・ピークのどれも変わらない。
- 完了: `tests/test_simulator.py` に B / C の手計算テスト、境界テスト（draw = p は当たりにならない、p = 1、遅延 0 の同時刻、n_banks = 3 で関係のない銀行が変わらない）、Model B の同時刻の順序を確かめる動作テストを追加。skip だった必須テスト 7 件のうち 6 件を実装。pytest は 517 passed / 1 skipped（skip は Day 9 の「割合の合計 = 1」）。`scripts/precommit_check.sh` は問題なし。
- 完了: `research/methodology.md`（状態行、sec. 2 の C の書き方、sec. 3 の B / C の `start_time` / `end_time`、sec. 11 の Day 7 の決定）と `README.md` の状態表示を更新。
- 判断（ユーザー承認、実験前）: Model B は予約の前に両方を確かめる。前の実装では、JPY が足りないときに USD を予約してから戻していた。そのため、何も動かなかった取引でも USD のピークが上がり、資金が足りない条件では B の Peak Liquidity Proxy が実装の都合で大きく出るおそれがあった。
- 判断（Claude）: C の `commit_both` と B の `reserve` が、確認のあとに False を返した場合は `RuntimeError` にする（何も動かずに `settled` と記録されるのを防ぐ）。
- 発見: 同時刻の順序（遅延後の処理が新しい到着より先）は Model B で結果を変える。動作テスト 3 件で確かめた（順序を逆にした変更をテストが検知した）。
- 検査: わざと壊す確認（C で障害の判定を資金より先にする、B で USD を先に予約する、イベント順を逆にする、C で片方のレッグを先に動かす、`<` を `<=` にする）はすべてテストが検知し、コードは元に戻した。
- 検査: `reviewer` 2 回。1 回目は高の指摘なし。中 2 件（B のピーク、B / C の境界テスト）と低 1 件（`commit_both` の戻り値）を修正した。2 回目は高・中の指摘なし。低 1 件（methodology sec. 2 の「コピーで確認」という古い書き方）を修正した。
- 未完了 / 既知の制限:
  - 小数の遅延では、`time + delay` の浮動小数の誤差で同時刻の順序の規則が効かないことがある。実験の水準（0, 60, 300 秒、整数の到着時刻）では起きない。
  - 0.005 未満の金額は整数にすると 0 になり、エラーになる。生成データでは起きない。
  - `integrity-checker` は Day 6〜7 の文書の変更に未実施。Week 1 ゲートで行う。
  - 流動性の較正（methodology sec. 6）は 3 モデルがそろったのでできるようになったが、未実施。実験も未実施で、`results/` に CSV はない。
- 次の日（Day 8）: Week 1 ゲート（`/gate 1`）を確認する。HANDOFF の Day 8（残高更新、残高不足、部分決済、障害、Atomic のロールバックのテスト）のうち、まだ足りないものを足す。較正をいつ行うかを決める。

## Week 1 ゲート（Day 7 終了時、2026-11-03）
- 実施: `reviewer`（コード・テスト）と `integrity-checker`（文書の整合性。Day 4〜7 に先送りしていた分を含む）。作業ツリーは Day 7 の変更が未 commit の状態で検査した。pytest 517 passed / 1 skipped、`scripts/precommit_check.sh` 問題なし。

| 項目 | 判定 | 根拠 |
|---|---|---|
| 同じ取引データを 3 モデルに入れられる | PASS | `run_model` が 3 モデルとも動く。サンプル 100 件で実行し、全モデルで USD・JPY の合計が変わらない |
| 各モデルの残高更新と状態を確認できる | PASS | `Ledger` の残高・予約・ピーク、`SettlementResult`。A / B / C それぞれの手計算テストあり |
| settled / partial / failed を区別できる | PASS | `SettlementResult` の検査と `test_status_matches_legs_done_in_every_run`（3 モデル） |
| Atomic の失敗で片側だけ残高が変わらないことをテストできる | PASS | `test_model_c_failure_leaves_every_balance_reservation_and_peak_unchanged`（6 パターン）、`test_failed_model_c_transaction_leaves_every_balance_unchanged` |
| Streamlit・スライドに時間を使いすぎない | PASS | `dashboard/`・`presentation/` は空 |
| HANDOFF 13 Technical | PASS | 残高更新・部分決済・失敗・Atomic の不可分性のテストあり |
| methodology sec. 7 の必須テスト | PASS（1 件は延期を明示） | 7 件中 6 件実装。「割合の合計 = 1」は Day 9 まで skip |
| `results/` に実験の出力がない | PASS | `figures/.gitkeep` のみ |
| Integrity（仮想データ、仮定、限界、出典、非公式であること） | PASS | README、methodology、hypotheses、research_question に記載あり |

- 指摘: 高 0 件。中 1 件: methodology sec. 7 の一覧に、「割合の合計 = 1」が skip 中（Day 9 で実装）であることが書かれていない。
- 指摘（低、コード）:
  - skip 中のテストを Day 9 で必ず解除する。
  - Day 9 で、partial を成功に含めないテストを割合の関数に直接足す。
  - `usd_payer == jpy_payer` の行は実行の途中でエラーになる。入力の確認を `_read_transactions` に前倒しすると安全。生成データでは起きない。
- 指摘（低、文書）:
  - methodology sec. 2 に model 列の値（sequential / prefunded / atomic）を書く。
  - sec. 3 の `start_time` を「全モデルで到着時刻」とまとめる。
  - sec. 11 の Day 6 の記述に「Model B のテストで確認済み」を足す。
  - sec. 9 に小数の遅延の浮動小数の制限を 1 行足す。
  - 設計上の予測（B の Proxy ≥ A など）を結果の証拠として書かない（今は問題なし）。
- 翌日（Day 8）の最初にやること: 文書の中 1 件と低 4 件を直す（methodology のみ。コードは変えない）。直したあと `integrity-checker` で確認する。そのあと HANDOFF の Day 8 に進む。

## Day 8 — Week 1 ゲートの文書修正と決済テストの強化
- 完了（文書）: `research/methodology.md` の Week 1 ゲートの指摘（中 1 件・低 4 件）を直した。コードは変えていない。
  - sec. 7: 「割合の合計 = 1」は skip 中で、Day 9 に `src/metrics.py` と一緒に実装すると明記。
  - sec. 2: `model` 列の値（`sequential` / `prefunded` / `atomic`）を明記。
  - sec. 3: `start_time` は全モデルで到着時刻、とまとめた。
  - sec. 9: 小数の遅延では浮動小数の誤差で同時刻の規則が効かないことがある、と 1 行追加。
  - sec. 11: Day 6 の記述に「Day 7 の Model B の動作テストで確認（手作業で順序を逆にして失敗を確認）」を追記。
  - Status 行を Day 8 にした。`README.md` の状態表示も Day 8 にした。
- 検査（文書）: `integrity-checker` 1 回。高・中 0 件、低 2 件（README の Day 表示、「手作業で確認」の明記）を修正。修正後の再検査はしていない。
- 完了（テスト）: `tests/test_simulator.py` にテストを追加。`src/` は変えていない（バグは見つからなかった）。
  - `naive_model_b` / `naive_model_c`: Ledger を使わない素朴な B / C。ストレス条件 × 障害確率 3 水準 × 遅延 {0, 60, 300} 秒で、取引ごとの状態・理由・レッグの完了フラグ・`end_time`、銀行・通貨ごとの最終残高と peak drawdown がエンジンと一致することを確認（`test_models_b_and_c_match_their_naive_oracles_under_stress`）。peak はイベントごとに全口座で計算し直し、エンジンの更新の仕方をまねない。
  - 3 モデル共通: 銀行・通貨ごとに `balance >= 0`、`max(0, 初期 - 最終) <= peak <= 初期`、`reserved == 0`（`test_every_bank_balance_and_peak_drawdown_stay_in_range_under_stress`）。
  - モデルごとの結果の種類（`EXPECTED_OUTCOMES`）: A は 4 種、B は settled / failed-insufficient_funds / partial-technical_failure、C は settled / failed-insufficient_funds / failed-technical_failure。`timeout` は出ない。B の `failed` はすべて `insufficient_funds`。
  - B で失敗した取引を入力から外しても、ほかの結果・残高・peak が変わらない（C 版はすでにあった）。
  - `test_status_matches_legs_done_in_every_run` に「JPY のレッグが USD より先に完了しない」を追加。
  - pytest は 960 passed / 1 skipped（skip は Day 9 の「割合の合計 = 1」）。`scripts/precommit_check.sh` は問題なし。
- 検査（わざと壊す確認）: B で障害時に JPY の予約を解除しない、C で USD を検証前に反映する、B で USD を予約でなく通常の残高から払う、B で予約失敗時に USD を予約してから戻す（Day 7 より前の動き）、の 4 種をすべて新しいテストが検知した。コードは元に戻し、`git diff --stat src/` が空であることを確認した。最後の 1 種は、最初はオラクル比較で検知できなかった（最終残高しか比べていなかったため）。peak も比べるようにして、オラクル比較でも検知できるようになった。
- 検査（コード）: `reviewer` 3 回（抜けの洗い出し、追加テストのレビュー、再レビュー）。高 0 件。2 回目の中 3 件のうち 2 件（オラクルで peak とフラグ・`end_time` を比べる）と低 3 件を修正した。再レビューでは高・中 0 件。
- 判断（Claude）: 結果の種類のテストは、全シードと全ケースをまとめた集合で比べる。1 ケースで種類が欠けても検知しないが、ケースごとの結果はオラクル比較が照合する。
- 未完了 / 既知の制限:
  - B のオラクルは、1 つのイベントが終わったあとにだけ peak を更新する。今は同じイベント内で同じ口座に支払いと受け取りが両方入ることはないので、差は出ない。`usd_payer == jpy_payer` を許す変更が入ったら見直す。
  - 文書の最後の修正（README、methodology sec. 11 の言い回し）のあと、`integrity-checker` は再実行していない。
  - 流動性の較正（methodology sec. 6）は未実施。実験も未実施で、`results/` に CSV はない。
- 次の日（Day 9）: `src/metrics.py` に Success / Partial / Failure Rate、Principal Exposure、失敗理由別の集計を実装する。Week 1 ゲートで Day 9 に回した、コードの低い指摘 3 件も行う。
  - skip 中の「割合の合計 = 1」のテストを解除する。
  - 割合の関数が partial を成功に数えないことを、直接確かめるテストを足す。
  - `usd_payer == jpy_payer` などの入力の確認を `_read_transactions` に前倒しする。
  - 較正をいつ行うかを決める。
