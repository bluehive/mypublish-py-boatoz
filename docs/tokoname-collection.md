# 常滑公式HTMLの時系列収集

利用者の要件は、**出走表・直前情報・オッズを20秒ごとに観測し、投票締切の2分前で終了**することです。
1レースを指定して動かす収集CLIを追加します。PR作成時点では連続ライブ運転は開始していません。

## 調査した公開ページ（2026-11-04 JST）

- [公式トップページ](https://www.boatrace-tokoname.jp/)は、JavaScriptで`/modules/yosou/`のHTMLをiframeへ表示しています。
- [出走表の例](https://www.boatrace-tokoname.jp/modules/yosou/group-syussou.php?day=20261104&race=1&kind=0&if=1)
- [直前情報の例](https://www.boatrace-tokoname.jp/modules/yosou/group-cyokuzen.php?day=20261104&race=1&kind=0&if=1)
- [3連単オッズの例](https://www.boatrace-tokoname.jp/modules/yosou/group-odds-result.php?day=20261104&race=1&kind=Odds1&if=1)
- [公式の更新処理](https://www.boatrace-tokoname.jp/modules/yosou/js/odds_update.js)には、更新ボタンの無効状態を60秒後に解除する処理があります。

上記3ページの単発取得で、1Rの締切10:21、出走表6艇、直前情報6艇、3連単120通りを解析できました。
直前情報の未公開の展示タイムなどはnullになりました。実HTMLは作業領域だけに保存し、リポジトリのテストには自作HTMLを使います。

**20秒の観測周期は、20秒ごとのデータ更新を保証するものではありません。**
HTMLの同一性と値の変化を記録して判定します。サイトの強制更新用パラメータ`update=on`は付けません。
通常ページとして公開されているHTMLのみを読み、ログインや投票機能は利用しません。

[robots.txt](https://www.boatrace-tokoname.jp/robots.txt)は調査時HTTP 404（HTMLのエラーページ）でした。
これは20秒間隔での収集許可を意味しません。公式フッターには著作権表示があり、20秒取得を明示的に許可する記載は確認できていません。
初回運用前に対象サイトの最新の利用条件・公開方針を確認してください。取得データの再配布許諾は本コードのBSDライセンスに含みません。

## 実行と停止の仕様

- 対象：常滑（場コード08）の当日JST、指定した1〜12Rの1レース。
- 既定対象：3連単オッズ（Odds1）、直前情報の展示情報（kind=0）、出走表の選手成績（kind=0）。
  それぞれのHTML全体を保存します。他の券種のオッズ、直前情報の別タブは今回の構造化対象に含めません。
- 1周期3ページを順番に取得するため、通常は最大9リクエスト/分です。並列通信はありません。
- 開始は起動時刻、`--start-at`指定時はその時刻。周期の開始間隔は20秒です。3ページは同時刻のデータではありません。
- 初回の通信前から停止時刻を適用できるよう、確認済みの**投票締切**を`--deadline`で必須指定します。
  発走時刻ではありません。必ず公式表示で確認してください。
- 停止時刻 = 投票締切 − 120秒。例：締切12:00なら11:58以降は新規通信しません。
  実際には通信を残さないため、停止時刻まで残り1秒以下では通信を始めません。
- 各応答から締切と対象日・レースを再確認。締切が早まれば停止も早め、延期されても自動延長しません。
  延長する場合は変更後の時刻を確認して再起動してください。
- 通信の総時間上限は8秒、停止境界が近いときは残り時間から1秒を引いた値に短縮します。
  HTTPを子プロセスで行い、総時間上限を超えたら子を終了します。ソケット単位タイムアウトだけに頼りません。
- 待機はmonotonic時計で測定し、OS時計が後戻りしても最初の停止期限を延ばしません。実機の時刻同期は必要です。
- 遅延した周期は飛ばし、取り逃した周期の要求をまとめて送りません。
- HTTP 429/5xx、通信障害は40/80/160/300/300秒の待機。Retry-Afterが長ければそれを優先し、5回連続障害で終了。
  待機中も停止期限を適用します。401/403/404・リダイレクト・HTML構造変更・対象不一致では直ちに停止します。
- 未知のHTMLや数値表記を0に置換しません。欠損・発売なしはnull。停止境界を過ぎた応答は分析用観測に加えません。
- 同一出力先・同一レースはOSファイルロックで多重起動を防ぎます。同じレースを異なる出力先・別マシンで同時実行しないでください。
- Ctrl+Cで終了できます。停止理由はログの`stop`に記録します。常駐サービス・自動起動設定は追加しません。

## コマンド

まずネットワーク通信をしないplanで、日付・レース・停止時刻を確認します。
次は説明用の仮の締切です。運用時には対象日の公式締切に置き換えてください。

```bash
python -m pip install -e ".[dev]"
boatoz tokoname plan --date 2026-11-04 --race 1 \
  --deadline 2026-11-04T12:00:00+09:00 \
  --start-at 2026-11-04T11:30:00+09:00
```

PR承認後、対象レースの開始時刻から実行します。初回の実地試験は`--max-cycles 2`で最大2周期に制限できます。

```bash
boatoz tokoname collect --date 2026-11-04 --race 1 \
  --deadline 2026-11-04T12:00:00+09:00 \
  --start-at 2026-11-04T11:30:00+09:00 --max-cycles 2
```

実運用は`--max-cycles`を外せば、指定開始時刻から締切2分前まで観測します。
`--pages odds before entries`が既定です。一種類だけの調査は`--pages odds`などと指定できます。
当日以外の収集は拒否します。過去HTMLの解析にはreplayを使います。

```bash
boatoz tokoname replay path/to/saved.html --date 2026-11-04 --race 1 --page odds
boatoz tokoname summary output/tokoname/2026-11-04/08-R01/observations.jsonl \
  --output output/tokoname-summary.csv
boatoz tokoname export output/tokoname/2026-11-04/08-R01/observations.jsonl \
  --output-dir output/tokoname-csv
```

## 保存形式とpandas集計

出力先は既定で`output/tokoname/YYYY-MM-DD/08-RNN/`です。

- `raw/<SHA256>.html`：受信したHTML全体。同じ内容は1ファイルにまとめ、異なる観測は失いません。
- `observations.jsonl`：観測、通信エラー、停止を追記。各行はfsyncし、再起動しても既存ログに追記します。
- 観測行：requested_at/received_at、date、stadium=8、race_number、deadline、page、url、sha256、raw_file、rows。
- 出走表のrows：艇番、選手登録番号・氏名、全国勝率（得点平均）、全国2連対率、モーター/ボート番号と2連対率。
- 直前情報のrows：艇番、選手登録番号・氏名、展示タイム、体重、チルト、部品交換。
- オッズのrows：3連単の組合せ、オッズ、元の表示文字列。常に120通りの対応を検証します。

公式勝率は`national_score`として保持し、架空教材モデルの0〜1の`win_rate`へ変換しません。
2連対率は百分率から0〜1へ変換します。未公開の値はnullで保存します。

`export`は3種類の観測を縦長CSV（odds.csv/before.csv/entries.csv）に変換し、
`summary`はオッズの組合せ別に観測件数・有効値件数・異なるHTML数・初回/最終時刻・初回/最終値・最小/最大値を集計します。
最新観測が欠損なら最終値も欠損にし、過去の値で埋めません。同じHTMLの再観測は「値が更新された」と扱いません。
異なるHTML数はページ全体の変更数なので、各組合せそのものの値の変更回数とは異なります。

```python
import pandas as pd
entries = pd.read_csv("output/tokoname-csv/entries.csv")
before = pd.read_csv("output/tokoname-csv/before.csv")
# 観測時刻を保持したまま、それぞれの艇の最新行を確認する例
latest = (entries.sort_values("received_at")
          .drop_duplicates(["date", "race_number", "boat_num"], keep="last"))
print(latest[["boat_num", "racer_name", "national_score", "motor_top_two_rate"]])
```

一部ページだけ成功した周期は、その成功したページの観測だけを残します。3種類を同時スナップショットとみなさず、
学習・検証の結合には各観測時刻と対象レースを使い、未来の結果や締切後データを混ぜないでください。

## 検証と承認範囲

CIは自作HTMLと仮想時計を使用し、公式サイトへ通信しません。
20秒周期、3ページ順次取得、停止境界の前後、締切変更、時計後戻り、遅延時の周期スキップ、429/403/構造変更、
タイムアウト時のHTTP子プロセス終了、多重起動防止、欠損を含むpandas集計を検証します。
調査では公開ページの単発取得と保存HTMLの解析まで実施しています。20秒間隔の連続実地運転の結果はまだありません。

ユーザー承認の対象は、この仕様・コードを含むPRの採用です。実地試験は、当日のレース番号・公式締切・開始時刻を
planで確認したうえで最大2周期から始め、そのログを確認してから本運用へ進めます。
