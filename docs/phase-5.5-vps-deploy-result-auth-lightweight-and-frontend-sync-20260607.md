# Phase 5.5 VPS Deploy Result — Auth Lightweight and Frontend Bundle Sync

Date: 2026-06-07

## 1. Latest GitHub head reviewed

Before deploy:

```text
branch: review/sanitized-root-20260531-115153
head: ac6c64f7b08bcc775c08218b139b816189f4e493
commit: docs: add phase 5.5 vps deploy plan for auth and frontend sync
new commits before deploy: none
```

Required Phase 5.4 commits were present:

```text
3ec8768 fix: use lightweight auth user loading
b94b656 fix: sync frontend bundle modules with safe monitoring flow
508b3b9 docs: record phase 5.4 auth and frontend bundle sync
ac6c64f docs: add phase 5.5 vps deploy plan for auth and frontend sync
```

## 2. Operator approval

Deployment proceeded after explicit operator approval:

```text
approve deploy Phase 5.4
```

## 3. Source validation before deploy

Source validation was run from a clean detached worktree at GitHub head `ac6c64f`.

Commands:

```bash
python -m compileall app
SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test PYTHONPATH=. uv run --with-requirements requirements.txt --with pytest pytest \
  tests/test_production_readiness_defaults.py \
  tests/test_restart_safe_guards.py \
  tests/test_frontend_bundle_sync.py \
  tests/test_answer_sync_service_routing.py \
  tests/test_auth_identity_loading.py \
  tests/test_admin_user_lightweight_queries.py \
  tests/test_auto_restart_scheduler_modal.py \
  -q
scripts/verify_frontend_bundles.sh
node --check static/js/api.js
node --check static/js/admin/monitoring.js
git diff --check
```

Result:

```text
compileall: PASS
pytest targeted suite: 78 passed
verify_frontend_bundles.sh: PASS (28 bundles)
node --check static/js/api.js: PASS
node --check static/js/admin/monitoring.js: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

## 4. VPS preflight result

Preflight was read-only and passed.

```text
health local: 200
health public: 200
active sessions: 0
running exam windows: 0
final-submit/drain: 0
DB long active queries >60s: 0
DB idle-in-transaction: 0
Redis PING: PONG
Redis rejected_connections: 0
Redis evicted_keys: 0
disk /: 52% used
memory available: ~11456 MB
load-test processes: none
next exam start: 2026-06-08 00:30:00+00:00
```

Effective env before deploy:

```json
{"ADMIN_MONITORING_DETAIL_LEVEL":"summary","ANSWER_QUEUE_ENABLED":false,"ANSWER_QUEUE_PERCENTAGE":0,"ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED":false,"ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE":0,"ANSWER_WRITE_MODE":"direct","EXAM_PEAK_MODE":true,"MOBILE_APK_PRIMARY":true,"VIOLATION_ASYNC_ENABLED":true}
```

## 5. Files deployed

Total files copied: 77.

```text
app/api/auth.py
app/api/grading.py
app/api/users.py
app/core/security.py
scripts/build_activity_logs_bundle.sh
scripts/build_admin_core_bundle.sh
scripts/build_alarm_system_bundle.sh
scripts/build_api_bundle.sh
scripts/build_api_error_handler_bundle.sh
scripts/build_auth_bundle.sh
scripts/build_bootstrap_modal_fix_bundle.sh
scripts/build_custom_confirm_bundle.sh
scripts/build_dashboard_widgets_bundle.sh
scripts/build_empty_state_bundle.sh
scripts/build_exam_builder_bundle.sh
scripts/build_exam_scheduling_bundle.sh
scripts/build_exam_system_bundle.sh
scripts/build_exam_templates_bundle.sh
scripts/build_header_user_bundle.sh
scripts/build_media_library_bundle.sh
scripts/build_mobile_nav_bundle.sh
scripts/build_modern_modals_bundle.sh
scripts/build_monitoring_bundle.sh
scripts/build_notifications_bundle.sh
scripts/build_performance_optimizer_bundle.sh
scripts/build_profile_modal_bundle.sh
scripts/build_seb_auth_diagnostic_bundle.sh
scripts/build_seb_builder_bundle.sh
scripts/build_sidebar_loader_bundle.sh
scripts/build_toast_bundle.sh
scripts/build_universal_modal_fix_bundle.sh
scripts/build_user_management_bundle.sh
static/js/activity-logs.js
static/js/admin-core.js
static/js/admin/monitoring.js
static/js/admin/monitoring/modules/00-core-ops-and-sessions.js
static/js/alarm-system.js
static/js/api-error-handler.js
static/js/api-error-handler/modules/00-api-error-handler-core.js
static/js/api.js
static/js/api/modules/30-ui-shortcuts.js
static/js/auth.js
static/js/auth/modules/10-auth-bootstrap-utils.js
static/js/bootstrap-modal-fix.js
static/js/custom-confirm.js
static/js/custom-confirm/modules/00-custom-confirm-core.js
static/js/dashboard-widgets.js
static/js/empty-state.js
static/js/exam-builder.js
static/js/exam-builder/modules/00-bootstrap-settings-events.js
static/js/exam-scheduling.js
static/js/exam-scheduling/modules/00-exam-scheduling-core.js
static/js/exam-system.js
static/js/exam-templates.js
static/js/exam-templates/modules/10-exam-templates-bootstrap.js
static/js/header-user.js
static/js/media-library.js
static/js/media-library/modules/00-sanitize-and-render-utils.js
static/js/media-library/modules/10-media-library-class.js
static/js/mobile-nav.js
static/js/modern-modals.js
static/js/modern-modals/modules/00-styles-utilities-static-modal.js
static/js/notifications.js
static/js/performance-optimizer.js
static/js/performance-optimizer/modules/10-performance-optimizer-bootstrap-export.js
static/js/profile-modal.js
static/js/profile-modal/modules/20-avatar-sync-and-bootstrap.js
static/js/seb-auth-diagnostic.js
static/js/seb-builder.js
static/js/sidebar-loader.js
static/js/sidebar-loader/modules/10-sidebar-loader-bootstrap.js
static/js/toast.js
static/js/toast/modules/00-toast-core.js
static/js/universal-modal-fix.js
static/js/universal-modal-fix/modules/00-universal-modal-fix-core.js
static/js/user-management.js
static/js/user-management/modules/00-user-management-core.js
```

## 6. Files explicitly not deployed

```text
.env
.env.*
docker-compose.production.yml
APK/AAB
flutter_client_code/build
keystore/JKS/key.properties/local.properties
DB dump/backup/sql/sqlite/db
session CSV/summary JSON
node_modules
tests
docs as runtime files
raw token/secret files
```

## 7. Backup directory

```text
/root/ujian_online_backups/phase-5.4-auth-frontend-20260606T203324Z
```

Payload:

```text
a601a779df8b8a03a73dc82578248f1ec752477505b010b5f34e33e7a6c19204  /tmp/phase55_payload.tar.gz
```

## 8. Pre/post checksums

Format:

```text
path<TAB>pre_live_sha256<TAB>post_live_sha256<TAB>source_sha256
```

```text
app/api/auth.py	14efbaecf64a79dd631f4a38c434b0587215e674db5a0fbfb8bd9ffa074dda4f	95578ac41753c5dacc249396175c86c5bbfedbd969450b25dc11fa23248da40a	95578ac41753c5dacc249396175c86c5bbfedbd969450b25dc11fa23248da40a
app/api/grading.py	bbba6b0759177442565a265161aa2d3e057a8115b7fb92634e5038cc6dc93c8c	740437a828cbb1fc99c21e95f39c8aefdae3d503d5e7268b26a13adfdf25dbcd	740437a828cbb1fc99c21e95f39c8aefdae3d503d5e7268b26a13adfdf25dbcd
app/api/users.py	3009f6cecbfe0e81f5a784ebeb0d02fdf85c31bd385dfccbf1ac81fabdddcdf9	5fa5c5cd9596b20954d72c3a330b72bc01c8ffcc9dc0779b86e27a919266ef98	5fa5c5cd9596b20954d72c3a330b72bc01c8ffcc9dc0779b86e27a919266ef98
app/core/security.py	83789df48cecad8f0444e45f582b46bd38b4fefec847197869a47b418246ac81	efcf0f63d59d5412511ac0573076d1442b280191b5fbc2af1f1ec6cde05a6c72	efcf0f63d59d5412511ac0573076d1442b280191b5fbc2af1f1ec6cde05a6c72
scripts/build_activity_logs_bundle.sh	3cb5a548d5356d4b333c53fc3cd00c126fffdaaef1828960dbd49050a6f2317c	a85d694be66bd834792d2507c9122f3c2dfd6a99885bdc99866dcfc71bee5472	a85d694be66bd834792d2507c9122f3c2dfd6a99885bdc99866dcfc71bee5472
scripts/build_admin_core_bundle.sh	86d02d7fa90f488caf9d5e45ffe42ec79a465a0f85589e73c440cac86fcf4b89	2a137cd91dd2f37bc7c3348bf48ba7be918d222fdef3b93f2b24fd72d0f5dd82	2a137cd91dd2f37bc7c3348bf48ba7be918d222fdef3b93f2b24fd72d0f5dd82
scripts/build_alarm_system_bundle.sh	8ccb0de495cab945ece19aaedefde0ae1d8c7993bcaa703390697643fb7e67f4	8cb895dea4eb3c6d484ea0732927776332607297d6b3115e3b21477ee64f51c0	8cb895dea4eb3c6d484ea0732927776332607297d6b3115e3b21477ee64f51c0
scripts/build_api_bundle.sh	e9c93356fc10af0ffe46840c81aba66282338258c65c4509f12c86c1f387b3f0	08698c355f85299a11d3093c4016022cd9ecf2405025debdc40ed9c40fe09a8f	08698c355f85299a11d3093c4016022cd9ecf2405025debdc40ed9c40fe09a8f
scripts/build_api_error_handler_bundle.sh	468c640b9a146029e58579e2289791523520eb9b971c2a44b1dc6b20f328bdcb	30ce640250b58ec9c1735433269b77c869911520c650ce5ba702fbf8580cf6ff	30ce640250b58ec9c1735433269b77c869911520c650ce5ba702fbf8580cf6ff
scripts/build_auth_bundle.sh	cdf52a2907c1fb3a1410b50157f3ac43ce4a6c16bcafe150e8d8a0058edde5e0	121f50dc23771ca3b1eb8e485f54e708b15479b5bc180a56a351de74a17282e7	121f50dc23771ca3b1eb8e485f54e708b15479b5bc180a56a351de74a17282e7
scripts/build_bootstrap_modal_fix_bundle.sh	d7f7440ad99b407a262460ede3832fb1c731c8f2db2aca37328ee06e4eaeffb7	9a9e3e2f6bb4b2cbdb8b0e7bc0420b2a23bf7c78f996d7b0628308d315a6be57	9a9e3e2f6bb4b2cbdb8b0e7bc0420b2a23bf7c78f996d7b0628308d315a6be57
scripts/build_custom_confirm_bundle.sh	dcf8c3011802c475998038a2f1cd6be84246e12064b28fe58bf1a882ffef9e6f	c4f15a5f9d2233359b199b814d035d4420d24814bbed660127e0070865ccbbd7	c4f15a5f9d2233359b199b814d035d4420d24814bbed660127e0070865ccbbd7
scripts/build_dashboard_widgets_bundle.sh	f821bdf176632f15f3577fc4dac84001b56d7f42f36d131415006b42808198c9	bd3fb2cfe7bb338324dab80ce581e3ff27baaf0c195f6e925dded60beb15ab87	bd3fb2cfe7bb338324dab80ce581e3ff27baaf0c195f6e925dded60beb15ab87
scripts/build_empty_state_bundle.sh	3792653719d80c867b95dad1e7d8967423f306cb5e5d47fdd4056e4ee5e3a71b	0325da795b526fd08c4e058e62ad5a068c809232ab33bed7fafb3f1e2e53d59b	0325da795b526fd08c4e058e62ad5a068c809232ab33bed7fafb3f1e2e53d59b
scripts/build_exam_builder_bundle.sh	f7df765e9377a2113566c2877a1d9322c7122818268436c118ce3b4fcc51f59f	3f3bddac2048d7cb773271909bf897c4ea630337fdcf78022d5aff5d879f6400	3f3bddac2048d7cb773271909bf897c4ea630337fdcf78022d5aff5d879f6400
scripts/build_exam_scheduling_bundle.sh	97e80ad7031f6154e34e00aa4beee73a9b03bc6a28fc7fb5071c70183e1a2987	2201bad8b03ecbbf13c68e6a309cd27a7b5c3b953ee9c3f1b388bd16ea822c8e	2201bad8b03ecbbf13c68e6a309cd27a7b5c3b953ee9c3f1b388bd16ea822c8e
scripts/build_exam_system_bundle.sh	3d47afc466c918f53f4cdaa8ad5452ec5b3d337e6c0344d8454becfddbf6b4c1	e71ba749fc4c8efdf6c2582e6682c622afecafa5e60fe02eb2178feffd9c0b35	e71ba749fc4c8efdf6c2582e6682c622afecafa5e60fe02eb2178feffd9c0b35
scripts/build_exam_templates_bundle.sh	ea166d07349f9b20e8a42aa245583cab0295be483480f178b81b3c238138c562	70dca2b2ae77624b58ecfd6ef3944d55b117785a511cdc9e52c5938cba18db1e	70dca2b2ae77624b58ecfd6ef3944d55b117785a511cdc9e52c5938cba18db1e
scripts/build_header_user_bundle.sh	b213dd6d766c7e562a0ed9b361c0d78660f3d721ee02a53c52bca272adc4b423	d472901107b225d3b604285f2ff6737db28b6f1ca46e2788b7dd36ba5ce25ef0	d472901107b225d3b604285f2ff6737db28b6f1ca46e2788b7dd36ba5ce25ef0
scripts/build_media_library_bundle.sh	51b1ea694f8c065e556e85795a7656898c164ea6109100db33894bf99cd772c3	0d14d2734247f355e5bf7cdf785581df4095d672f48e3d0705464410ed8e8d60	0d14d2734247f355e5bf7cdf785581df4095d672f48e3d0705464410ed8e8d60
scripts/build_mobile_nav_bundle.sh	b04aec2041d921b82dab075d8aa351accb26ab37b6c74477f1ae2c5a18040d72	9d56798e1bdc6553871f4f8ab7445471894f61f701a4247bac01d825d64cc7c7	9d56798e1bdc6553871f4f8ab7445471894f61f701a4247bac01d825d64cc7c7
scripts/build_modern_modals_bundle.sh	893aecbc92cdac29622f85ab2b72f6f54ed759461b2a263d7d789a3f99e13631	fcc8bfac1e3da33c46003153cf344959345b1e857690e337c8a8b0b15007e264	fcc8bfac1e3da33c46003153cf344959345b1e857690e337c8a8b0b15007e264
scripts/build_monitoring_bundle.sh	0b690382df2c3371b087b95282b43df56ef33fa24d1e87dac99c2126dc2b24b8	04859d566679cc360c2ec3d79efa2e71458077213a0829d12e5b4b9fb40c8009	04859d566679cc360c2ec3d79efa2e71458077213a0829d12e5b4b9fb40c8009
scripts/build_notifications_bundle.sh	b570e999844463f30375afab772b5d8d0ef69f1e2e7f2f678baac80093d4c122	918ce8f5df185b4936da7d3bbd6eedd0c2b8090555c4d94fcf787b8bb9471629	918ce8f5df185b4936da7d3bbd6eedd0c2b8090555c4d94fcf787b8bb9471629
scripts/build_performance_optimizer_bundle.sh	435a01d92584f09e4da1d7d44ff840626317bce93d4bb66a786c5ceaf8eb097d	f9c84afccd059b785c6b6bf53d25a98b18619f745f8cdd4935b574edffefe1ec	f9c84afccd059b785c6b6bf53d25a98b18619f745f8cdd4935b574edffefe1ec
scripts/build_profile_modal_bundle.sh	de75ce0a982cb1d03f947b27a05656386d871cf8d5e10dd40b21c9e32347b0a9	ea6ef106038d456e52711ac6c78f19864bde574572dd80ff590eefb23a2d7899	ea6ef106038d456e52711ac6c78f19864bde574572dd80ff590eefb23a2d7899
scripts/build_seb_auth_diagnostic_bundle.sh	d46cbc0a26191a4b502748b4aa5a143f2c74ba069ca630dc06d4c31dd9caa44d	e2b7fe0fa0b4d874fb1f2789846affeb305566be3207526e40961cdfeacbf307	e2b7fe0fa0b4d874fb1f2789846affeb305566be3207526e40961cdfeacbf307
scripts/build_seb_builder_bundle.sh	93df811567064d8a5372b224c637fc130d8aa6c6e0014d9f5f0d5fc574997318	94cbd624f89da73d90cdd68c23926be7ea070f3e456c0f3f5b8c35d08e71a27a	94cbd624f89da73d90cdd68c23926be7ea070f3e456c0f3f5b8c35d08e71a27a
scripts/build_sidebar_loader_bundle.sh	a4233737d781ea460da3316ed2223dde8787d5ecf49820b87d511c295aeff5fd	7dc8996e783059c03408530b2e02c50f31e33cb370b2aea1d349b39a10e210ef	7dc8996e783059c03408530b2e02c50f31e33cb370b2aea1d349b39a10e210ef
scripts/build_toast_bundle.sh	47b3afa049c68485641f0ecb54b30e7a4cf2f6da69552f19b00bd99c4efc7647	3dbe665358c11dfa9fcf200109092d977b5e25acc8dda97efb63f6f397456189	3dbe665358c11dfa9fcf200109092d977b5e25acc8dda97efb63f6f397456189
scripts/build_universal_modal_fix_bundle.sh	4cf5772d84e848d28e6fbbfbebeb51d60f9ee8f1ba4f0d5220612c4da446eea3	8db49352044264dfa4e26362dd593334db07ea40ef6b9f9663bc86c07a8a0a11	8db49352044264dfa4e26362dd593334db07ea40ef6b9f9663bc86c07a8a0a11
scripts/build_user_management_bundle.sh	bb24cd0be19b33672ad4f0f874a224852ace73f99ee7986f547c88d941bc8f1f	63b424a482ba2aab29423212affedcccd001970c268e3f62a8c44ea20c1b7c98	63b424a482ba2aab29423212affedcccd001970c268e3f62a8c44ea20c1b7c98
static/js/activity-logs.js	d4688a90105ecc5b237e64476b4202296f1fd5cb5eed69fdc353b6ef39d6cb4c	aaa3a1337dd1bf34d9ab2d151a3385a38db14266fe7168e989c589a85b4fa918	aaa3a1337dd1bf34d9ab2d151a3385a38db14266fe7168e989c589a85b4fa918
static/js/admin-core.js	df231f67bc4465d1d84daba0e42b0e3653434864f0fbfe0682f82ab24c1e4a33	999d8142e22722538969b2ac632bbe41c7a565da2196f81e6cf730b2ba03e5a9	999d8142e22722538969b2ac632bbe41c7a565da2196f81e6cf730b2ba03e5a9
static/js/admin/monitoring.js	a6748d3b80459f411324b92367fa7338352a95cda25fe5caa0b4d4e8fb383706	df734121e45463a2f11227e68a6a0bd0341c1f71f64c0c91596c04794bdf3f43	df734121e45463a2f11227e68a6a0bd0341c1f71f64c0c91596c04794bdf3f43
static/js/admin/monitoring/modules/00-core-ops-and-sessions.js	835c5fe127cf1a00e61e4ff79365a28de1948b0e50687ee9f6e93cac76b54a70	03355dba5df2006e8b8b22d47fd8127be9e5e6141dfb56249bb19dc8f68f705a	03355dba5df2006e8b8b22d47fd8127be9e5e6141dfb56249bb19dc8f68f705a
static/js/alarm-system.js	c9ebdddd6a1b319a519e94bb3e168b0e15b7c3757877ac644b0aa458cb0609d1	5d6edfb96ba4dc58712662060ec0a1d4154c575dca099dce08b7e2aa58e7c028	5d6edfb96ba4dc58712662060ec0a1d4154c575dca099dce08b7e2aa58e7c028
static/js/api-error-handler.js	759c28dd4b69956f9cd80b1983764a2ca1a237f6bcf953c69957d372ca64a501	74e892909c865c68a6e40b0cd99bc48b42c408b1d70a64308296e72b743894e9	74e892909c865c68a6e40b0cd99bc48b42c408b1d70a64308296e72b743894e9
static/js/api-error-handler/modules/00-api-error-handler-core.js	cdddd46d2d32689ab650b804fc0f1ee614a6e73c39c6e88cbb51eb8cfd8ed02b	cdf9946c46b4133070da3fe0768d5c9772c1337aefdf06b292ba7b243c8b51e4	cdf9946c46b4133070da3fe0768d5c9772c1337aefdf06b292ba7b243c8b51e4
static/js/api.js	7b19134da0d759a646057e0fc71ff5a44a7a2f2a8ffdf15b68d5bb40fee187eb	233b8aeb172af217b12d2511d9a878a845b1d5b520682c959482f069fc85d010	233b8aeb172af217b12d2511d9a878a845b1d5b520682c959482f069fc85d010
static/js/api/modules/30-ui-shortcuts.js	9f3e06cd46f5190a11cc715867d4af3962303b3479f72d6494f9a763568bc02d	e4f8d3c5511e26557999a33dd1a783fca30a9f19252d5f6c3010980eb0c7eb6c	e4f8d3c5511e26557999a33dd1a783fca30a9f19252d5f6c3010980eb0c7eb6c
static/js/auth.js	c2e18a607d6d930720249c4147942d0a4b10726252fb17c6033d61e9b446623b	6837a390033fa3c1880d16a15061c6dc086533ce0d1bc4710d0d02dbd0334c4a	6837a390033fa3c1880d16a15061c6dc086533ce0d1bc4710d0d02dbd0334c4a
static/js/auth/modules/10-auth-bootstrap-utils.js	9ddaa39f3b289f7bbbdf44efa1170f912a2c63caa109fddeed576e9d82e3b15a	4e9d84890e2bdd827f3dadebb2d89873a820ed4300740c456224439ed1b36550	4e9d84890e2bdd827f3dadebb2d89873a820ed4300740c456224439ed1b36550
static/js/bootstrap-modal-fix.js	2cd16028b355010cb463c88b6f0fb55e93857c49855f738f56d77adf30924801	a921fea40625c27408105555543c4980f04cfee9d850b6e6c5acab3f2291cf3e	a921fea40625c27408105555543c4980f04cfee9d850b6e6c5acab3f2291cf3e
static/js/custom-confirm.js	6e766ae30fcd8ee0b2e7412a4f910469545b5d3bd806df3774ed7058430f02fa	aa72bbecc039f81c460df9c637238a5825deb3a58468b350047e996f09194d63	aa72bbecc039f81c460df9c637238a5825deb3a58468b350047e996f09194d63
static/js/custom-confirm/modules/00-custom-confirm-core.js	6f77dd6d36b0ec9fc6d8e75981c7a01be6e382598b993f935b302683056efd0d	ec88dac05ec9aa982c1496aeeaebdf36ddabb33a7abfd7ca39475425c8a349ae	ec88dac05ec9aa982c1496aeeaebdf36ddabb33a7abfd7ca39475425c8a349ae
static/js/dashboard-widgets.js	8e5732023cef1d96a60fa252743559622052a52e05ee0b67771569f78e4bc3dc	d2b1d73e331bca2a5be997ffd80b1b9a4e642d6bc0361ea08681ffe2c468bfb0	d2b1d73e331bca2a5be997ffd80b1b9a4e642d6bc0361ea08681ffe2c468bfb0
static/js/empty-state.js	355bdf436133bbe3db43cce773a5b3a596a6b7c3feda0eda514bd00e76598c08	86573d2d5a8531b438a9e53a79af6535dd0da999aca809f40deaa5319dfc14fb	86573d2d5a8531b438a9e53a79af6535dd0da999aca809f40deaa5319dfc14fb
static/js/exam-builder.js	3ebdb72d5b651764875368e465b38b185a2c64ad2e3f2b355d92b55ed9a69bf6	d8d1ffeafe6802bb60483befc64389d7d9628a08320715b4dd554ad0b4e3c6b3	d8d1ffeafe6802bb60483befc64389d7d9628a08320715b4dd554ad0b4e3c6b3
static/js/exam-builder/modules/00-bootstrap-settings-events.js	0c2d9b68fdd6a35826ee50a3c1e97d28fb247f3eb30f4054707586b0a343807e	a65bd5d43629cf2c9c432c995ef1fcf22f23271c57a8da131371bfc07d523345	a65bd5d43629cf2c9c432c995ef1fcf22f23271c57a8da131371bfc07d523345
static/js/exam-scheduling.js	f7ad1df462299ea835bcaffe733e832d4a213cb14c0eaf12f88f4407ac8cd67c	6a1fa163272010024a1715156a84493887daf93f0a9e0ff65453aaf8640710e9	6a1fa163272010024a1715156a84493887daf93f0a9e0ff65453aaf8640710e9
static/js/exam-scheduling/modules/00-exam-scheduling-core.js	02e9d0bb84d27be55bdb5f3b5125064017cf530505f0e13f6cdd6e1a6360c39a	4109e3067dd334c59e5e4d8d2498ab0721a99f555ab1eb9162221aa072d1a718	4109e3067dd334c59e5e4d8d2498ab0721a99f555ab1eb9162221aa072d1a718
static/js/exam-system.js	65db58a40506c313644fa70f3d85cc6c215937024f22180e59318b395d994e02	ab5bb7aecf18c3dc0553c27b75a500e903be9e0645e49f9940e6284b5d7a142e	ab5bb7aecf18c3dc0553c27b75a500e903be9e0645e49f9940e6284b5d7a142e
static/js/exam-templates.js	b8ee70bba796742e3e2bf9b6136108641ab14f2a735da7a1d9bed38fb53be0bb	a60c21b4d917d73260446b3d28c1f91110c3beb44d9ac8e6b8dcced2fc7e0ec3	a60c21b4d917d73260446b3d28c1f91110c3beb44d9ac8e6b8dcced2fc7e0ec3
static/js/exam-templates/modules/10-exam-templates-bootstrap.js	b83f4cad4e2c19831652019448f6a4fdfa1fc6f94aaf0a0ea2a5e38988491660	23c976adc2a8e2ca734210ede1bcd0b73c80cbbdc8dfb89aed33cdee86733d69	23c976adc2a8e2ca734210ede1bcd0b73c80cbbdc8dfb89aed33cdee86733d69
static/js/header-user.js	8dc42c1a0b0ccf23690fd56de60208a47fae5ee71ba38582fb73bf43ecdc78a3	d69481475cfa8a5a69781cf83158215b9d46338fa027e99be9b775882d44473e	d69481475cfa8a5a69781cf83158215b9d46338fa027e99be9b775882d44473e
static/js/media-library.js	627a5db99a219e5443d7ea9ce2a99e4f0bc7b7bed82c2acfe33a5ac150c02093	246de03466a1a38a6214e5ddfd0a6d76544ac7c41dee898a08c67582fbc13460	246de03466a1a38a6214e5ddfd0a6d76544ac7c41dee898a08c67582fbc13460
static/js/media-library/modules/00-sanitize-and-render-utils.js	56ee33cf8278a01d954b7acbf1de071e65d09d1cfc7a277dd03a7938c38e76f7	dda965da183e1b75443664f317d495da328e090861be6804aa77369ae71cce9c	dda965da183e1b75443664f317d495da328e090861be6804aa77369ae71cce9c
static/js/media-library/modules/10-media-library-class.js	b98100c7e0ce6131ead504fe7b95f93f6a4a2bbf5b2882859418282365403942	447254440197d03879f1044f1f1949b1cab255f2cb0a1b35556a39e2ad7c954b	447254440197d03879f1044f1f1949b1cab255f2cb0a1b35556a39e2ad7c954b
static/js/mobile-nav.js	2551984a5e00daf131f481c78a08aedcce9671f956fb9f0a358cef77692805dc	ff02722566c434356968b617cb2f5014e96f6527cc2f0a13be5be120ea94cd65	ff02722566c434356968b617cb2f5014e96f6527cc2f0a13be5be120ea94cd65
static/js/modern-modals.js	cd03bbe96f497aef14e1b58fb26a4484399f42cc92edef8d8e58b88dd786126f	5f3491ba1e6446258e4bfde994a6a756bef255d2d30e452290d79f12c3ae1503	5f3491ba1e6446258e4bfde994a6a756bef255d2d30e452290d79f12c3ae1503
static/js/modern-modals/modules/00-styles-utilities-static-modal.js	3f83dc28aa62ad3278ab814d3645cf115ad2395302d826e5e7653b105d07e7a7	dccde74b63cd24ec621f7e93cc9285bc74bc9ed1902981e7ca038f320bd37e64	dccde74b63cd24ec621f7e93cc9285bc74bc9ed1902981e7ca038f320bd37e64
static/js/notifications.js	dc2a8e25856e4933708d26cb47699b38789cc1053e2f9b47709116efa41476e7	1acb536514f2ac0a61340c6108c186e45ad4206abf70c3475e04cec88d06be4c	1acb536514f2ac0a61340c6108c186e45ad4206abf70c3475e04cec88d06be4c
static/js/performance-optimizer.js	33f21764b9cc492be9c1aa750ba9de8b7f5d0d06e72840227c4116f2498b60ce	d3e519d1150bba5419419abc3e40bd590475ee7fd865006f5b81bd17116626e1	d3e519d1150bba5419419abc3e40bd590475ee7fd865006f5b81bd17116626e1
static/js/performance-optimizer/modules/10-performance-optimizer-bootstrap-export.js	a0b7fe63065a4323326cac90fbefc4c47df328f8fb596c653531e90e16302d7e	31b35aa27f0f25ed606caa966547fb21e6c90692b3e0d8bf5511098003fd861b	31b35aa27f0f25ed606caa966547fb21e6c90692b3e0d8bf5511098003fd861b
static/js/profile-modal.js	0a0538c58b1b9493da8d4fe7fd8afe9d646b3567cde3fa7177974c09b2c0b5fa	dc0d47bb1e01d129c01bba24039f897bb2f4d00fb5d8943500525f33f9d3fe52	dc0d47bb1e01d129c01bba24039f897bb2f4d00fb5d8943500525f33f9d3fe52
static/js/profile-modal/modules/20-avatar-sync-and-bootstrap.js	51ad1d9c9d5fce287efee7f4850157802ad8e327710cae3b452804fae032e1f0	7054fe4418e89610f5574ff590d2d7ae53810731c8482de16f05362611704ec0	7054fe4418e89610f5574ff590d2d7ae53810731c8482de16f05362611704ec0
static/js/seb-auth-diagnostic.js	bbe67350174094421e845d4161c4d5db2407e49f3506013649f31cd27a18f5fb	aaf9c842766e9c59414daa0bb85c7d19bac0a67870bb3c3c5d4eeb13cc094b8a	aaf9c842766e9c59414daa0bb85c7d19bac0a67870bb3c3c5d4eeb13cc094b8a
static/js/seb-builder.js	df0286c38d96d1c7d4c1b448fdc7716386b6fd832ab61d5983c510188bffc77d	30cc7bad1156e9c03dc1abafbc2b398a6954cdd3f91122192264a8e58a0216d2	30cc7bad1156e9c03dc1abafbc2b398a6954cdd3f91122192264a8e58a0216d2
static/js/sidebar-loader.js	d06abcb89957b464fdca5787773557a1ef7c1536e9abdae4bf48ae84fa130821	5dbead9f378851fb1afd8c436ae08cc78f7ff7bbe4ed24e7fe69fb68a34c3eb2	5dbead9f378851fb1afd8c436ae08cc78f7ff7bbe4ed24e7fe69fb68a34c3eb2
static/js/sidebar-loader/modules/10-sidebar-loader-bootstrap.js	0091619d286dadfe0de6e0631b4cd92d35d9a529a5d4058860edb17e19bc952f	4c0506fa5af008edad18f6e5fc76f4ffa42e5c31ba83b5d760d00c7fef770922	4c0506fa5af008edad18f6e5fc76f4ffa42e5c31ba83b5d760d00c7fef770922
static/js/toast.js	61b781ae0d6dc198fe7006efee987a7634f7af55b5fa6398e25ef8372e418a66	f46a2787c1bb8a6cf7b313837c181bec711da5603b8179173005f5f88bd2d962	f46a2787c1bb8a6cf7b313837c181bec711da5603b8179173005f5f88bd2d962
static/js/toast/modules/00-toast-core.js	fe20aa6d3942aced779986835e8611591853a75d3c5e283e318af4fced728bfe	af46cd61884d45b9b8c587a65760304fd2a9aede4366468246b20adda0b49440	af46cd61884d45b9b8c587a65760304fd2a9aede4366468246b20adda0b49440
static/js/universal-modal-fix.js	050545e55c0e338d1759a944213195bbe8f8f58912a1f4ddf123b06fafb23681	2e2e84b933ca7e7cd19f5c3b541209a07cbbb03f06ba4303d3b408a42c4aaa56	2e2e84b933ca7e7cd19f5c3b541209a07cbbb03f06ba4303d3b408a42c4aaa56
static/js/universal-modal-fix/modules/00-universal-modal-fix-core.js	95264e0e5ba000091684317331164c9ee003cf5e2f712be1984cc1dd88843f45	114dc7106ef34a158de7e6e0d432b10ba7e594029a22efba7e4f3b7dc7ec38e3	114dc7106ef34a158de7e6e0d432b10ba7e594029a22efba7e4f3b7dc7ec38e3
static/js/user-management.js	53a2c8b336d7dd6fa01859eaea03eb18631d7608354dfc8219137c12ecaeed00	1bd5adca1eaf905c70c0ee61d33f6c0819db8b8360da0068bb2bf9917b64b27c	1bd5adca1eaf905c70c0ee61d33f6c0819db8b8360da0068bb2bf9917b64b27c
static/js/user-management/modules/00-user-management-core.js	c25b76406c4d8872f23cc78a902f5ecaf919d543c717816ecc64557cd08520fc	617fd6c2c20aa692721ce22ef4d8a4fb01a879c5439823c52a3be2806f0237b8	617fd6c2c20aa692721ce22ef4d8a4fb01a879c5439823c52a3be2806f0237b8
```

All post-copy checksums matched source checksums.

## 9. Compile and safety checks on VPS

`python -m py_compile` initially failed because the container could not write to `__pycache__`:

```text
Permission denied: /app/app/api/__pycache__/auth.cpython-311.pyc...
```

No app-plane restart had happened at that point. The validation was continued with in-memory syntax compilation that does not write `.pyc` files:

```text
syntax_compile_in_memory=OK
```

Static safety grep on live source passed:

```text
const includeDataServices = false: present
runRestartRequest(true): present
Restart DB/Redis/PgBouncer: present
Service app-plane di-restart: present
unsafe include_data_services: restartBackendVisual.fullRestartAvailable: absent
```

## 10. Restart scope

Restarted app-plane only, sequentially:

```text
api
api2
api3
api4
api5
api6
api7
api8
api_admin
api_admin2
```

Each service returned healthy after restart.

## 11. Services not restarted

Not restarted:

```text
db
pgbouncer
redis
nginx
celery_worker
celery_beat
prometheus
grafana
```

Data-service StartedAt before and after app-plane restart was unchanged:

```text
ujian_online-db-1        2026-06-06T04:27:40.732547151Z
ujian_online-pgbouncer-1 2026-06-06T04:27:38.009982103Z
ujian_online-redis-1     2026-06-06T04:27:39.367061352Z
```

## 12. Immediate post-deploy validation

Health/static:

```text
health local: 200
health public: 200
/static/js/admin/monitoring.js: 200 text/javascript, 197689 bytes
/static/js/api.js: 200 text/javascript, 62522 bytes
served static safety: OK
```

Effective env after restart:

```json
{"ADMIN_MONITORING_DETAIL_LEVEL":"summary","ANSWER_QUEUE_ENABLED":false,"ANSWER_QUEUE_PERCENTAGE":0,"ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED":false,"ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE":0,"ANSWER_WRITE_MODE":"direct","EXAM_PEAK_MODE":true,"MOBILE_APK_PRIMARY":true,"VIOLATION_ASYNC_ENABLED":true}
```

DB/Redis gates after restart:

```text
active sessions: 0
running exam windows: 0
final-submit/drain: 0
DB long active queries >60s: 0
DB idle-in-transaction: 0
Redis rejected_connections: 0
Redis evicted_keys: 0
```

Backend functional checks used a short-lived in-memory admin token generated inside the API container. The token was not printed or stored.

```json
{"/api/grading/stats":200,"/api/monitoring/system/ops-summary":200,"/api/stats/dashboard":200,"/api/users/1":200,"/api/users/advanced-search?per_page=1":200,"/health":200}
```

## 13. Restart-safe UI validation

Validated in served `static/js/admin/monitoring.js`:

```text
dry-run/preflight before restart: YES
include_data_services=false default: YES
DB/Redis/PgBouncer restart displayed as TIDAK by default: YES
success text says app-plane services restarted: YES
unsafe include_data_services coupling to fullRestartAvailable: ABSENT
```

## 14. Observation window result

Observation ran for more than 30 minutes after app-plane restart.

Final observation timestamp:

```text
2026-06-06T21:12:48Z
```

Health/static after observation:

```text
health local: 200
health public: 200
/static/js/admin/monitoring.js: 200 text/javascript, 197689 bytes
/static/js/api.js: 200 text/javascript, 62522 bytes
```

App-plane health after observation:

```text
api through api8: healthy
api_admin and api_admin2: healthy
```

Data services after observation:

```text
db: healthy, StartedAt unchanged
pgbouncer: healthy, StartedAt unchanged
redis: healthy, StartedAt unchanged
```

Resources after observation:

```text
disk /: 52% used
memory available: ~12029 MB
swap used: 3 MB
```

DB/Redis gates after observation:

```json
{"active_sessions":0,"final_submit_or_drain":0,"idle_in_transaction":0,"long_active_queries":0,"redis":{"evicted_keys":0,"rejected_connections":0},"running_exam_windows":0}
```

Functional checks after observation:

```json
{"/api/grading/stats":200,"/api/monitoring/system/ops-summary":200,"/api/stats/dashboard":200,"/api/users/1":200,"/api/users/advanced-search?per_page=1":200,"/health":200}
```

Log summary over the observation window:

```json
{"asyncpg_internal":0,"http_500":0,"http_503_409":0,"import_error":0,"queue_hybrid":0,"shadow_activation":0,"traceback":0}
```

Nginx summary over the observation window:

```json
{"499":0,"500":0,"static_404":0,"static_5xx":0}
```

## 15. Forbidden artifact check

No forbidden deployment artifacts were copied:

```text
APK/AAB: not deployed
keystore/JKS/key.properties/local.properties: not deployed
.env/.env.*: not deployed
DB dump/backup/sql/sqlite/db: not deployed
session CSV/summary JSON: not deployed
raw token/secret files: not deployed
```

## 16. Production action performed

Performed:

```text
source file copy by manifest
backup/checksum before and after copy
app-plane-only rolling restart
post-deploy validation
30+ minute observation
```

Not performed:

```text
no .env change
no docker-compose.production.yml change
no migration/schema change
no production load-test
no APK change
no DB restart
no PgBouncer restart
no Redis restart
no Nginx restart
no Celery restart
no Phase 6 shadow enablement
no queue/hybrid enablement
```

## 17. Rollback reference

Rollback source:

```text
/root/ujian_online_backups/phase-5.4-auth-frontend-20260606T203324Z
```

Rollback steps if needed:

```text
1. confirm active sessions/running exam/final-submit drain are all zero
2. restore files from the backup directory
3. app-plane-only rolling restart
4. verify health and direct safe-mode env
5. do not restart DB/Redis/PgBouncer unless separately approved
```

## 18. Final decision

```text
Phase 5.4 deploy: PASS
Backend auth eager-load fix live: YES
Frontend bundle source sync live: YES
Restart-safe UI live: YES
Phase 6 shadow remains OFF: YES
Queue/hybrid remains OFF: YES
Safe to continue direct production: YES
```
