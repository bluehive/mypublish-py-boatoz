"""章順に原稿を結合し、HTMLを生成する。外部依存なし。"""

from html import escape
from pathlib import Path

root = Path(__file__).resolve().parents[1]
book = root / "books/python-boatoz"
slugs = [
    line.strip()[2:]
    for line in (book / "config.yaml").read_text().splitlines()
    if line.strip().startswith("- ")
]
parts = ["# Pythonで学ぶボートレース統計入門\n"]
for slug in slugs:
    text = (book / f"{slug}.md").read_text(encoding="utf-8")
    _, meta, body = text.split("---", 2)
    title = meta.strip().removeprefix("title: ").strip('"')
    parts.append(f"# {title}\n{body.strip()}\n")
out = root / "output"
out.mkdir(exist_ok=True)
text = "\n".join(parts)
(out / "book.md").write_text(text, encoding="utf-8")
# HTML版は原稿の書式をそのまま読みやすく表示する簡易プレビュー。
(out / "book.html").write_text(
    '<!doctype html><html lang="ja"><meta charset="utf-8">'
    "<title>Pythonで学ぶボートレース統計入門</title>"
    "<style>body{max-width:54rem;margin:3rem auto;padding:1rem;"
    "font:16px/1.9 sans-serif}pre{white-space:pre-wrap}</style><body><pre>"
    + escape(text)
    + "</pre></body></html>",
    encoding="utf-8",
)
print(f"{len(slugs)} chapters -> {out}")
