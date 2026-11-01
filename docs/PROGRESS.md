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
