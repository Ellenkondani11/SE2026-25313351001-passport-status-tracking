# Requirements Traceability Matrix — PassTrack (PASTNS)
- **Token:** `EK01-HAZY-VM26` | **Student:** `25313351001` | **Baseline:** `v0.8`

| Req ID | Tag | Design / Code Module | Automated Test(s) |
|---|---|---|---|
| FR-01 | Built | `core/views.py:public_home`, `public_status` | `test_workflows.py::test_public_lookup_requires_both_factors_and_masks_phone`, `test_characterisation.py::test_public_lookup_accepts_local_phone_number` |
| FR-02 | Built | `core/models.py:Applicant`, `core/utils.py:mask_phone`, `mask_national_id` | `test_characterisation.py::test_phone_normalization_masking_and_national_id_masking` |
| FR-03 | Built | `core/middleware.py:QueryLanguageMiddleware`, `core/views.py:language_switch` | `test_characterisation.py::test_language_switch_sets_cookie_and_blocks_external_redirect` |
| FR-04 | Built | `core/views.py:ussd_endpoint`, `_ussd_collection_response`, `_bound_ussd` | `test_workflows.py::test_ussd_flow_uses_id_and_tracking_code`, `test_chichewa_ussd_collection_keeps_full_hours_under_screen_limit`, `test_characterisation.py::test_ussd_phone_shortcut_invalid_option_and_truncation` |
| FR-05 | Built | `core/views.py:register_application`, `core/utils.py:tracking_code_for` | `test_characterisation.py::test_register_application_creates_record_stage_and_notification`, `test_tracking_code_for_increments_sequence_per_office_and_year` |
| FR-06 | Built | `core/views.py:application_detail`, `_change_stage` | `test_workflows.py::test_authenticated_stage_update_sends_sms_and_audits` |
| FR-07 | Built | `core/views.py:application_detail`, `core/api.py:ApplicationStageAPIView` | `test_characterisation.py::test_officer_cannot_skip_or_reject_but_supervisor_can` |
| FR-08 | Partial | `core/views.py:application_detail` (`hold`/`resume`) | `test_characterisation.py::test_hold_and_resume_preserve_previous_stage` (+ TDD test in `v0.9`) |
| FR-09 | Built | `core/views.py:bulk_update` | `test_characterisation.py::test_bulk_update_only_advances_eligible_stage_and_csv_escapes_formulas` |
| FR-10 | Built | `core/views.py:_csv_safe`, `_applications_csv` | `test_characterisation.py::test_bulk_update_only_advances_eligible_stage_and_csv_escapes_formulas` |
| FR-11 | Built | `core/views.py:application_detail`, `core/forms.py:ContactCorrectionForm` | `test_characterisation.py::test_contact_correction_requires_id_check_and_audits_masked_numbers` |
| FR-12 | Built | `core/views.py:officer_login`, `config/settings.py` | `test_characterisation.py::test_officer_login_lockout_after_five_failures` |
| FR-13 | Built | `core/views.py:role_required`, `core/api.py:ApplicationDetailAPIView` | `test_characterisation.py::test_role_based_access_control_on_officer_pages`, `test_api_office_scoping_and_sms_delivery_callback` |
| FR-14 | Built | `core/views.py:admin_console` | Covered in TDD/admin extension tests (`v0.9`) |
| FR-15 | Built | `core/views.py:reports`, `_stage_metrics`, `_monthly_counts` | `test_characterisation.py::test_role_based_access_control_on_officer_pages` |
| FR-16 | Built | `core/api.py`, `config/urls.py` | `test_workflows.py::test_authenticated_api_is_office_scoped`, `test_api_create_stage_and_openapi_schema` |
| FR-17 | Partial | `core/services.py`, `core/views.py` (Observer + Strategy channels) | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-18 | New | `core/models.py:Notification`, `core/services.py`, `send_pending.py` | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-19 | Partial | `core/services.py:notify`, `core/api.py:SmsDeliveryAPIView` | `test_characterisation.py::test_api_office_scoping_and_sms_delivery_callback` + TDD deduplication tests (`v0.9`) |
| FR-20 | New | `core/models.py:Applicant.date_of_birth`, `LookupOtp`, `core/views.py` | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-21 | Partial | `core/views.py:public_home`, `public_status` | `test_characterisation.py::test_public_lookup_rate_limit_blocks_sixth_attempt` + IP/TTL TDD tests (`v0.9`) |
| FR-22 | Partial | `core/models.py:AuditLog` (`prev_hash`, `entry_hash`), `core/utils.py:audit` | `test_characterisation.py::test_audit_log_is_immutable_on_save_and_delete` + hash-chain TDD tests (`v0.9`) |
| FR-23 | New | `core/events.py` / `core/channels.py` (Observer, Strategy, Template Method) | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-24 | New | `core/views.py` / `core/api.py` (Audit verify & Drop 1–3 seam) | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-25 | Partial | `core/models.py:Stage`, `core/models.py:SmsTemplate`, `core/services.py:render_message` | Planned TDD tests in `tests/test_signature_challenge.py` (`v0.9`) |
| FR-26 | Built | `core/services.py`, `core/management/commands/send_pending.py`, `core/views.py:outbox` | `test_characterisation.py::test_render_message_uses_active_template_and_email_channel` |
| FR-27 | Built | `core/views.py:ussd_endpoint`, `_bound_ussd`, `_ussd_collection_response` | `test_characterisation.py::test_ussd_phone_shortcut_invalid_option_and_truncation` |
| FR-28 | Built | `core/views.py:admin_console`, `core/models.py:AuditLog` | Covered in TDD/admin extension tests (`v0.9`) |
