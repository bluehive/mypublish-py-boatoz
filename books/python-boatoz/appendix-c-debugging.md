---
title: "付録C：エラーを調べる"
---

ModuleNotFoundErrorが出たら仮想環境が有効か確認し、`python -m pip install -e ".[dev]"` を再実行します。`python -m pip --version` でどのPythonのpipか確認できます。

FileNotFoundErrorなら、リポジトリ直下から実行しているか確認します。KeyErrorならCSVの列名を表示してください。rankと着順などの表記揺れは自動変換しません。

テストは `python -m pytest -q`、静的検査は `ruff check .` です。通信エラーは日付、URL、HTTP状態を確認し、未公開データを架空値で代用しないでください。
