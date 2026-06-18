from pathlib import Path


RESULTS_HTML = Path("templates/admin/results.html").read_text(encoding="utf-8")
PDF_GENERATOR = Path("app/core/pdf_generator.py").read_text(encoding="utf-8")
EXAMS_API = Path("app/api/exams.py").read_text(encoding="utf-8")


LEGACY_EXPORT_BRANDING = [
    "Ujian Online",
    "Sistem Ujian Online",
    "Laporan Resmi Hasil Ujian Online",
]


def _function_body(source: str, name: str) -> str:
    marker = f"function {name}("
    start = source.index(marker)
    next_function = source.find("\n        function ", start + len(marker))
    if next_function == -1:
        return source[start:]
    return source[start:next_function]


def test_results_export_uses_siab1_branding_without_legacy_strings() -> None:
    for legacy in LEGACY_EXPORT_BRANDING:
        assert legacy not in RESULTS_HTML
        assert legacy not in PDF_GENERATOR

    assert "SIAB1 — Sistem Informasi Asesmen Berintegritas" in RESULTS_HTML
    assert "csv += `Sistem,${toCsvCell(EXPORT_BRANDING.reportSubtitle)}" in RESULTS_HTML
    assert "Laporan Resmi Hasil Asesmen SIAB1" in PDF_GENERATOR


def test_participation_exports_include_siab1_branding_in_all_formats() -> None:
    assert 'EXPORT_SYSTEM_NAME = "SIAB1 — Sistem Informasi Asesmen Berintegritas"' in EXAMS_API
    assert '("Sistem", EXPORT_SYSTEM_NAME)' in EXAMS_API
    assert 'Laporan Kehadiran Ujian SIAB1' in EXAMS_API
    assert 'document.add_paragraph(EXPORT_SYSTEM_NAME)' in EXAMS_API


def test_download_helpers_append_anchor_and_delay_object_url_revoke() -> None:
    trigger_download = _function_body(RESULTS_HTML, "triggerDownload")
    download_blob = _function_body(RESULTS_HTML, "downloadBlob")
    download_file = _function_body(RESULTS_HTML, "downloadFile")

    assert "document.body.appendChild(anchor)" in trigger_download
    assert "anchor.click()" in trigger_download
    assert "setTimeout(() => anchor.remove(), 0)" in trigger_download

    assert "triggerDownload(url, filename)" in download_blob
    assert "setTimeout(() => URL.revokeObjectURL(url), 30000)" in download_blob
    assert "URL.revokeObjectURL(url);" not in download_blob

    assert "downloadBlob(blob, filename)" in download_file
    assert "URL.createObjectURL" not in download_file


def test_export_dropdown_items_prevent_hash_navigation() -> None:
    assert RESULTS_HTML.count('class="dropdown-item" onclick="event.preventDefault();') == 8
    assert 'href="#" class="dropdown-item" onclick="exportResults' not in RESULTS_HTML
    assert 'href="#" class="dropdown-item" onclick="exportCurrentExamQuestions' not in RESULTS_HTML


def test_question_pdf_opens_reserved_window_before_async_work() -> None:
    export_current = _function_body(RESULTS_HTML, "exportCurrentExamQuestions")
    assert "if (format === 'pdf')" in export_current
    assert "reservedPrintWindow = openQuestionPdfWindow();" in export_current
    assert export_current.index("reservedPrintWindow = openQuestionPdfWindow();") < export_current.index("await api.getQuestions")

    export_pdf = _function_body(RESULTS_HTML, "exportQuestionsPDF")
    assert "reservedPrintWindow || window.open('', '_blank')" in export_pdf
    assert "Popup PDF diblokir browser" in export_pdf
    assert "downloadFile(" in export_pdf


def test_question_word_and_excel_reuse_robust_download_helper() -> None:
    export_word = _function_body(RESULTS_HTML, "exportQuestionsDOCX")
    export_excel = _function_body(RESULTS_HTML, "exportQuestionsExcel")

    assert "downloadFile(" in export_word
    assert "document.body.appendChild(a)" not in export_word
    assert "URL.revokeObjectURL(url)" not in export_word

    assert "downloadFile(" in export_excel
    assert "document.body.appendChild(a)" not in export_excel
    assert "URL.revokeObjectURL(url)" not in export_excel
