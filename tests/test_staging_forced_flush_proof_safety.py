import json
from pathlib import Path

from scripts import staging_forced_flush_proof as proof


def _safe_env(**overrides):
    env = {
        "STAGING_FORCE_FLUSH_PROOF": "true",
        "APP_ENV": "staging",
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@staging-db/staging_test",
        "REDIS_URL": "redis://staging-redis:6379/0",
        "STAGING_PROOF_ALLOWED_DB_HOSTS": "staging-db,localhost",
        "STAGING_PROOF_ALLOWED_REDIS_HOSTS": "staging-redis,localhost",
        "STAGING_PROOF_ARTIFACT_DIR": "/tmp/ujianonline-staging-proof-tests",
    }
    env.update(overrides)
    return env


def _run(argv, env=None, capsys=None):
    code = proof.main(argv, env or _safe_env())
    captured = capsys.readouterr().out if capsys else ""
    return code, json.loads(captured) if captured else {}


def test_refuses_when_app_env_is_production(capsys):
    code, payload = _run(
        ["preflight", "--i-understand-this-is-staging-only"],
        _safe_env(APP_ENV="production"),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "production" in payload["error"]


def test_refuses_when_staging_flag_is_not_true(capsys):
    code, payload = _run(
        ["preflight", "--i-understand-this-is-staging-only"],
        _safe_env(STAGING_FORCE_FLUSH_PROOF="false"),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "STAGING_FORCE_FLUSH_PROOF" in payload["error"]


def test_refuses_without_explicit_confirmation(capsys):
    code, payload = _run(["preflight"], _safe_env(), capsys)

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "i-understand" in payload["error"]


def test_refuses_if_production_domain_or_host_appears(capsys):
    code, payload = _run(
        ["preflight", "--i-understand-this-is-staging-only"],
        _safe_env(
            DATABASE_URL="postgresql+asyncpg://user:pass@103.175.218.56/staging_test",
            STAGING_PROOF_ALLOWED_DB_HOSTS="103.175.218.56",
        ),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "production host" in payload["error"]


def test_refuses_production_like_database_name(capsys):
    code, payload = _run(
        ["preflight", "--i-understand-this-is-staging-only"],
        _safe_env(DATABASE_URL="postgresql+asyncpg://user:pass@staging-db/exam_system"),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "database name" in payload["error"]


def test_requires_synthetic_prefix_for_scenario(capsys):
    code, payload = _run(
        [
            "run-direct-baseline",
            "--synthetic-prefix",
            "WRONG_PREFIX",
            "--i-understand-this-is-staging-only",
        ],
        _safe_env(),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False
    assert "PHASE6_FORCE_FLUSH_TEST" in payload["error"]


def test_redaction_is_default_and_output_contains_no_raw_answer_token_or_pii(capsys):
    env = _safe_env(
        SECRET_TOKEN="SUPER_SECRET_TOKEN_SHOULD_NOT_APPEAR",
        RAW_ANSWER="RAW_ANSWER_SHOULD_NOT_APPEAR",
        USER_EMAIL="student@example.invalid",
    )
    code, payload = _run(
        [
            "run-shadow-baseline",
            "--synthetic-prefix",
            "__PHASE6_FORCE_FLUSH_TEST__",
            "--i-understand-this-is-staging-only",
        ],
        env,
        capsys,
    )
    output = json.dumps(payload)

    assert code == 0
    assert payload["redacted"] is True
    assert "SUPER_SECRET_TOKEN_SHOULD_NOT_APPEAR" not in output
    assert "RAW_ANSWER_SHOULD_NOT_APPEAR" not in output
    assert "student@example.invalid" not in output


def test_cleanup_plan_does_not_delete_by_default(capsys):
    code, payload = _run(
        ["cleanup-plan", "--i-understand-this-is-staging-only"],
        _safe_env(),
        capsys,
    )

    assert code == 0
    assert payload["cleanup_plan_only"] is True
    assert payload["cleanup_deletion_executed"] is False
    assert payload["cleanup_requires_separate_approval"] is True


def test_preflight_and_summarize_modes_report_no_db_or_redis_writes(capsys):
    for command in ["preflight", "summarize"]:
        code, payload = _run(
            [command, "--i-understand-this-is-staging-only"],
            _safe_env(),
            capsys,
        )

        assert code == 0
        assert payload["read_only"] is True
        assert payload["no_db_writes"] is True
        assert payload["no_redis_writes"] is True


def test_source_does_not_import_database_or_redis_clients_for_preflight_safety():
    source = Path("scripts/staging_forced_flush_proof.py").read_text(encoding="utf-8")

    forbidden_imports = [
        "from app.database",
        "import redis",
        "redis.asyncio",
        "asyncpg",
        "sqlalchemy",
    ]
    for marker in forbidden_imports:
        assert marker not in source
