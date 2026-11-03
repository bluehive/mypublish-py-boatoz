---
title: "付録D：実行環境と自動化"
---

miseを使う場合は `mise trust`、`mise install` 後に仮想環境と依存をセットアップします。Pythonを直接利用しても構いません。

`mise run test` はテスト、`mise run book:build` は結合原稿とHTMLの生成です。生成物はoutputに置きます。GitHub ActionsはPython 3.11〜3.13でテスト・静的検査・パッケージ作成・書籍ビルドを実行します。

EPUBが必要ならPandocを導入し、`pandoc output/book.md -o output/python-boatoz.epub --metadata title="Pythonで学ぶボートレース統計入門" --metadata lang=ja` を実行します。公開前に実際のリーダーで確認してください。
