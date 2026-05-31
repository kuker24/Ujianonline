from pathlib import Path


EXAMS_SOURCE = Path("app/api/exams.py").read_text(encoding="utf-8")


def test_offline_package_uses_backward_compatible_show_exam_timer_fallback() -> None:
    assert '"show_exam_timer": bool(getattr(session.exam, "show_exam_timer", True))' in EXAMS_SOURCE
