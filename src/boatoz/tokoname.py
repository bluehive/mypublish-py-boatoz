"""常滑公式の公開HTMLを読み、時刻付きの観測記録へ変換する。JSは実行しない。"""

import json
import math
import re
from datetime import date, datetime, time, timezone
from itertools import permutations
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup

JST = ZoneInfo("Asia/Tokyo")
PAGES = {"entries": "group-syussou", "before": "group-cyokuzen", "odds": "group-odds-result"}


def source_url(day: date, race: int, page: str) -> str:
    if not 1 <= race <= 12 or page not in PAGES:
        raise ValueError("レースは1〜12、種類はentries/before/oddsです")
    kind = "&kind=Odds1" if page == "odds" else "&kind=0"
    return (
        f"https://www.boatrace-tokoname.jp/modules/yosou/{PAGES[page]}.php"
        f"?day={day:%Y%m%d}&race={race}&if=1{kind}"
    )


def number(text):
    text = text.strip().replace(",", "")
    if text in {"", "-", "--", "---", "―", "－", "欠場", "欠", "中止", "発売なし"}:
        return None
    if re.fullmatch(r"[-.]+", text):
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"未知の数値表記: {text}") from exc
    if not math.isfinite(value):
        raise ValueError("有限の数値が必要です")
    return value


def _text(node):
    if node is None:
        raise ValueError("想定したHTML要素がありません")
    return node.get_text(" ", strip=True)


def _parent_html(soup, selector):
    # 親フレームへ渡すJSON互換の文字列リテラルだけを読む。evalは使わない。
    pattern = re.compile(
        r'\$\("' + re.escape(selector) + r'",\s*parent\.document\)\.html\(("(?:\\.|[^"\\])*")\)'
    )
    matches = [
        m.group(1)
        for script in soup.find_all("script")
        for m in pattern.finditer(script.get_text())
    ]
    if len(matches) != 1:
        raise ValueError(f"{selector}を一意に識別できません")
    return BeautifulSoup(json.loads(matches[0]), "html.parser")


def parse_page(html: bytes, day: date, race: int, page: str) -> dict:
    source_url(day, race, page)
    soup = BeautifulSoup(html.decode("utf-8", errors="strict"), "html.parser")
    # ページが別の日・レースへフォールバックしていないことを確認。
    selected = soup.select_one(".sub-tabs li.selected a[data-day][data-race]")
    if selected is None or selected.get("data-day") != day.strftime("%Y%m%d"):
        raise ValueError("開催日を確認できません（休催・ページ変更の可能性）")
    if selected.get("data-race") != str(race):
        raise ValueError("レース番号が一致しません")
    if page == "odds" and selected.get("data-kind") != "Odds1":
        raise ValueError("3連単のページではありません")
    race_label = _parent_html(soup, ".race_number").get_text(strip=True)
    if race_label != f"{race}R":
        raise ValueError("親フレームのレース番号が一致しません")
    deadline_text = _text(_parent_html(soup, ".race_deadline").select_one(".raceinfo_dento_time"))
    if not re.fullmatch(r"\d{2}:\d{2}", deadline_text):
        raise ValueError("締切時刻を確認できません")
    deadline = datetime.combine(day, time.fromisoformat(deadline_text), JST)
    if page == "odds":
        rows = _odds(soup)
    else:
        rows = _boats(soup, page)
    return {
        "date": day.isoformat(),
        "stadium": 8,
        "race_number": race,
        "page": page,
        "deadline": deadline.isoformat(),
        "rows": rows,
    }


def _odds(soup):
    rows = []
    tables = soup.select("table.odds3Tan")
    if len(tables) != 6:
        raise ValueError("3連単6テーブルを確認できません")
    for table in tables:
        first = int(_text(table.select_one(".chaku_left1")))
        second = None
        for tr in table.select("tr"):
            if tr.select_one(".chaku_2"):
                second = int(_text(tr.select_one(".chaku_2")))
            cell = tr.select_one("td.odds")
            if cell is None:
                continue
            third = int(_text(tr.select_one(".chaku_3")))
            if second is None:
                raise ValueError("2着の艇番を確認できません")
            raw = _text(cell)
            value = number(raw)
            if value is not None and value <= 0:
                raise ValueError("オッズが正数ではありません")
            rows.append({"combination": f"{first}-{second}-{third}", "odds": value, "display": raw})
    expected = {"-".join(map(str, p)) for p in permutations(range(1, 7), 3)}
    if len(rows) != 120 or {r["combination"] for r in rows} != expected:
        raise ValueError("3連単120通りの対応が崩れています")
    return rows


def _boats(soup, page):
    rows = []
    for cell in soup.select("td.waku"):
        tr = cell.find_parent("tr")
        row = {"boat_num": int(_text(cell)), "racer_name": _text(tr.select_one(".com-rname"))}
        racer = _text(tr.select_one(".com-toban"))
        match = re.search(r"/(\d{4})$", racer.replace(" ", ""))
        if match is None:
            raise ValueError("選手登録番号を確認できません")
        row["racer_id"] = int(match.group(1))
        if page == "entries":
            row["national_score"] = number(_text(tr.select_one(".col6 .ue")))
            row["national_top_two_rate"] = _percentage(tr.select_one(".col6 .shita"))
            row["motor_number"] = number(_text(tr.select_one(".col8 .ue")))
            row["motor_top_two_rate"] = _percentage(tr.select_one(".col8 .shita"))
            row["boat_number"] = number(_text(tr.select_one(".col9 .ue")))
            row["boat_top_two_rate"] = _percentage(tr.select_one(".col9 .shita"))
        else:
            row["exhibition_time"] = number(_text(tr.select_one("td.col3")))
            row["weight_kg"] = number(_text(tr.select_one("td.col4")))
            row["tilt"] = number(_text(tr.select_one("td.col5")))
            row["parts_replaced"] = _text(tr.select_one("td.col10"))
        rows.append(row)
    if len(rows) != 6 or {r["boat_num"] for r in rows} != set(range(1, 7)):
        raise ValueError("6艇の出走情報を確認できません")
    return rows


def _percentage(node):
    value = number(_text(node))
    if value is not None and not 0 <= value <= 100:
        raise ValueError("百分率が範囲外です")
    return value / 100 if value is not None else None


def summarize_observations(path):
    """追記ログの成功した観測から、組合せ別オッズ推移を集計。"""
    records = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            if entry.get("event") != "observation" or entry.get("page") != "odds":
                continue
            for row in entry["rows"]:
                records.append(
                    {
                        "date": entry["date"],
                        "race_number": entry["race_number"],
                        "combination": row["combination"],
                        "odds": row["odds"],
                        "at": entry["received_at"],
                        "sha256": entry["sha256"],
                    }
                )
    columns = [
        "date",
        "race_number",
        "combination",
        "observations",
        "valid_values",
        "distinct_html",
        "first_at",
        "last_at",
        "first_odds",
        "last_odds",
        "min_odds",
        "max_odds",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(records).sort_values("at")
    # first/lastは欠損も保持する。最新が発売なしなら過去値へ後退しない。
    return (
        frame.groupby(["date", "race_number", "combination"])
        .agg(
            observations=("at", "size"),
            valid_values=("odds", "count"),
            distinct_html=("sha256", "nunique"),
            first_at=("at", "min"),
            last_at=("at", "max"),
            first_odds=("odds", lambda s: s.iloc[0]),
            last_odds=("odds", lambda s: s.iloc[-1]),
            min_odds=("odds", "min"),
            max_odds=("odds", "max"),
        )
        .reset_index()[columns]
    )


def utcnow():
    return datetime.now(timezone.utc)


def export_observations(log, output_dir):
    """各種類の観測を取得時刻付きの縦長CSVへ展開する。"""
    from pathlib import Path

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    counts = {}
    entries = [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines()]
    for page in PAGES:
        observations = [e for e in entries if e.get("event") == "observation" and e["page"] == page]
        rows = []
        for entry in observations:
            meta = {
                key: entry[key]
                for key in [
                    "date",
                    "stadium",
                    "race_number",
                    "deadline",
                    "requested_at",
                    "received_at",
                    "sha256",
                    "url",
                ]
            }
            rows.extend({**meta, **row} for row in entry["rows"])
        pd.DataFrame(rows).to_csv(directory / f"{page}.csv", index=False)
        counts[page] = len(rows)
    return counts
