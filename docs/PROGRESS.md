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
