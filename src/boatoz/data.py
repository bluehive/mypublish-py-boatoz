"""日次JSONの取得と、艇単位の表への正規化。"""

import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

COLUMNS = [
    "date",
    "race_id",
    "stadium",
    "race_number",
    "boat_num",
    "racer_id",
    "racer_name",
    "rank",
    "start_timing",
]
VENUES = {"gamagori": 7, "tokoname": 8, "tsu": 9, "biwako": 11}


def normalize(payload):
    """全国results/v3または参照元の会場別JSONを受け取る。異常着順は欠損。"""
    if not isinstance(payload, dict):
        raise ValueError("JSONオブジェクトが必要です")
    races = payload.get("results", payload.get("races"))
    if not isinstance(races, list):
        raise ValueError("JSONにresultsまたはraces配列が必要です")
    rows = []
    for race in races:
        day = date.fromisoformat(race.get("date", payload.get("date", ""))).isoformat()
        stadium = int(race["stadium_number"])
        number = int(race["number"])
        for boat in race["boats"]:
            rows.append(
                dict(
                    zip(
                        COLUMNS,
                        [
                            day,
                            f"{day}-{stadium:02}-{number:02}",
                            stadium,
                            number,
                            boat["racer_boat_number"],
                            boat.get("racer_number"),
                            boat.get("racer_name", ""),
                            boat.get("racer_place_number"),
                            boat.get("racer_start_timing"),
                        ],
                    )
                )
            )
    frame = pd.DataFrame(rows, columns=COLUMNS)
    for col in ["stadium", "race_number", "boat_num", "racer_id", "rank", "start_timing"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["rank"] = frame["rank"].where(frame["rank"].isin(range(1, 7)))
    if frame.duplicated(["race_id", "boat_num"]).any():
        raise ValueError("同一レースの艇が重複しています")
    return frame


def parse_files(paths):
    frames = [normalize(json.loads(Path(p).read_text(encoding="utf-8"))) for p in paths]
    if not frames:
        raise ValueError("JSONファイルがありません")
    frame = pd.concat(frames, ignore_index=True)
    if frame.duplicated(["race_id", "boat_num"]).any():
        raise ValueError("ファイル間でレースの艇が重複しています")
    return frame.sort_values(["date", "stadium", "race_number", "boat_num"])


def download(start, end, destination, interval=1.0):
    """404は未公開として返す。それ以外の通信障害は呼び出し元へ伝える。"""
    if start > end or interval < 0:
        raise ValueError("期間または取得間隔が不正です")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    status = []
    day = start
    while day <= end:
        target = destination / f"{day.isoformat()}.json"
        if target.exists():
            status.append((day.isoformat(), "cached"))
        else:
            url = f"https://boatraceopenapi.github.io/results/v3/{day:%Y}/{day:%Y%m%d}.json"
            try:
                request = Request(url, headers={"User-Agent": "mypublish-py-boatoz/0.1"})
                with urlopen(request, timeout=30) as response:
                    raw = response.read()
                normalize(json.loads(raw))
                temporary = target.with_suffix(".tmp")
                temporary.write_bytes(raw)
                temporary.replace(target)
                status.append((day.isoformat(), "saved"))
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                status.append((day.isoformat(), "unavailable"))
            finally:
                time.sleep(interval)
        day += timedelta(days=1)
    return status
