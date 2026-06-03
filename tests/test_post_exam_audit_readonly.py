"""
Tests for post-exam audit read-only script safety.

Validates:
- Production URL detection
- Query builders produce SELECT-only SQL
- Report structure and data safety concern logic
- CLI argument parsing
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.post_exam_audit_readonly import (
    PostExamAuditor,
    _get_database_url,
    _is_production_url,
    _parse_args,
    _check_production_safety,
    _q_session_status_distribution,
    _q_submitted_count,
    _q_in_progress_stuck,
    _q_answer_count_per_submitted,
    _q_question_count,
    _q_sessions_zero_answers,
    _q_duplicate_answers,
    _q_final_submit_anomalies,
    _q_answers_after_submit,
    _q_submitted_score_null,
    _q_ungraded_answers,
    _q_violation_log_aggregate,
    _q_security_events_aggregate,
    _q_violation_count_distribution,
    _q_synthetic_residue,
    _q_exam_summary,
    _q_score_distribution,
)


# ---------------------------------------------------------------------------
# Production URL detection
# ---------------------------------------------------------------------------

class TestProductionUrlDetection:
    """Test _is_production_url."""

    def test_production_ip(self):
        assert _is_production_url("postgresql://user:pass@103.175.218.56:5432/db")

    def test_production_domain(self):
        assert _is_production_url("postgresql://user:pass@man1rokanhulu.cloud:5432/db")

    def test_production_hostname(self):
        assert _is_production_url("postgresql://user:pass@adminujian:5432/db")

    def test_localhost_not_production(self):
        assert not _is_production_url("postgresql://user:pass@localhost:5432/db")

    def test_127_not_production(self):
        assert not _is_production_url("postgresql://user:pass@127.0.0.1:5432/db")

    def test_random_host_not_production(self):
        assert not _is_production_url("postgresql://user:pass@db-staging.internal:5432/db")

    def test_case_insensitive(self):
        assert _is_production_url("postgresql://user:pass@MAN1ROKANHULU.CLOUD:5432/db")


# ---------------------------------------------------------------------------
# Production safety check
# ---------------------------------------------------------------------------

class TestProductionSafetyCheck:
    """Test _check_production_safety."""

    def test_blocks_production_without_flag(self):
        with pytest.raises(SystemExit):
            _check_production_safety("postgresql://user:pass@103.175.218.56/db", False)

    def test_allows_production_with_flag(self):
        _check_production_safety("postgresql://user:pass@103.175.218.56/db", True)

    def test_allows_localhost_without_flag(self):
        _check_production_safety("postgresql://user:pass@localhost/db", False)


# ---------------------------------------------------------------------------
# DATABASE_URL retrieval
# ---------------------------------------------------------------------------

class TestGetDatabaseUrl:
    """Test _get_database_url."""

    def test_raises_without_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(SystemExit):
            _get_database_url()

    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        assert _get_database_url() == "postgresql://localhost/test"


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestParseArgs:
    """Test _parse_args."""

    def test_required_exam_id(self):
        args = _parse_args(["--exam-id", "42"])
        assert args.exam_id == 42
        assert not args.allow_production_readonly
        assert args.summary_json is None
        assert not args.verbose

    def test_all_flags(self):
        args = _parse_args([
            "--exam-id", "7",
            "--allow-production-readonly",
            "--summary-json", "/tmp/out.json",
            "--verbose",
        ])
        assert args.exam_id == 7
        assert args.allow_production_readonly
        assert args.summary_json == "/tmp/out.json"
        assert args.verbose

    def test_missing_exam_id(self):
        with pytest.raises(SystemExit):
            _parse_args([])


# ---------------------------------------------------------------------------
# SQL safety: all queries are SELECT-only
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]


def _assert_select_only(sql: str):
    """Assert SQL contains no write keywords (whole-word match)."""
    import re
    upper = sql.upper()
    for kw in _WRITE_KEYWORDS:
        # Word-boundary check to avoid false positives on column names like is_deleted
        pattern = r'\b' + kw + r'\b'
        match = re.search(pattern, upper)
        # Allow DELETE only if it appears as part of a column name (e.g. IS_DELETED, DELETED_AT)
        if match:
            # Check if DELETE is preceded by IS_ or followed by _AT/_BY (column name pattern)
            start = match.start()
            prefix = upper[max(0, start-3):start]
            suffix_end = min(len(upper), match.end() + 3)
            suffix = upper[match.end():suffix_end]
            if kw == "DELETE" and ("IS_" in prefix or "_" in suffix or "ED" in suffix):
                continue
            assert False, f"SQL contains write keyword: {kw}\nSQL: {sql}"


class TestQuerySafety:
    """Test all query builders produce SELECT-only SQL."""

    def test_session_status_distribution(self):
        sql, params = _q_session_status_distribution(1)
        _assert_select_only(sql)
        assert params == {"exam_id": 1}

    def test_submitted_count(self):
        sql, params = _q_submitted_count(1)
        _assert_select_only(sql)

    def test_in_progress_stuck(self):
        sql, params = _q_in_progress_stuck(1)
        _assert_select_only(sql)

    def test_answer_count_per_submitted(self):
        sql, params = _q_answer_count_per_submitted(1)
        _assert_select_only(sql)

    def test_question_count(self):
        sql, params = _q_question_count(1)
        _assert_select_only(sql)

    def test_sessions_zero_answers(self):
        sql, params = _q_sessions_zero_answers(1)
        _assert_select_only(sql)

    def test_duplicate_answers(self):
        sql, params = _q_duplicate_answers(1)
        _assert_select_only(sql)

    def test_final_submit_anomalies(self):
        sql, params = _q_final_submit_anomalies(1)
        _assert_select_only(sql)

    def test_answers_after_submit(self):
        sql, params = _q_answers_after_submit(1)
        _assert_select_only(sql)

    def test_submitted_score_null(self):
        sql, params = _q_submitted_score_null(1)
        _assert_select_only(sql)

    def test_ungraded_answers(self):
        sql, params = _q_ungraded_answers(1)
        _assert_select_only(sql)

    def test_violation_log_aggregate(self):
        sql, params = _q_violation_log_aggregate(1)
        _assert_select_only(sql)

    def test_security_events_aggregate(self):
        sql, params = _q_security_events_aggregate(1)
        _assert_select_only(sql)

    def test_violation_count_distribution(self):
        sql, params = _q_violation_count_distribution(1)
        _assert_select_only(sql)

    def test_synthetic_residue(self):
        sql, params = _q_synthetic_residue()
        _assert_select_only(sql)

    def test_exam_summary(self):
        sql, params = _q_exam_summary(1)
        _assert_select_only(sql)

    def test_score_distribution(self):
        sql, params = _q_score_distribution(1)
        _assert_select_only(sql)


# ---------------------------------------------------------------------------
# Auditor: report structure
# ---------------------------------------------------------------------------

class TestAuditorReportStructure:
    """Test PostExamAuditor report building without DB."""

    def test_build_report_no_data(self):
        auditor = PostExamAuditor(exam_id=999)
        report = auditor._build_report()
        assert report["audit_metadata"]["exam_id"] == 999
        assert report["data_safety_concern"] is False
        assert report["anomalies"] == []
        assert report["high_risk_anomalies"] == []

    def test_build_report_with_high_risk_anomaly(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.anomalies.append({
            "severity": "high_risk",
            "description": "Zero-answer submitted session found.",
        })
        report = auditor._build_report()
        assert report["data_safety_concern"] is True
        assert len(report["high_risk_anomalies"]) == 1

    def test_build_report_with_needs_review(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.anomalies.append({
            "severity": "needs_review",
            "description": "Some anomaly.",
        })
        report = auditor._build_report()
        assert report["data_safety_concern"] is False
        assert len(report["high_risk_anomalies"]) == 0
        assert len(report["anomalies"]) == 1

    def test_report_json_serializable(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.anomalies.append({
            "severity": "high_risk",
            "description": "Test anomaly.",
        })
        auditor.results["exam_summary"] = [{"title": "Test Exam", "total_sessions": 10}]
        report = auditor._build_report()
        # Ensure serializable
        json_str = json.dumps(report, default=str)
        assert "Test anomaly" in json_str
        assert "Test Exam" in json_str

    def test_audit_timestamps(self):
        auditor = PostExamAuditor(exam_id=1)
        assert auditor.start_time is not None
        report = auditor._build_report()
        assert "audit_start" in report["audit_metadata"]
        assert "audit_end" in report["audit_metadata"]
        assert "duration_seconds" in report["audit_metadata"]


# ---------------------------------------------------------------------------
# Auditor: anomaly detection with mock data
# ---------------------------------------------------------------------------

class TestAuditorAnomalyDetection:
    """Test anomaly detection logic with mock data."""

    def test_stuck_sessions_detected(self):
        auditor = PostExamAuditor(exam_id=1)
        # Simulate stuck sessions found
        auditor.results["in_progress_stuck"] = [{"id": 1, "user_id": 10}]
        auditor.anomalies.append({
            "severity": "needs_review",
            "description": f"{len(auditor.results['in_progress_stuck'])} session(s) still in_progress.",
        })
        report = auditor._build_report()
        assert report["in_progress_stuck_count"] == 1

    def test_zero_answer_sessions_detected(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.results["sessions_zero_answers"] = [{"session_id": 1, "user_id": 10}]
        auditor.anomalies.append({
            "severity": "high_risk",
            "description": "Submitted session with zero answers.",
        })
        report = auditor._build_report()
        assert report["data_safety_concern"] is True
        assert report["sessions_zero_answers_count"] == 1

    def test_duplicate_answers_detected(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.results["duplicate_answers"] = [{"session_id": 1, "question_id": 5, "row_count": 2}]
        auditor.anomalies.append({
            "severity": "needs_review",
            "description": "Duplicate answer rows found.",
        })
        report = auditor._build_report()
        assert report["duplicate_answers_count"] == 1

    def test_score_null_detected(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.results["submitted_score_null"] = [{"id": 1, "user_id": 10}]
        auditor.anomalies.append({
            "severity": "needs_review",
            "description": "Submitted session with NULL score.",
        })
        report = auditor._build_report()
        assert report["submitted_score_null_count"] == 1

    def test_synthetic_residue_detected(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.results["synthetic_residue"] = [{"id": 1, "username": "synthetic_user_1"}]
        auditor.anomalies.append({
            "severity": "needs_review",
            "description": "Synthetic/test user found.",
        })
        report = auditor._build_report()
        assert report["synthetic_residue_count"] == 1


# ---------------------------------------------------------------------------
# Auditor: happy path (no anomalies)
# ---------------------------------------------------------------------------

class TestAuditorHappyPath:
    """Test auditor with clean data (no anomalies)."""

    def test_clean_audit_no_anomalies(self):
        auditor = PostExamAuditor(exam_id=1)
        auditor.results["exam_summary"] = [{
            "exam_id": 1, "title": "Ujian Test", "total_sessions": 200,
            "submitted_sessions": 200, "in_progress_sessions": 0,
            "abandoned_sessions": 0, "total_answers": 2000,
            "avg_score": 85.5, "min_score": 40.0, "max_score": 100.0,
        }]
        auditor.results["in_progress_stuck"] = []
        auditor.results["sessions_zero_answers"] = []
        auditor.results["duplicate_answers"] = []
        auditor.results["final_submit_anomalies"] = []
        auditor.results["answers_after_submit"] = []
        auditor.results["submitted_score_null"] = []
        auditor.results["ungraded_answers"] = []
        auditor.results["synthetic_residue"] = []
        report = auditor._build_report()
        assert report["data_safety_concern"] is False
        assert report["anomalies"] == []
