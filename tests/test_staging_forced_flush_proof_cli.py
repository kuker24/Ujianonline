import json

from scripts import staging_forced_flush_proof as proof


def _safe_env(**overrides):
    env = {
        "STAGING_FORCE_FLUSH_PROOF": "true",
        "APP_ENV": "staging",
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/staging_test",
        "REDIS_URL": "redis://localhost:6379/0",
        "STAGING_PROOF_ALLOWED_DB_HOSTS": "localhost",
        "STAGING_PROOF_ALLOWED_REDIS_HOSTS": "localhost",
        "STAGING_PROOF_ARTIFACT_DIR": "/tmp/ujianonline-staging-proof-cli-tests",
    }
    env.update(overrides)
    return env


def _json_run(argv, env, capsys):
    code = proof.main(argv, env)
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_parser_exposes_required_subcommands():
    parser = proof.build_parser()

    required = {
        "preflight",
        "run-direct-baseline",
        "run-shadow-baseline",
        "run-buffer-drain",
        "run-worker-restart",
        "run-final-submit-pending",
        "summarize",
        "cleanup-plan",
    }
    subparser_action = next(action for action in parser._actions if getattr(action, "choices", None))
    assert required <= set(subparser_action.choices)


def test_preflight_returns_required_json_shape(capsys):
    code, payload = _json_run(
        ["preflight", "--staging-only", "--i-understand-this-is-staging-only"],
        _safe_env(),
        capsys,
    )

    assert code == 0
    required = {
        "git_head",
        "environment_type",
        "staging_guard_passed",
        "synthetic_prefix",
        "scenario",
        "checked_sessions",
        "checked_answers",
        "payload_hash_mismatch",
        "redis_errors",
        "missing_in_redis",
        "extra_in_redis",
        "answer_queue_pending",
        "answer_queue_processing",
        "answer_queue_deadletter",
        "runtime_answer_buffer_keys_count",
        "answer_queue_keys_count",
        "legacy_answer_queue_keys_count",
        "final_submit_success_count",
        "final_submit_fail_count",
        "worker_restart_tested",
        "redis_reconnect_tested",
        "forced_flush_verified",
        "safe_to_continue",
        "read_only",
        "redacted",
    }
    assert required <= set(payload)
    assert payload["scenario"] == "preflight"
    assert payload["staging_guard_passed"] is True
    assert payload["read_only"] is True


def test_summarize_fail_on_mismatch_exits_nonzero(capsys):
    code, payload = _json_run(
        ["summarize", "--fail-on-mismatch", "--i-understand-this-is-staging-only"],
        _safe_env(STAGING_PROOF_SIMULATE_MISMATCH="1"),
        capsys,
    )

    assert code == 2
    assert payload["payload_hash_mismatch"] == 1
    assert payload["safe_to_continue"] is False


def test_summarize_without_mismatch_exits_zero(capsys):
    code, payload = _json_run(
        ["summarize", "--fail-on-mismatch", "--i-understand-this-is-staging-only"],
        _safe_env(),
        capsys,
    )

    assert code == 0
    assert payload["payload_hash_mismatch"] == 0
    assert payload["redis_errors"] == 0
    assert payload["safe_to_continue"] is True


def test_worker_restart_scenario_refuses_unless_staging_guard_passes(capsys):
    code, payload = _json_run(
        [
            "run-worker-restart",
            "--synthetic-prefix",
            "__PHASE6_FORCE_FLUSH_TEST__",
            "--i-understand-this-is-staging-only",
        ],
        _safe_env(STAGING_FORCE_FLUSH_PROOF="false"),
        capsys,
    )

    assert code == 2
    assert payload["staging_guard_passed"] is False


def test_worker_restart_scenario_is_dry_run_stub_when_guard_passes(capsys):
    code, payload = _json_run(
        [
            "run-worker-restart",
            "--synthetic-prefix",
            "__PHASE6_FORCE_FLUSH_TEST__",
            "--i-understand-this-is-staging-only",
        ],
        _safe_env(),
        capsys,
    )

    assert code == 0
    assert payload["scenario"] == "run-worker-restart"
    assert payload["worker_restart_tested"] is True
    assert payload["execution_mode"] == "dry_run_stub"
    assert payload["writes_synthetic_only"] is True
    assert payload["no_production_target"] is True


def test_scenario_commands_accept_required_synthetic_prefix(capsys):
    for command in [
        "run-direct-baseline",
        "run-shadow-baseline",
        "run-buffer-drain",
        "run-final-submit-pending",
    ]:
        code, payload = _json_run(
            [
                command,
                "--synthetic-prefix",
                "__PHASE6_FORCE_FLUSH_TEST__",
                "--redact",
                "--i-understand-this-is-staging-only",
            ],
            _safe_env(),
            capsys,
        )

        assert code == 0
        assert payload["scenario"] == command
        assert payload["redacted"] is True
        assert payload["writes_synthetic_only"] is True


def test_cleanup_plan_json_shape_is_non_destructive(capsys):
    code, payload = _json_run(
        ["cleanup-plan", "--redact", "--i-understand-this-is-staging-only"],
        _safe_env(),
        capsys,
    )

    assert code == 0
    assert payload["cleanup_plan_only"] is True
    assert payload["cleanup_deletion_executed"] is False
    assert "no broad Redis deletion" in payload["allowed_cleanup_scope"]


def test_help_parses_without_environment_guards(capsys):
    try:
        proof.build_parser().parse_args(["preflight", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
