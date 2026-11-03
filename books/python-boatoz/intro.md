---
title: "序章：Pythonで統計を学ぶ"
---

ボートレースを題材に、データを集め、表を整え、集計し、仮説を検証する一連の流れを学びます。対象はプログラミングと統計の初心者です。Pythonは計算の手順を記述する言語、pandasは行と列を持つ表を操作するライブラリです。

本書の目的は統計の理解です。教材は架空データなので、その的中率から現実の性能を推測できません。気象条件や払戻額は分析対象に含めず、艇番・着順・事前能力指標に範囲を絞ります。

Python 3.11以上を用意し、リポジトリ直下で環境を作ります。
```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShellでは .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
boatoz show data/sample_races.csv
```
実行結果には艇番ごとの出走数と1着率が表示されます。エラーが出たら付録Cで実行環境を確認してください。
