from __future__ import annotations

from pathlib import Path

ROOT = Path('.')
BOOTSTRAP = ROOT / 'static/js/exam-builder/modules/00-bootstrap-settings-events.js'
RENDERING = ROOT / 'static/js/exam-builder/modules/10-question-core-rendering.js'
SAVE_PREVIEW = ROOT / 'static/js/exam-builder/modules/20-advanced-preview-publish-validate.js'
PUBLISH = ROOT / 'static/js/exam-builder/modules/30-media-modal-publish-time-points.js'
SCHEMA = ROOT / 'app/schemas/exam.py'
BACKEND_EXAMS = ROOT / 'app/api/exams.py'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_pgk_stimulus_helpers_default_missing_flags_to_enabled_and_do_not_switch_type() -> None:
    source = _read(BOOTSTRAP)

    assert 'function getPgkStimulusEnabled(question)' in source
    assert 'function setPgkStimulusEnabled(questionIndex, enabled)' in source
    assert "return question?.pgk_type || settings.pgk_type || 'checkbox';" in source
    assert "if (currentType === 'checkbox'" not in source
    assert "return 'table_validation';" not in source
    assert "return 'checkbox';" not in source


def test_pgk_legacy_type_flags_are_only_stimulus_fallbacks() -> None:
    source = _read(BOOTSTRAP)

    assert 'pgk_type_a_stimulus_enabled' in source
    assert 'pgk_type_b_stimulus_enabled' in source
    assert 'pgk_type_a_enabled' in source
    assert 'pgk_type_b_enabled' in source
    assert 'only as stimulus flags when the new stimulus-specific flags are missing' in source


def test_pgk_stimulus_toggle_ui_replaces_type_active_toggle() -> None:
    rendering = _read(RENDERING)

    assert 'data-pgk-stimulus-toggle="1"' in rendering
    assert 'Stimulus ${stimulusTypeLabel}: ${stimulusEnabled ? \'ON\' : \'OFF\'}' in rendering
    assert 'Stimulus OFF untuk soal ini. Soal tetap ${stimulusTypeLabel}' in rendering
    assert 'data-pgk-type-toggle' not in rendering
    assert 'Tipe aktif:' not in rendering
    assert 'Soal PGK harus memiliki minimal satu tipe aktif' not in rendering


def test_pgk_save_payload_persists_stimulus_flags_and_preserves_answer_data() -> None:
    save_preview = _read(SAVE_PREVIEW)

    assert 'pgk_type_a_stimulus_enabled' in save_preview
    assert 'pgk_type_b_stimulus_enabled' in save_preview
    assert 'pgk_type_a_options' in save_preview
    assert 'pgk_type_a_correct_answers' in save_preview
    assert 'pgk_type_b_statements' in save_preview
    assert 'pgk_type_b_statement_answers' in save_preview
    assert 'getPgkTypeAEnabled' not in save_preview
    assert 'getPgkTypeBEnabled' not in save_preview


def test_pgk_publish_validation_uses_stimulus_toggle_but_keeps_type_validation() -> None:
    source = _read(PUBLISH)

    assert 'const stimulusEnabled = getPgkStimulusEnabled(q);' in source
    assert 'Stimulus wajib diisi atau matikan toggle Stimulus.' in source
    assert "if (resolvedPgkType === 'checkbox')" in source
    assert "} else if (resolvedPgkType === 'table_validation')" in source
    assert 'typeAEnabled' not in source
    assert 'typeBEnabled' not in source
    assert 'Soal PGK harus memiliki minimal satu tipe aktif' not in source


def test_backend_publish_validation_uses_stimulus_flags_without_type_switching() -> None:
    source = _read(BACKEND_EXAMS)

    assert 'pgk_type_a_stimulus_enabled' in source
    assert 'pgk_type_b_stimulus_enabled' in source
    assert 'Stimulus wajib diisi atau matikan toggle Stimulus.' in source
    assert 'pgk_type = "table_validation"' not in source
    assert 'pgk_type = "checkbox"' not in source


def test_pgk_schema_explicitly_allows_stimulus_flags_and_preserve_fields() -> None:
    source = _read(SCHEMA)

    assert 'pgk_type_a_stimulus_enabled: Optional[bool] = None' in source
    assert 'pgk_type_b_stimulus_enabled: Optional[bool] = None' in source
    assert 'pgk_type_a_enabled: Optional[bool] = None' in source
    assert 'pgk_type_b_enabled: Optional[bool] = None' in source
    assert 'pgk_type_a_options: Optional[List[Any]] = None' in source
    assert 'pgk_type_b_statements: Optional[List[Any]] = None' in source
