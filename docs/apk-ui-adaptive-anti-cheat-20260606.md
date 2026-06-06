# APK UI Cleanup and Adaptive Anti-Cheat Report - 2026-06-06

## Scope
- Remove distracting normal connection badge text (`Online • sinkron`) from APK exam UI.
- Remove public server URL text below the native login button.
- Change native login ready status copy from `Keamanan APK siap` to `Ujian siap dimulai.`
- Keep anti-cheat enabled during normal operation.
- Add adaptive server-heavy behavior so non-critical anti-cheat telemetry is temporarily suppressed while answer save/final submit remain priority paths.

## Source Changes
### Flutter APK
- `flutter_client_code/lib/pages/native_login_page.dart`
  - Login ready banner now says `Ujian siap dimulai.`
  - Server URL footer below `MASUK` removed.
- `flutter_client_code/lib/pages/exam_page.dart`
  - Connection badge is hidden when the APK is online and fully synced.
  - Badge only appears for degraded/offline/local queued state and is smaller in the lower safe corner.
  - Runtime policy now suppresses non-critical violation reporting when the server policy says `critical_only`.
- `flutter_client_code/lib/services/api_service.dart`
  - Reads `cheating_reporting_mode`, `disabled_violation_types`, and `force_submit_on_violation_enabled` from `/api/runtime/policy`.
  - Direct violation logging and queued violation flushing respect temporary suppression.

### Backend
- `app/core/runtime_policy.py`
  - Adds adaptive anti-cheat policy fields:
    - `cheating_reporting_mode`
    - `disabled_violation_types`
    - `critical_violation_types`
    - `force_submit_on_violation_enabled`
  - Emergency `resource_mode=high/extreme` or degrade mode now overrides `EXAM_PEAK_MODE` for APK policy.
  - Normal mode keeps anti-cheat reporting fully enabled.
  - Busy/degraded mode suppresses non-critical violation telemetry.
- `app/api/violation_events.py`
  - Server fallback ignores non-critical violation events quickly when runtime policy disables them.
  - Critical events remain accepted through the async violation path.

## Adaptive Anti-Cheat Behavior
### Normal / exam peak
- APK token/signature validation: ON.
- Kiosk / lock-task: ON.
- Screenshot blocking: ON.
- Critical violation reporting: ON.
- Non-critical violation reporting: ON.
- Final submit priority: ON.

### Server heavy / degraded
- APK token/signature validation: ON.
- Kiosk / lock-task: ON.
- Screenshot blocking: ON.
- Critical violation reporting: ON.
- Non-critical violation reporting: temporarily OFF/ignored.
- Final submit priority: ON.

Non-critical examples temporarily suppressed:
- `violation_tab_switch`
- `violation_tab_switch_minor`
- `violation_focus_lost`
- `violation_browser_minimize`
- `violation_right_click`
- `violation_cut`
- `violation_overlay_app`
- `violation_accessibility_risk`
- `violation_security_warning`

Critical examples kept active:
- `violation_apk_tampering`
- `violation_screenshot_attempt`
- `violation_screen_recording`
- `violation_external_display`
- `violation_devtools_open`
- `violation_copy`
- `violation_paste`
- `violation_clipboard_violation`

## Local Validation
- `git diff --check`: PASS
- `python3 -m compileall app`: PASS
- `pytest tests/test_runtime_policy.py tests/test_apk_ui_runtime_policy_source.py tests/test_apk_builder_gui_config.py -q`: PASS (`12 passed`)
- `flutter analyze --no-fatal-infos --no-fatal-warnings`: completed with pre-existing info/warnings only
- `flutter test`: PASS

## APK Build
- APK: `/home/fahmi/Downloads/ujian-online-apk/ujian-online-1.0.7-ui-adaptive-20260606-122220.apk`
- SHA256: `1bac6476d6948022228957015aea94c75eb71b73a64165750faeb9f4e8dba045`
- Package: `com.school.examapp`
- Version: `1.0.7`
- Label: `UJIAN ONLINE MAN 1 Rokan Hulu`
- Signing: V2 verified
- Signer cert SHA-256: `297ad1bfc6ed358684ad699569daf4a6565847790211ce726bf53da580ef3187`
- Build token registered in VPS New Update profile with masked token `BUILD-2026...VPUWKJ`.

## VPS Deployment and Validation
Preflight before backend patch/restart:
- `active_sessions=0`
- `running_exam_windows=0`
- `long_active_queries_gt_60s=0`

Backend files patched on VPS:
- `/root/ujian_online/app/core/runtime_policy.py`
- `/root/ujian_online/app/api/violation_events.py`

Restart:
- Rolling restart completed for `api`, `api2` ... `api8`, `api_admin`, `api_admin2`.
- All restarted API containers returned healthy.

Live policy validation:
- Normal state: `mode=exam_peak`, `cheating_reporting_mode=normal`, `disabled_violation_types=[]`, `final_submit_priority=true`.
- Temporary `resource_mode=high` validation: `mode=busy`, `cheating_reporting_mode=critical_only`, non-critical disabled list present, `final_submit_priority=true`.
- Resource mode reset to normal after validation.

APK profile after registration:
- Stable enabled: true
- Accepted token count: 2
- New Update token registered: true
- New Update signature registered: true
- `token_validation_bypass=false`

## Physical Smoke Status
APK `1.0.7` was built and registered, but local ADB smoke could not continue because the phone temporarily disappeared from `adb devices`.

Follow-up manual smoke was then completed by the operator after rebuilding/installing from the synced source. Operator-confirmed checks:
1. APK installs and launches on the phone.
2. Native login footer URL is absent.
3. Native login ready banner says `Ujian siap dimulai.`
4. Normal exam view no longer shows the distracting `Online • sinkron` badge.
5. Updated APK flow is usable on the phone.

## Rollout Decision
- Source/backend adaptive policy: ready and live.
- APK `1.0.8`: built from the synced main worktree and registered as New Update.
- Physical phone UI smoke: PASS by operator confirmation.
- Rollout recommendation: GO for controlled/limited rollout first, with security events and final-submit monitoring kept active.

## Follow-up APK Build from Main Worktree - 2026-06-06
After syncing the main local worktree with the GitHub review branch, a fresh APK was built so `tools/apk_builder_gui.py` / local builds use the updated native-login and adaptive anti-cheat source.

- APK: `/home/fahmi/Downloads/ujian-online-apk/ujian-online-1.0.8-main-updated-20260606-151432.apk`
- SHA256: `08bb73c2836df001736d6d587e3044b28f110399b440514e2811a6dce1f959d9`
- Package: `com.school.examapp`
- Version: `1.0.8`
- Signing: V2 verified
- Signer cert SHA-256: `297ad1bfc6ed358684ad699569daf4a6565847790211ce726bf53da580ef3187`
- New Update token registered on VPS with masked token `BUILD-2026...T5G6MW`.
- Stable profile remains enabled and `token_validation_bypass=false`.

Physical device UI smoke was later confirmed PASS by the operator after rebuilding/installing from the synced source. Continue with controlled rollout monitoring rather than broad unattended rollout.
