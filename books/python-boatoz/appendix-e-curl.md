---
title: "付録E：curlで取得する"
---

JSONの中身を直接確認したい場合は次のように取得します。
```bash
curl --fail --location --output output/results.json https://boatraceopenapi.github.io/results/v3/2026/20260101.json
boatoz parse output/results.json --output output/results.csv
```
--failはHTTPエラーを成功として扱わないための指定です。アクセス先の利用条件を確認し、過剰な並列取得を避けてください。CLIのdownloadは既存ファイルを使い回し、未取得ファイルの通信後に待ち時間を設けています。
