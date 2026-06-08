from __future__ import annotations

from pathlib import Path

ROOT = Path('.')
BOOTSTRAP = ROOT / 'static/js/exam-builder/modules/00-bootstrap-settings-events.js'
RENDERING = ROOT / 'static/js/exam-builder/modules/10-question-core-rendering.js'
SAVE_PREVIEW = ROOT / 'static/js/exam-builder/modules/20-advanced-preview-publish-validate.js'
PUBLISH = ROOT / 'static/js/exam-builder/modules/30-media-modal-publish-time-points.js'
SCHEMA = ROOT / 'app/schemas/exam.py'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_pgk_toggle_helpers_default_missing_flags_to_enabled() -> None:
    source = _read(BOOTSTRAP)

    assert 'function getPgkTypeAEnabled(question)' in source
    assert 'function getPgkTypeBEnabled(question)' in source
    assert 'settings.pgk_type_a_enabled !== false' in source
    assert 'settings.pgk_type_b_enabled !== false' in source
    assert 'question?.pgk_type_a_enabled !== false' in source
    assert 'question?.pgk_type_b_enabled !== false' in source


def test_pgk_toggle_ui_persists_to_question_settings_without_clearing_data() -> None:
    rendering = _read(RENDERING)
    save_preview = _read(SAVE_PREVIEW)

    assert 'data-pgk-type-toggle="A"' in rendering
    assert 'data-pgk-type-toggle="B"' in rendering
    assert 'pgk_type_a_enabled: true' in rendering
    assert 'pgk_type_b_enabled: true' in rendering
    assert 'pgk_type_a_options' in save_preview
    assert 'pgk_type_a_correct_answers' in save_preview
    assert 'pgk_type_b_statements' in save_preview
    assert 'pgk_type_b_statement_answers' in save_preview


def test_pgk_publish_validation_respects_enabled_type_and_blocks_both_off() -> None:
    source = _read(PUBLISH)

    assert 'Soal PGK harus memiliki minimal satu tipe aktif: Tipe A atau Tipe B.' in source
    assert "resolvedPgkType === 'checkbox' && typeAEnabled" in source
    assert "resolvedPgkType === 'table_validation' && typeBEnabled" in source
    assert 'Soal No. ${num} (PGK Tipe A):' in source
    assert 'Soal No. ${num} (PGK Tipe B):' in source


def test_pgk_schema_explicitly_allows_toggle_and_preserve_fields() -> None:
    source = _read(SCHEMA)

    assert 'pgk_type_a_enabled: Optional[bool] = None' in source
    assert 'pgk_type_b_enabled: Optional[bool] = None' in source
    assert 'pgk_type_a_options: Optional[List[Any]] = None' in source
    assert 'pgk_type_b_statements: Optional[List[Any]] = None' in source
