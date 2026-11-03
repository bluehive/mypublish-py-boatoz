"""事前特徴だけを使う固定スコア。学習済みAIではない。"""

import pandas as pd

COURSE = {1: 40, 2: 20, 3: 15, 4: 12, 5: 8, 6: 5}


def score(frame):
    result = frame.copy()
    for col in ["boat_num", "win_rate", "motor_rate"]:
        values = pd.to_numeric(result[col], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{col}に欠損または非数値があります")
        result[col] = values
    if not result["boat_num"].isin(COURSE).all():
        raise ValueError("艇番は1〜6です")
    for col in ["win_rate", "motor_rate"]:
        if not result[col].between(0, 1).all():
            raise ValueError(f"{col}は0〜1の割合で指定してください")
    if result.duplicated(["race_id", "boat_num"]).any():
        raise ValueError("艇が重複しています")
    result["score"] = (
        result["boat_num"].map(COURSE) + 50 * result["win_rate"] + 20 * result["motor_rate"]
    )
    return result


def evaluate(frame):
    scored = score(frame)
    # 欠損着順や途中結果のレース全体を除外する。
    complete = scored.groupby("race_id")["rank"].apply(
        lambda ranks: len(ranks) == 6 and set(ranks) == set(range(1, 7))
    )
    scored = scored[scored["race_id"].isin(complete[complete].index)]
    top = scored.sort_values(["score", "boat_num"], ascending=[False, True])
    top = top.drop_duplicates("race_id")
    count = len(top)
    hits = int(top["rank"].eq(1).sum())
    baseline = scored[scored["boat_num"].eq(1)]
    return {
        "races": count,
        "hits": hits,
        "accuracy": hits / count if count else None,
        "course1_accuracy": float(baseline["rank"].eq(1).mean()) if count else None,
        "excluded_races": int((~complete).sum()),
    }
