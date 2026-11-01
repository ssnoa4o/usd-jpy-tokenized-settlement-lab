# Progress Log

毎日の終わりに Claude が追記する（やったこと / 未完了 / 次にやること / 気づき）。

## Day 0 — setup
- Claude Code 用スターターキット（CLAUDE.md, .claude/agents, .claude/skills）を配置。

## Day 1 — project setup
- 完了: `.venv`（Python 3.14.6）作成、依存導入（numpy/pandas/plotly/streamlit/pytest、requirements.txt はバージョン固定）。
- 完了: フォルダ構成、`.gitignore`、MIT `LICENSE`、英語 README 初版。
- 完了: `src/transactions.py` と `data/sample_transactions.csv`（100 件、seed 42、シードは `*_meta.json` に保存）。`tests/test_transactions.py`（16 件パス）。
- 判断: リポジトリは public / MIT。`CLAUDE.md`・`.claude/`・`*.docx`・`docs/HANDOFF.md` は公開しない（HANDOFF に別プロジェクトの詳細が含まれるため）。
- 未完了: git 初期化と GitHub への public 公開（公開前に追跡ファイル一覧の確認が必要）。
- 次の日（Day 2）: BIS Project Agorá・日銀・CLS・OSFI の一次資料を読み、literature_review.md の初版と出典一覧を作る。
