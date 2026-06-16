from pathlib import Path

from scripts.check_siab1_ui_regressions import check_form_control_visibility


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_minimal_valid_files(root: Path) -> None:
    _write(
        root / "static/css/responsive.css",
        """
input[type="checkbox"]:not(.custom-checkbox),
input[type="radio"]:not(.custom-checkbox) {
    -webkit-appearance: auto;
    -moz-appearance: auto;
    appearance: auto;
}
select.custom-select-arrow { appearance: none; }
""",
    )
    _write(
        root / "templates/admin/exam-templates.html",
        """
<style>
.custom-modal-body { color: var(--text-primary); }
.class-checkbox { appearance: auto; width: 18px; height: 18px; }
.class-checkbox:focus-visible { outline: 3px solid rgba(99, 102, 241, 0.45); }
.class-checkbox:disabled { opacity: 0.55; }
.class-checkbox-row:has(.class-checkbox:checked) { background: rgba(99, 102, 241, 0.12); }
</style>
<label class="class-checkbox-row">
  <input type="checkbox" class="class-checkbox" value="X">
  <span class="class-checkbox-label">X</span>
</label>
<script>
document.querySelectorAll('.class-checkbox:checked')
</script>
""",
    )
    _write(
        root / "templates/admin/users.html",
        """
<style>
.custom-checkbox { appearance: none; }
.custom-checkbox::before { content: ""; }
.custom-checkbox:checked::before { transform: scale(1); }
</style>
""",
    )
    _write(
        root / "static/css/admin.css",
        ".toggle-switch input:checked + .toggle-slider { background: var(--primary); }\n",
    )


def test_form_control_visibility_guard_accepts_scoped_native_and_custom_controls(tmp_path):
    _write_minimal_valid_files(tmp_path)

    assert check_form_control_visibility(tmp_path) == []


def test_form_control_visibility_guard_blocks_firefox_global_input_appearance_none(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(
        tmp_path / "static/css/responsive.css",
        """
@-moz-document url-prefix() {
    input,
    textarea,
    select {
        -moz-appearance: none;
        appearance: none;
    }
}
""",
    )

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("Firefox" in message for message in messages)
    assert any("global input/textarea/select" in message for message in messages)


def test_form_control_visibility_guard_blocks_global_input_appearance_none(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(tmp_path / "static/css/admin.css", "input { appearance: none; }\n")

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("global input appearance:none" in message for message in messages)


def test_form_control_visibility_guard_blocks_native_checkbox_radio_appearance_none(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(
        tmp_path / "static/css/responsive.css",
        """
input[type="checkbox"],
input[type="radio"] { appearance: none; }
""",
    )

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("native checkbox/radio" in message for message in messages)


def test_form_control_visibility_guard_blocks_webkit_select_arrow_removal(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(
        tmp_path / "static/css/responsive.css",
        """
@media screen and (-webkit-min-device-pixel-ratio: 0) {
    select {
        background-image: none;
        -webkit-appearance: none;
        appearance: none;
    }
}
""",
    )

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("select arrows" in message for message in messages)


def test_form_control_visibility_guard_blocks_broad_modal_color_selector(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(
        tmp_path / "templates/admin/exam-templates.html",
        """
<style>
.custom-modal-body * { color: white !important; }
</style>
""",
    )

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any(".custom-modal-body *" in message for message in messages)
    assert any("class-checkbox" in message for message in messages)


def test_form_control_visibility_guard_requires_class_checkbox_visual_states(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(
        tmp_path / "templates/admin/exam-templates.html",
        """
<label><input type="checkbox" class="class-checkbox" value="X">X</label>
<script>document.querySelectorAll('.class-checkbox:checked')</script>
""",
    )

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("visible wrapper" in message for message in messages)
    assert any("visible width" in message for message in messages)
    assert any("focus-visible" in message for message in messages)


def test_form_control_visibility_guard_preserves_existing_custom_checkbox_and_toggle(tmp_path):
    _write_minimal_valid_files(tmp_path)
    _write(tmp_path / "templates/admin/users.html", ".custom-checkbox { appearance: none; }\n")
    _write(tmp_path / "static/css/admin.css", "")

    messages = [issue.message for issue in check_form_control_visibility(tmp_path)]

    assert any("custom-checkbox checkmark" in message for message in messages)
    assert any("toggle switch checked" in message for message in messages)
