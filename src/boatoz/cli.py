"""boatozコマンド。ファイルパスは実行ディレクトリ基準。"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from .analysis import monthly, recent_races, summarize
from .data import VENUES, download, parse_files
from .model import evaluate
from .plot import scatter


def main():
    parser = argparse.ArgumentParser(description="ボートレース統計入門 Python版")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("download")
    fetch.add_argument("--start", type=date.fromisoformat, required=True)
    fetch.add_argument("--end", type=date.fromisoformat)
    fetch.add_argument("--dest", default=str(Path(os.getenv("BOATRACE_DATA_ROOT", "data")) / "raw"))
    fetch.add_argument("--interval", type=float, default=1.0)
    parse = sub.add_parser("parse")
    parse.add_argument("files", nargs="+")
    parse.add_argument("--output", default="data/parsed_races.csv")
    for name in ["show", "monthly", "predict", "plot"]:
        command = sub.add_parser(name)
        command.add_argument("csv", type=Path)
        if name == "show":
            command.add_argument("--venue", choices=VENUES)
            command.add_argument("--recent", type=int, default=12)
        if name == "plot":
            command.add_argument("--output", default="output/motor-scatter.png")
    args = parser.parse_args()
    try:
        if args.command == "download":
            print(
                json.dumps(
                    download(args.start, args.end or args.start, args.dest, args.interval),
                    ensure_ascii=False,
                )
            )
        elif args.command == "parse":
            frame = parse_files(args.files)
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(args.output, index=False)
            print(f"{len(frame)} rows -> {args.output}")
        else:
            frame = pd.read_csv(args.csv)
            if args.command == "show":
                if args.venue:
                    frame = frame[frame["stadium"].eq(VENUES[args.venue])]
                print(summarize(recent_races(frame, args.recent)).to_string(index=False))
            elif args.command == "monthly":
                print(monthly(frame).to_string(index=False))
            elif args.command == "predict":
                print(json.dumps(evaluate(frame), ensure_ascii=False, indent=2))
            elif args.command == "plot":
                scatter(frame, args.output)
                print(args.output)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
