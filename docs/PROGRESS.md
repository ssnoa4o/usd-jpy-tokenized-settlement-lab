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
