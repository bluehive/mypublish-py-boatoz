# Pythonで学ぶボートレース統計入門 — mypublish-py-boatoz

[![CI](https://github.com/bluehive/mypublish-py-boatoz/actions/workflows/ci.yml/badge.svg)](https://github.com/bluehive/mypublish-py-boatoz/actions/workflows/ci.yml)

Python・pandas・matplotlibで、データ収集から前処理、統計集計、可視化、固定スコアの検証までを学ぶ初心者向けの実習書です。
[参考リポジトリ](https://github.com/bluehive/mypublish-racket-statistics)の書籍・章別コード・データ・ビルドの構成を参考に、Python用に新規実装・執筆しています。

## はじめる

Python 3.11以上を使い、リポジトリ直下で実行します。

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
boatoz show data/sample_races.csv --venue tsu --recent 12
boatoz monthly data/sample_races.csv
boatoz plot data/sample_races.csv
boatoz predict data/sample_races.csv
python scripts/build_book.py
```

サンプルCSVは**架空の216艇・36レース**です。出力される精度は実際の予測性能を示しません。
win_rateは教育用の0〜1指標で、公式の勝率（得点平均）とは別です。

## 構成と目次

- `books/python-boatoz/`: 序章、Python基礎、データ収集、pandas、統計、可視化、予測検証、付録A〜E（全12章）
- `src/boatoz/`: 再利用可能なPythonパッケージとCLI
- `code/`: 章別の実行例
- `data/`: 架空教材CSV（[説明](data/README.md)）、取得JSONの保存先
- `scripts/build_book.py`: Markdown結合・HTMLプレビュー生成
- `tests/`: 通信モック、正規化、集計、モデル、描画、CLIの検証
- `output/`: 生成原稿・図（Git管理外）
- `mise.toml`, `.github/workflows/ci.yml`: ローカルタスク・CI

## 実データを取得する

```bash
boatoz download --start 2026-01-01 --end 2026-01-03
boatoz parse data/raw/*.json --output data/parsed_races.csv
boatoz show data/parsed_races.csv --venue tsu
boatoz monthly data/parsed_races.csv
```

提供元は非公式の[Boatrace Open API results/v3](https://github.com/boatraceopenapi/results)です。
404は未公開として報告し、既存ファイルはキャッシュします。`--interval`（既定1秒）で通信間隔、`--dest`で保存先を指定できます。
`BOATRACE_DATA_ROOT`設定時の既定保存先はその配下のrawです。
会場はtsu（9）、gamagori（7）、tokoname（8）、biwako（11）を指定できます。全国データは全24場を保持します。
参照元の会場別日次JSONもparseに渡せます。

結果JSONだけではwin_rateやmotor_rateを得られません。実データでplot/predictを使うには、レース前の出走表から該当列を別途結合してください。日付より後の成績を入れるデータ漏洩に注意します。集計は有効着順1〜6のみを分母にし、予測評価は6艇の着順が揃うレースのみを対象にします。

## 開発・書籍ビルド

```bash
python -m pytest -q
ruff check .
python -m build
python scripts/build_book.py
```

`output/book.md` と `output/book.html` を生成します。HTMLはMarkdown原稿の簡易表示です。
EPUBはPandocを別途導入して `pandoc output/book.md -o output/python-boatoz.epub --metadata lang=ja` で生成できます。
Zenn向けconfig.yamlは誤公開防止のためpublished: falseです。GitHubリポジトリ自体は公開です。

## ライセンス

新規のコード・原稿・架空教材データは[BSD 2-Clause](LICENSE)です。
参考元から原稿・コード・収集済み実データを転載せず、章立てと学習の流れを参考にしています。
第三者APIのデータには提供元の利用条件が適用されます。
