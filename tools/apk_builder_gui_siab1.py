#!/usr/bin/env python3
"""Launch the existing APK Builder GUI with SIAB1 branding applied."""
from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

TOOLS_DIR = Path(__file__).resolve().parent
BUILDER_FILE = TOOLS_DIR / "apk_builder_gui.py"
FULL_NAME = "SIAB1 — Sistem Informasi Asesmen Berintegritas"

REPLACEMENTS = (
    ("UJIAN ONLINE MAN 1 Rokan Hulu", FULL_NAME),
    ("Ujian Online MAN 1 Rokan Hulu", FULL_NAME),
    ("UJIAN ONLINE SEB", "SIAB1"),
    ("Ujian Online", "SIAB1"),
    ("UJIAN ONLINE", "SIAB1"),
)


def _load_builder_module():
    spec = importlib.util.spec_from_file_location("siab1_apk_builder_legacy", BUILDER_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Tidak dapat memuat APK Builder: {BUILDER_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _replace_brand(value: str) -> str:
    updated = value
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def _rebrand_widget_tree(widget: tk.Misc) -> None:
    try:
        if "text" in widget.keys():
            current = widget.cget("text")
            if isinstance(current, str):
                updated = _replace_brand(current)
                if updated != current:
                    widget.configure(text=updated)
    except (tk.TclError, AttributeError):
        pass
    for child in widget.winfo_children():
        _rebrand_widget_tree(child)


def main() -> int:
    try:
        module = _load_builder_module()
        root = tk.Tk()
        app = module.APKBuilderGUI(root)
        root.title("SIAB1 - APK Builder v3.1")
        if hasattr(app, "app_name_var"):
            app.app_name_var.set(FULL_NAME)
        _rebrand_widget_tree(root)
        root.mainloop()
        return 0
    except Exception as exc:
        try:
            messagebox.showerror("SIAB1 APK Builder", str(exc))
        except Exception:
            print(f"SIAB1 APK Builder gagal dimulai: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
