"""20秒周期・締切2分前停止。ネットワーク、時計、待機を差し替えて検証可能。"""

import base64
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from .tokoname import JST, PAGES, parse_page, source_url, utcnow

INTERVAL = 20.0
GUARD = 1.0


@dataclass
class Response:
    status: int
    body: bytes = b""
    retry_after: str | None = None


def fetch(url, timeout):
    process = subprocess.Popen(
        [sys.executable, "-m", "boatoz.tokoname_http", url, str(timeout)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        output, error = process.communicate(timeout=timeout)
    except BaseException:
        process.kill()
        process.communicate()
        raise
    if process.returncode:
        raise OSError(error.decode("utf-8", errors="replace")[:300])
    result = json.loads(output)
    if "error" in result:
        raise OSError(result["error"])
    return Response(
        result["status"], base64.b64decode(result.get("body", "")), result.get("retry_after")
    )


@dataclass(frozen=True)
class Config:
    day: date
    race: int
    deadline: datetime
    output: Path
    pages: tuple = ("odds", "before", "entries")
    start_at: datetime | None = None
    max_cycles: int | None = None

    def __post_init__(self):
        source_url(self.day, self.race, "odds")
        if self.deadline.tzinfo is None or self.deadline.utcoffset() is None:
            raise ValueError("締切にはタイムゾーンを指定してください")
        if self.deadline.astimezone(JST).date() != self.day:
            raise ValueError("締切日と開催日が一致しません")
        if self.start_at is not None:
            if self.start_at.tzinfo is None or self.start_at.utcoffset() is None:
                raise ValueError("開始時刻にはタイムゾーンを指定してください")
            if self.start_at >= self.deadline - timedelta(minutes=2):
                raise ValueError("開始時刻が収集停止時刻以降です")
        if not self.pages or len(set(self.pages)) != len(self.pages):
            raise ValueError("取得種類が空または重複しています")
        if any(page not in PAGES for page in self.pages):
            raise ValueError("不明な取得種類です")
        if self.max_cycles is not None and self.max_cycles < 1:
            raise ValueError("max_cyclesは1以上です")

    @property
    def cutoff(self):
        return self.deadline - timedelta(minutes=2)

    @property
    def directory(self):
        return self.output / self.day.isoformat() / f"08-R{self.race:02}"

    def plan(self):
        return {
            "date": self.day.isoformat(),
            "race": self.race,
            "start_at": self.start_at.isoformat() if self.start_at else "now",
            "deadline": self.deadline.isoformat(),
            "cutoff": self.cutoff.isoformat(),
            "interval_seconds": INTERVAL,
            "requests_per_cycle": len(self.pages),
            "directory": str(self.directory),
            "urls": [source_url(self.day, self.race, p) for p in self.pages],
        }


@contextmanager
def exclusive_run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    # 同一出力先の同一レースを複数プロセスで動かさない。OSが異常終了時も解放。
    with (directory / ".lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("同じ出力先でこのレースを収集中です") from exc
        yield


def _append(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _retry_delay(value, now):
    if value is None:
        return INTERVAL
    try:
        return max(INTERVAL, float(int(value)))
    except ValueError:
        try:
            return max(INTERVAL, (parsedate_to_datetime(value) - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return INTERVAL


def collect(config, *, get=fetch, now=utcnow, monotonic=time.monotonic, sleep=time.sleep):
    if now().astimezone(JST).date() != config.day:
        raise ValueError("ライブ収集は本日（JST）のレースだけ実行できます")
    with exclusive_run(config.directory):
        return _collect(config, get, now, monotonic, sleep)


def _collect(config, get, now, monotonic, sleep):
    directory = config.directory
    log = directory / "observations.jsonl"
    cutoff = config.cutoff
    mono_cutoff = monotonic() + max(0, (cutoff - now()).total_seconds())

    def remaining():
        return min((cutoff - now()).total_seconds(), mono_cutoff - monotonic())

    def wait_until(target):
        while remaining() > GUARD and monotonic() < target:
            sleep(max(0, min(1.0, target - monotonic(), remaining() - GUARD)))

    def event(kind, **fields):
        _append(log, {"event": kind, "at": now().isoformat(), **fields})

    event("start", **config.plan())
    target = monotonic()
    if config.start_at:
        target += max(0, (config.start_at - now()).total_seconds())
    cycles = observations = failures = 0
    reason = "cutoff"
    try:
        while remaining() > GUARD:
            wait_until(target)
            if remaining() <= GUARD:
                break
            cycle_start = monotonic()
            cycles += 1
            retry_delay = INTERVAL
            for page in config.pages:
                if remaining() <= GUARD:
                    break
                url = source_url(config.day, config.race, page)
                requested_at = now().isoformat()
                timeout = min(8.0, remaining() - GUARD)
                try:
                    response = get(url, timeout)
                except (OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
                    failures += 1
                    event("request_error", page=page, error=str(exc), consecutive=failures)
                    retry_delay = min(300, INTERVAL * 2 ** min(failures, 4))
                    break
                if response.status == 429 or 500 <= response.status <= 599:
                    failures += 1
                    retry_delay = max(
                        _retry_delay(response.retry_after, now()),
                        min(300, INTERVAL * 2 ** min(failures, 4)),
                    )
                    event(
                        "http_retry",
                        page=page,
                        status=response.status,
                        delay_seconds=retry_delay,
                        consecutive=failures,
                    )
                    break
                if response.status != 200:
                    event("http_stop", page=page, status=response.status)
                    raise ValueError(f"HTTP {response.status}: 収集停止（{page}）")
                received_at = now()
                digest = hashlib.sha256(response.body).hexdigest()
                rawdir = directory / "raw"
                rawdir.mkdir(exist_ok=True)
                rawpath = rawdir / f"{digest}.html"
                if not rawpath.exists():
                    temporary = rawpath.with_suffix(".tmp")
                    temporary.write_bytes(response.body)
                    temporary.replace(rawpath)
                try:
                    parsed = parse_page(response.body, config.day, config.race, page)
                except ValueError as exc:
                    event("parse_stop", page=page, sha256=digest, error=str(exc))
                    raise
                observed_cutoff = datetime.fromisoformat(parsed["deadline"]) - timedelta(minutes=2)
                if observed_cutoff < cutoff:
                    cutoff = observed_cutoff
                    mono_cutoff = min(mono_cutoff, monotonic() + (cutoff - now()).total_seconds())
                    event("cutoff_advanced", cutoff=cutoff.isoformat())
                # 締切変更や遅い応答で境界を越えたデータは分析用の観測にしない。
                if received_at >= cutoff or remaining() <= 0:
                    event("late_response", page=page, sha256=digest)
                    break
                _append(
                    log,
                    {
                        "event": "observation",
                        **parsed,
                        "url": url,
                        "requested_at": requested_at,
                        "received_at": received_at.isoformat(),
                        "sha256": digest,
                        "raw_file": f"raw/{digest}.html",
                        "cycle": cycles,
                    },
                )
                observations += 1
            else:
                failures = 0
            if failures >= 5:
                raise ValueError("連続5回の通信障害により停止しました")
            if config.max_cycles and cycles >= config.max_cycles:
                reason = "max_cycles"
                break
            # 遅延時に取り逃した回数を一気に要求しない。周期は開始時刻基準。
            elapsed = monotonic() - cycle_start
            slots = max(1, math.floor(elapsed / INTERVAL) + 1)
            target = max(
                cycle_start + slots * INTERVAL, monotonic() + retry_delay if failures else 0
            )
    except KeyboardInterrupt:
        reason = "interrupted"
        raise
    except Exception:
        reason = "error"
        raise
    finally:
        event(
            "stop",
            reason=reason,
            cycles=cycles,
            observations=observations,
            cutoff=cutoff.isoformat(),
        )
    return {"reason": reason, "cycles": cycles, "observations": observations, "log": str(log)}
