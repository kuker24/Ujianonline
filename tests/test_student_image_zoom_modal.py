from pathlib import Path


STUDENT_EXAM_TEMPLATE = Path("templates/student/exam.html")


def _student_exam_template() -> str:
    return STUDENT_EXAM_TEMPLATE.read_text(encoding="utf-8")


def test_student_image_zoom_has_touch_close_controls() -> None:
    template = _student_exam_template()

    assert 'class="zoom-close-btn"' in template
    assert 'onclick="closeImageZoom(event)"' in template
    assert 'ontouchend="closeImageZoom(event)"' in template
    assert 'class="zoom-exit-btn"' in template
    assert 'Tutup gambar' in template


def test_student_image_zoom_close_stops_event_propagation() -> None:
    template = _student_exam_template()

    assert "function closeImageZoom(event)" in template
    assert "event.preventDefault();" in template
    assert "event.stopPropagation();" in template
    assert "if (zoomCloseTimer) clearTimeout(zoomCloseTimer);" in template


def test_student_image_zoom_can_close_from_backdrop_at_normal_zoom() -> None:
    template = _student_exam_template()

    assert "target.closest('.zoom-close-btn, .zoom-exit-btn')" in template
    assert "currentZoom <= 1" in template
    assert "target.classList.contains('image-zoom-container')" in template
