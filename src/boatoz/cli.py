"""boatozコマンド。ファイルパスは実行ディレクトリ基準。"""

import argparse
import json
import os
from datetime import date, datetime
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
    tok = sub.add_parser("tokoname", help="常滑の20秒間隔収集と観測集計")
    actions = tok.add_subparsers(dest="action", required=True)
    for name in ["plan", "collect"]:
        command = actions.add_parser(name)
        command.add_argument("--date", type=date.fromisoformat, required=True)
        command.add_argument("--race", type=int, required=True)
        command.add_argument("--deadline", type=datetime.fromisoformat, required=True)
        command.add_argument("--start-at", type=datetime.fromisoformat)
        command.add_argument(
            "--pages",
            nargs="+",
            choices=["odds", "before", "entries"],
            default=["odds", "before", "entries"],
        )
        command.add_argument("--output", type=Path, default=Path("output/tokoname"))
        command.add_argument("--max-cycles", type=int)
    summary = actions.add_parser("summary")
    summary.add_argument("log", type=Path)
    summary.add_argument("--output", type=Path, default=Path("output/tokoname-summary.csv"))
    export = actions.add_parser("export", help="3種類の観測をCSVへ変換")
    export.add_argument("log", type=Path)
    export.add_argument("--output-dir", type=Path, default=Path("output/tokoname-csv"))
    replay = actions.add_parser("replay", help="保存HTMLのオフライン解析")
    replay.add_argument("html", type=Path)
    replay.add_argument("--date", type=date.fromisoformat, required=True)
    replay.add_argument("--race", type=int, required=True)
    replay.add_argument("--page", choices=["odds", "before", "entries"], required=True)
    args = parser.parse_args()
    try:
        if args.command == "tokoname":
            from .polling import Config, collect
            from .tokoname import export_observations, parse_page, summarize_observations

            if args.action == "export":
                print(
                    json.dumps(export_observations(args.log, args.output_dir), ensure_ascii=False)
                )
            elif args.action == "summary":
                result = summarize_observations(args.log)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                result.to_csv(args.output, index=False)
                print(f"{len(result)} combinations -> {args.output}")
            elif args.action == "replay":
                print(
                    json.dumps(
                        parse_page(args.html.read_bytes(), args.date, args.race, args.page),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                config = Config(
                    args.date,
                    args.race,
                    args.deadline,
                    args.output,
                    tuple(args.pages),
                    args.start_at,
                    args.max_cycles,
                )
                result = config.plan() if args.action == "plan" else collect(config)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "download":
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
