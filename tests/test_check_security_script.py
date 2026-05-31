from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_check_security_module():
    root_dir = Path(__file__).resolve().parents[1]
    module_path = root_dir / "scripts" / "check_security.py"
    spec = importlib.util.spec_from_file_location("check_security_script", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_is_truthy_env_supports_common_values(monkeypatch) -> None:
    module = _load_check_security_module()
    monkeypatch.setenv("SECURITY_FAIL_ON_TELNET_CLIENT", "YES")
    assert module._is_truthy_env("SECURITY_FAIL_ON_TELNET_CLIENT") is True
    monkeypatch.setenv("SECURITY_FAIL_ON_TELNET_CLIENT", "0")
    assert module._is_truthy_env("SECURITY_FAIL_ON_TELNET_CLIENT") is False
    monkeypatch.setenv(module.SKIP_OUTDATED_ENV, "on")
    assert module._is_truthy_env(module.SKIP_OUTDATED_ENV) is True


def test_parse_requirement_name_handles_extras_and_markers() -> None:
    module = _load_check_security_module()
    assert module._parse_requirement_name("uvicorn[standard]==0.24.0") == "uvicorn"
    assert module._parse_requirement_name("pydantic>=2.7.0") == "pydantic"
    assert module._parse_requirement_name("redis==7.3.0 ; python_version >= '3.11'") == "redis"
    assert module._parse_requirement_name("# comment") is None


def test_check_system_vulnerabilities_telnet_client_not_blocking_by_default(
    monkeypatch,
    capsys,
) -> None:
    module = _load_check_security_module()
    monkeypatch.delenv("SECURITY_FAIL_ON_TELNET_CLIENT", raising=False)

    def fake_which(name: str):
        if name == "telnet":
            return "/usr/bin/telnet"
        if name == "inetutils-telnetd":
            return None
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(
        module,
        "_run_command",
        lambda cmd, timeout, text=True: SimpleNamespace(returncode=0, stdout=""),
    )
    monkeypatch.setattr(
        module,
        "_get_telnet_remove_hint",
        lambda telnet_path: "sudo pacman -Rns inetutils",
    )

    issues = module.check_system_vulnerabilities()
    output = capsys.readouterr().out
    assert issues == 0
    assert "Telnet client binary found" in output
    assert "STRICT MODE" not in output


def test_check_system_vulnerabilities_telnet_client_blocking_in_strict_mode(
    monkeypatch,
    capsys,
) -> None:
    module = _load_check_security_module()
    monkeypatch.setenv("SECURITY_FAIL_ON_TELNET_CLIENT", "true")

    def fake_which(name: str):
        if name == "telnet":
            return "/usr/bin/telnet"
        if name == "inetutils-telnetd":
            return None
        return None

    monkeypatch.setattr(module.shutil, "which", fake_which)
    monkeypatch.setattr(
        module,
        "_run_command",
        lambda cmd, timeout, text=True: SimpleNamespace(returncode=0, stdout=""),
    )
    monkeypatch.setattr(
        module,
        "_get_telnet_remove_hint",
        lambda telnet_path: "sudo pacman -Rns inetutils",
    )

    issues = module.check_system_vulnerabilities()
    output = capsys.readouterr().out
    assert issues == 1
    assert "STRICT MODE" in output
