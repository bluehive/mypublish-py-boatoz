"""レース単位の抽出と、欠損値を考慮した集計。"""

import pandas as pd


def recent_races(frame, n):
    if n < 1:
        raise ValueError("レース数は1以上にしてください")
    keys = frame[["date", "stadium", "race_number", "race_id"]].drop_duplicates()
    ids = keys.sort_values(["date", "stadium", "race_number"]).tail(n)["race_id"]
    return frame[frame["race_id"].isin(ids)].copy()


def summarize(frame, by="boat_num"):
    valid = frame[frame["rank"].isin(range(1, 7))].copy()
    valid["win"] = valid["rank"].eq(1)
    valid["top_two"] = valid["rank"].le(2)
    return (
        valid.groupby(by)
        .agg(
            starts=("rank", "size"),
            wins=("win", "sum"),
            win_rate=("win", "mean"),
            top_two_rate=("top_two", "mean"),
            mean_rank=("rank", "mean"),
            std_rank=("rank", "std"),
        )
        .reset_index()
    )


def monthly(frame):
    result = frame.copy()
    result["month"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m")
    return summarize(result, "month")
