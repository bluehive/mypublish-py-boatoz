import json
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd
import pytest

from boatoz.analysis import monthly, recent_races, summarize
from boatoz.data import download, normalize, parse_files
from boatoz.model import evaluate, score
from boatoz.plot import scatter

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample():
    return pd.read_csv(ROOT / "data/sample_races.csv")


@pytest.fixture
def payload():
    return json.loads((ROOT / "tests/fixtures/results.json").read_text())


def test_normalize_missing_and_duplicate(payload):
    payload["races"][0]["boats"][0]["racer_place_number"] = "F"
    frame = normalize(payload)
    assert len(frame) == 6
    assert pd.isna(frame.iloc[0]["rank"])
    assert frame.iloc[0]["race_id"] == "2026-01-01-09-01"
    payload["races"][0]["boats"].append(payload["races"][0]["boats"][0])
    with pytest.raises(ValueError, match="重複"):
        normalize(payload)


def test_parse_overlap():
    path = ROOT / "tests/fixtures/results.json"
    assert len(parse_files([path])) == 6
    with pytest.raises(ValueError):
        parse_files([path, path])
    with pytest.raises(ValueError):
        parse_files([])


def test_recent_complete_races(sample):
    recent = recent_races(sample.sample(frac=1, random_state=7), 5)
    assert len(recent) == 30
    assert recent.race_id.nunique() == 5
    assert recent.date.min() == "2026-01-11"
    with pytest.raises(ValueError):
        recent_races(sample, 0)


def test_summary_denominator(sample):
    frame = sample.iloc[:6].copy()
    frame["rank"] = [1, 2, 3, 4, 5, None]
    summary = summarize(frame, "stadium").iloc[0]
    assert summary["starts"] == 5
    assert summary["win_rate"] == pytest.approx(0.2)
    assert summary["top_two_rate"] == pytest.approx(0.4)
    assert monthly(sample).iloc[0]["starts"] == 216


def test_evaluation_hand_computed(sample):
    frame = sample.iloc[:12].copy()
    frame["win_rate"] = 0.5
    frame["motor_rate"] = 0.5
    frame["rank"] = [1, 2, 3, 4, 5, 6, 2, 1, 3, 4, 5, 6]
    result = evaluate(frame)
    assert result["races"] == 2
    assert result["accuracy"] == 0.5
    assert result["course1_accuracy"] == 0.5
    frame.loc[0, "rank"] = None
    assert evaluate(frame)["excluded_races"] == 1
    assert evaluate(frame.iloc[:0])["accuracy"] is None
    frame.loc[1, "motor_rate"] = 40
    with pytest.raises(ValueError):
        score(frame)


def test_no_rank_leakage(sample):
    original = score(sample)["score"]
    sample["rank"] = 6
    pd.testing.assert_series_equal(score(sample)["score"], original)


def test_download_cache_and_404(tmp_path, payload):
    response = __import__("io").BytesIO(json.dumps(payload).encode())
    day = date(2026, 1, 1)
    with patch("boatoz.data.urlopen", return_value=response) as request:
        assert download(day, day, tmp_path, 0)[0][1] == "saved"
        assert download(day, day, tmp_path, 0)[0][1] == "cached"
        assert request.call_count == 1
    with patch("boatoz.data.urlopen", side_effect=HTTPError("url", 404, "", {}, None)):
        assert download(date(2026, 1, 2), date(2026, 1, 2), tmp_path, 0)[0][1] == "unavailable"
    with patch("boatoz.data.urlopen", side_effect=HTTPError("url", 500, "", {}, None)):
        with pytest.raises(HTTPError):
            download(date(2026, 1, 3), date(2026, 1, 3), tmp_path, 0)


def test_plot(sample, tmp_path):
    target = tmp_path / "scatter.png"
    scatter(sample, target)
    assert target.read_bytes().startswith(b"\x89PNG")


def test_cli(sample, monkeypatch, capsys):
    from boatoz.cli import main

    monkeypatch.setattr("sys.argv", ["boatoz", "predict", str(ROOT / "data/sample_races.csv")])
    main()
    assert json.loads(capsys.readouterr().out)["races"] == 36


def test_national_schema(payload):
    national = {"results": payload["races"]}
    pd.testing.assert_frame_equal(normalize(national), normalize(payload))


def test_empty_national():
    assert normalize({"results": []}).empty
