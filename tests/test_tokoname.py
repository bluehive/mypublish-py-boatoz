import json
import subprocess
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from tokoname_fixtures import combinations, html

from boatoz.polling import Config, Response, collect, exclusive_run, fetch
from boatoz.tokoname import JST, parse_page, source_url, summarize_observations

DAY = date(2026, 11, 4)
DEADLINE = datetime(2026, 11, 4, 12, tzinfo=JST)


class Clock:
    def __init__(self, seconds=65):
        self.wall = DEADLINE - timedelta(minutes=2, seconds=seconds)
        self.mono = 0.0

    def now(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.mono += seconds


def config(tmp_path, **kwargs):
    return Config(DAY, 1, DEADLINE, tmp_path, **kwargs)


def run(cfg, clock, get):
    return collect(cfg, get=get, now=clock.now, monotonic=clock.monotonic, sleep=clock.sleep)


def records(cfg):
    return [
        json.loads(line) for line in (cfg.directory / "observations.jsonl").read_text().splitlines()
    ]


def page_for(url):
    if "group-syussou" in url:
        return "entries"
    if "group-cyokuzen" in url:
        return "before"
    return "odds"


def test_real_structure_mapping():
    result = parse_page(html(), DAY, 1, "odds")
    assert len(result["rows"]) == 120
    assert {r["combination"] for r in result["rows"]} == combinations()
    for row in result["rows"]:
        a, b, c = map(int, row["combination"].split("-"))
        assert row["odds"] == pytest.approx(a * 100 + b * 10 + c / 10)
    assert result["deadline"] == DEADLINE.isoformat()


def test_entries_and_before_units():
    row = parse_page(html("entries"), DAY, 1, "entries")["rows"][0]
    assert row["racer_id"] == 9001
    assert row["national_score"] == 5.47
    assert row["national_top_two_rate"] == pytest.approx(0.366)
    assert row["motor_top_two_rate"] == pytest.approx(0.368)
    row = parse_page(html("before"), DAY, 1, "before")["rows"][0]
    assert row["exhibition_time"] is None
    assert row["tilt"] == -0.5
    assert row["weight_kg"] == 52


@pytest.mark.parametrize(
    "body",
    [
        b"<html>captcha</html>",
        html(day="20261103"),
        html(race=2),
        html().replace(b"12:00", b"--:--"),
        html().replace(b"chaku_3", b"changed"),
        html().replace(b"120.3", b"unknown"),
    ],
)
def test_structure_or_identity_change_stops(body):
    with pytest.raises(ValueError):
        parse_page(body, DAY, 1, "odds")


def test_20_second_cycles_all_three_pages_and_boundary(tmp_path):
    clock = Clock()
    calls = []
    cfg = config(tmp_path)

    def get(url, timeout):
        calls.append((clock.mono, timeout))
        assert timeout <= (cfg.cutoff - clock.now()).total_seconds() - 1
        clock.sleep(2)
        return Response(200, html(page_for(url)))

    result = run(cfg, clock, get)
    assert [c[0] for c in calls] == [0, 2, 4, 20, 22, 24, 40, 42, 44, 60, 62]
    assert result["reason"] == "cutoff"
    observations = [r for r in records(cfg) if r["event"] == "observation"]
    assert len(observations) == 11
    assert {r["page"] for r in observations} == {"odds", "before", "entries"}
    assert all(datetime.fromisoformat(r["received_at"]) < cfg.cutoff for r in observations)
    assert len(list((cfg.directory / "raw").glob("*.html"))) == 3


@pytest.mark.parametrize("seconds", [0, -30, 1])
def test_no_request_at_or_after_cutoff(tmp_path, seconds):
    clock = Clock(seconds)

    def get(*args):
        pytest.fail("停止境界で通信してはいけない")

    assert run(config(tmp_path), clock, get)["observations"] == 0


def test_deadline_moves_earlier_no_next_page(tmp_path):
    clock = Clock()
    calls = []
    cfg = config(tmp_path)

    def get(url, timeout):
        calls.append(url)
        return Response(200, html(deadline="11:58"))

    result = run(cfg, clock, get)
    assert len(calls) == 1
    assert result["observations"] == 0
    assert any(r["event"] == "cutoff_advanced" for r in records(cfg))


def test_later_deadline_never_extends_window(tmp_path):
    clock = Clock(21)
    calls = []

    def get(url, timeout):
        calls.append(clock.mono)
        return Response(200, html(page_for(url), deadline="12:10"))

    run(config(tmp_path), clock, get)
    assert calls == [0, 0, 0]  # 次の周期は停止ガード境界のため開始しない


def test_slow_cycle_skips_missed_slots(tmp_path):
    clock = Clock(130)
    calls = []
    cfg = config(tmp_path, max_cycles=2)

    def get(url, timeout):
        calls.append(clock.mono)
        clock.sleep(7.5)
        return Response(200, html(page_for(url)))

    run(cfg, clock, get)
    assert calls == [0, 7.5, 15, 40, 47.5, 55]


def test_429_retry_after_and_recovery(tmp_path):
    clock = Clock(180)
    calls = []

    def get(url, timeout):
        calls.append(clock.mono)
        if len(calls) == 1:
            return Response(429, retry_after="60")
        return Response(200, html(page_for(url)))

    result = run(config(tmp_path, max_cycles=2), clock, get)
    assert calls == [0, 60, 60, 60]
    assert result["observations"] == 3


@pytest.mark.parametrize("status", [401, 403, 404, 302])
def test_http_stop_without_retry(tmp_path, status):
    clock = Clock()
    calls = []

    def get(url, timeout):
        calls.append(url)
        return Response(status)

    with pytest.raises(ValueError, match="HTTP"):
        run(config(tmp_path), clock, get)
    assert len(calls) == 1


def test_timeout_near_boundary(tmp_path):
    clock = Clock(5)
    calls = []

    def get(url, timeout):
        calls.append(timeout)
        clock.sleep(timeout)
        raise TimeoutError("総時間上限")

    assert run(config(tmp_path), clock, get)["observations"] == 0
    assert calls == [4]


def test_clock_rollback_does_not_extend(tmp_path):
    clock = Clock(30)
    calls = []

    def get(url, timeout):
        calls.append(clock.mono)
        clock.wall -= timedelta(hours=1)
        return Response(200, html(page_for(url)))

    run(config(tmp_path), clock, get)
    assert calls == [0, 0, 0, 20, 20, 20]
    assert clock.mono <= 30


def test_start_time_and_restart_append(tmp_path):
    clock = Clock(120)
    start = clock.now() + timedelta(seconds=30)
    cfg = config(tmp_path, max_cycles=1, start_at=start)
    calls = []

    def get(url, timeout):
        calls.append(clock.mono)
        return Response(200, html(page_for(url)))

    run(cfg, clock, get)
    run(cfg, clock, get)
    assert calls == [30] * 6
    assert len([r for r in records(cfg) if r["event"] == "observation"]) == 6
    assert summarize_observations(cfg.directory / "observations.jsonl").iloc[0]["observations"] == 2


def test_output_lock(tmp_path):
    with exclusive_run(tmp_path):
        with pytest.raises(ValueError, match="収集中"):
            with exclusive_run(tmp_path):
                pass
    with exclusive_run(tmp_path):
        pass


def test_kill_http_worker_on_total_timeout():
    with patch("boatoz.polling.subprocess.Popen") as factory:
        proc = factory.return_value
        proc.communicate.side_effect = [subprocess.TimeoutExpired("http", 3), (b"", b"")]
        with pytest.raises(subprocess.TimeoutExpired):
            fetch(source_url(DAY, 1, "odds"), 3)
        proc.kill.assert_called_once()
        assert proc.communicate.call_count == 2


def test_latest_missing_odds_is_not_old_value(tmp_path):
    clock = Clock(100)
    calls = []
    cfg = config(tmp_path, max_cycles=2, pages=("odds",))

    def get(url, timeout):
        calls.append(1)
        raw = html()
        if len(calls) == 2:
            raw = raw.replace(b"120.3", b"---")
        return Response(200, raw)

    run(cfg, clock, get)
    row = summarize_observations(cfg.directory / "observations.jsonl")
    row = row[row.combination.eq("1-2-3")].iloc[0]
    assert row["observations"] == 2
    assert row["valid_values"] == 1
    assert pd.isna(row["last_odds"])
    assert row["first_odds"] == 120.3


def test_wrong_day_or_naive_deadline_rejected(tmp_path):
    clock = Clock()
    clock.wall -= timedelta(days=1)
    with pytest.raises(ValueError, match="本日"):
        run(config(tmp_path), clock, lambda *_: pytest.fail())
    with pytest.raises(ValueError, match="タイムゾーン"):
        Config(DAY, 1, DEADLINE.replace(tzinfo=None), tmp_path)


def test_plan_never_fetches(tmp_path, monkeypatch, capsys):
    from boatoz.cli import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "boatoz",
            "tokoname",
            "plan",
            "--date",
            DAY.isoformat(),
            "--race",
            "1",
            "--deadline",
            DEADLINE.isoformat(),
        ],
    )
    with patch("boatoz.polling.fetch", side_effect=AssertionError("no network")):
        main()
    result = json.loads(capsys.readouterr().out)
    assert result["interval_seconds"] == 20
    assert result["requests_per_cycle"] == 3
    assert datetime.fromisoformat(result["cutoff"]) == DEADLINE - timedelta(minutes=2)


def test_export_all_categories_with_time_and_null(tmp_path):
    from boatoz.tokoname import export_observations

    clock = Clock()
    cfg = config(tmp_path, max_cycles=1)
    run(cfg, clock, lambda url, timeout: Response(200, html(page_for(url))))
    output = tmp_path / "csv"
    counts = export_observations(cfg.directory / "observations.jsonl", output)
    assert counts == {"entries": 6, "before": 6, "odds": 120}
    before = pd.read_csv(output / "before.csv")
    assert before.exhibition_time.isna().all()
    assert before.received_at.notna().all()
    assert pd.read_csv(output / "entries.csv").national_score.iloc[0] == 5.47


def test_parse_failure_preserves_raw_and_records_stop(tmp_path):
    clock = Clock()
    cfg = config(tmp_path)
    with pytest.raises(ValueError):
        run(cfg, clock, lambda *_: Response(200, b"<html>changed</html>"))
    assert len(list((cfg.directory / "raw").glob("*.html"))) == 1
    assert records(cfg)[-1]["reason"] == "error"
    assert records(cfg)[-2]["event"] == "parse_stop"


def test_five_consecutive_failures_stop(tmp_path):
    clock = Clock(2000)
    calls = []

    def get(*_):
        calls.append(clock.mono)
        return Response(503)

    with pytest.raises(ValueError, match="5回"):
        run(config(tmp_path), clock, get)
    assert calls == [0, 40, 120, 280, 580]


def test_retry_after_http_date(tmp_path):
    from email.utils import format_datetime

    clock = Clock(180)
    retry_date = format_datetime(clock.now() + timedelta(seconds=90))
    calls = []

    def get(url, timeout):
        calls.append(clock.mono)
        if len(calls) == 1:
            return Response(429, retry_after=retry_date)
        return Response(200, html(page_for(url)))

    run(config(tmp_path, max_cycles=2), clock, get)
    assert calls == [0, 90, 90, 90]


def test_actual_child_is_terminated_at_total_timeout(monkeypatch):
    import sys

    from boatoz import polling

    original_popen = subprocess.Popen
    processes = []

    def sleeper(*args, **kwargs):
        process = original_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(polling.subprocess, "Popen", sleeper)
    with pytest.raises(subprocess.TimeoutExpired):
        fetch(source_url(DAY, 1, "odds"), 0.1)
    assert processes[0].poll() is not None
