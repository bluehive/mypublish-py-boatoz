---
title: "第3章：pandasによるデータ操作"
---

DataFrameは表全体、Seriesは列を表します。Indexは行ラベルです。CSVの読み込み後、型と欠損件数を確認します。
```python
import pandas as pd
from boatoz.analysis import recent_races

df = pd.read_csv("data/sample_races.csv")
print(df.head())
print(df.dtypes)
print(df.isna().sum())
recent = recent_races(df, 10)
print(recent["race_id"].nunique())
```
直近10行をtail(10)で選ぶと、1レースの途中で切れることがあります。recent_racesはレースキーを一意にした後で10件選び、そのレースの全艇を戻します。同じ日付では会場番号、レース番号の順を用います。全国の実際の発走時刻順ではありません。

条件抽出は `df[df["boat_num"].eq(1)]`、列選択は `df[["race_id", "rank"]]` です。日付を比較するときはISO形式に統一し、型の不一致に注意します。

練習：直近5レースを取り、行数とレース数を表示してください。教材では30行・5レースです。欠損を消すときはdropnaの対象列を限定し、不要な列の空欄で出走を消さないようにします。
