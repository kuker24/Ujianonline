from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/load_test_answer_sync.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("load_test_answer_sync", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["load_test_answer_sync"] = module
    spec.loader.exec_module(module)
    return module


load_script = _load_module()


def _args(**overrides):
    values = {
        "base_url": "https://staging.example.test",
        "token": "",
        "session_id": 1001,
        "question_id": 2001,
        "selected_option_id": 3001,
        "sessions_csv": "",
        "vus": 10,
        "duration_seconds": 60,
        "think_ms_min": 500,
        "think_ms_max": 2500,
        "include_violation_burst": False,
        "final_submit_sample_rate": 0.0,
        "summary_json": "",
        "execute": False,
        "allow_production": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_validate_args_rejects_production_host_without_allow_production() -> None:
    with pytest.raises(SystemExit, match="Refusing production traffic"):
        load_script.validate_args(_args(base_url="https://man1rokanhulu.cloud"))


@pytest.mark.parametrize("base_url", ["https://man1rokanhulu.cloud", "http://103.175.218.56"])
def test_validate_args_allows_production_only_with_explicit_flag(base_url) -> None:
    load_script.validate_args(_args(base_url=base_url, allow_production=True))


def test_dry_run_default_does_not_execute_http(monkeypatch, capsys) -> None:
    async def fail_run(*_args, **_kwargs):
        raise AssertionError("run() must not be called during dry-run")

    monkeypatch.setattr(load_script, "run", fail_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_test_answer_sync.py",
            "--base-url",
            "https://staging.example.test",
            "--session-id",
            "1001",
            "--question-id",
            "2001",
        ],
    )

    load_script.main()

    output = capsys.readouterr().out
    assert "Dry-run only" in output
    assert "endpoint=/api/exams/submit-answer" in output


def test_csv_parser_reads_session_question_option_and_token(tmp_path) -> None:
    csv_file = tmp_path / "sessions.csv"
    csv_file.write_text(
        "session_id,question_id,selected_option_id,token\n"
        "1001,2001,3001,token-one\n"
        "1002,2002,,\n",
        encoding="utf-8",
    )

    rows = load_script.load_session_rows(
        csv_file,
        fallback_token="fallback-token",
        fallback_selected_option_id=9999,
    )

    assert rows == [
        load_script.SessionRow(1001, 2001, 3001, "token-one"),
        load_script.SessionRow(1002, 2002, 9999, "fallback-token"),
    ]


def test_execute_with_csv_requires_token_for_every_row(tmp_path) -> None:
    csv_file = tmp_path / "sessions.csv"
    csv_file.write_text(
        "session_id,question_id,selected_option_id,token\n"
        "1001,2001,3001,\n",
        encoding="utf-8",
    )
    rows = load_script.load_session_rows(csv_file, fallback_token="", fallback_selected_option_id=1)

    with pytest.raises(SystemExit, match="--token is required"):
        load_script.validate_args(_args(sessions_csv=str(csv_file), execute=True), rows)


def test_mask_token_does_not_print_full_secret() -> None:
    token = "abcdefghijklmnopqrstuvwxyz"
    masked = load_script.mask_token(token)

    assert masked == "abcd...wxyz"
    assert token not in masked
    assert load_script.mask_token("") == "<empty>"
    assert load_script.mask_token("short") == "****"


def test_round_robin_worker_assignment_is_stable() -> None:
    rows = [
        load_script.SessionRow(1001, 2001, 3001, "t1"),
        load_script.SessionRow(1002, 2002, 3002, "t2"),
        load_script.SessionRow(1003, 2003, 3003, "t3"),
    ]

    assigned_sessions = [load_script.assign_row(rows, worker_id).session_id for worker_id in range(7)]

    assert assigned_sessions == [1001, 1002, 1003, 1001, 1002, 1003, 1001]


def test_success_status_counts_only_2xx() -> None:
    success_codes = [200, 201, 202, 204, 299]
    failure_codes = [0, 300, 400, 401, 403, 404, 429, 500, 503]

    for status_code in success_codes:
        assert load_script.is_success_status(status_code) is True
    for status_code in failure_codes:
        assert load_script.is_success_status(status_code) is False


def test_summarize_counts_4xx_as_failure() -> None:
    samples = [
        load_script.Sample(
            "/api/exams/submit-answer",
            200,
            10.0,
            load_script.is_success_status(200),
        ),
        load_script.Sample(
            "/api/exams/submit-answer",
            429,
            20.0,
            load_script.is_success_status(429),
        ),
        load_script.Sample(
            "/api/exams/submit-answer",
            401,
            30.0,
            load_script.is_success_status(401),
        ),
    ]

    summary = load_script.summarize(samples)
    per_endpoint = summary["per_endpoint"]["/api/exams/submit-answer"]

    assert summary["requests"] == 3
    assert summary["success"] == 1
    assert summary["failures"] == 2
    assert summary["status_counts"] == {200: 1, 401: 1, 429: 1}
    assert per_endpoint["success"] == 1
    assert per_endpoint["failures"] == 2
    assert per_endpoint["status_counts"] == {200: 1, 401: 1, 429: 1}


def test_summarize_includes_percentiles_and_per_endpoint() -> None:
    samples = [
        load_script.Sample("/api/exams/submit-answer", 200, 10.0, True),
        load_script.Sample("/api/exams/submit-answer", 200, 20.0, True),
        load_script.Sample("/api/exams/submit", 503, 30.0, False),
    ]

    summary = load_script.summarize(samples)

    assert summary["requests"] == 3
    assert summary["success"] == 2
    assert summary["failures"] == 1
    assert summary["p50_ms"] == 20.0
    assert summary["p95_ms"] > 0
    assert summary["p99_ms"] > 0
    assert "/api/exams/submit-answer" in summary["per_endpoint"]
    assert summary["per_endpoint"]["/api/exams/submit"]["status_counts"] == {503: 1}


@pytest.mark.parametrize(
    "csv_text,expected",
    [
        ("question_id,selected_option_id,token\n2001,3001,t\n", "missing required column"),
        ("session_id,selected_option_id,token\n1001,3001,t\n", "missing required column"),
        ("session_id,question_id,selected_option_id,token\n,2001,3001,t\n", "session_id and question_id are required"),
    ],
)
def test_invalid_csv_missing_required_session_or_question_fails(tmp_path, csv_text, expected) -> None:
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_text, encoding="utf-8")

    with pytest.raises(SystemExit, match=expected):
        load_script.load_session_rows(csv_file, fallback_token="fallback", fallback_selected_option_id=1)
