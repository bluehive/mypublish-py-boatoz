---
title: "第4章：集計と統計量"
---

平均は中心、標準偏差はばらつきを表します。pandasのstdは既定で標本標準偏差（ddof=1）です。観測1件では標準偏差を推定できずNaNになります。
```python
import pandas as pd
from boatoz.analysis import summarize, monthly

df = pd.read_csv("data/sample_races.csv")
print(summarize(df))
print(summarize(df, "racer_id"))
print(monthly(df))
```
summarizeは有効着順1〜6だけを分母にします。失格を含む公式出走数の定義とは一致しない場合があるため、startsはこの教材における有効着順件数です。1着率とともに必ず件数を示してください。

1勝/2走の50%と50勝/100走の50%は、割合が同じでも推定の不確かさが異なります。会場や期間の構成が違う集団を単純比較すると、選手の能力以外の要因が混ざります。

練習：艇番ごとのstartsを合計してください。欠損のない教材では216になります。月次集計のCLIは `boatoz monthly data/sample_races.csv` です。
