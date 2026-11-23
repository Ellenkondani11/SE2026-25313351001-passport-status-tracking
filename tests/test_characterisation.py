from datetime import timedelta
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core.models import (
    Applicant, Application, AuditLog, LoginAttempt, LookupAttempt,
    Notification, Office, OfficerNote, SmsTemplate, Stage, StageChange,
    hash_sensitive,
)
from core.services import AfricasTalkingGateway, notify, render_message, retry_notification
from core.utils import mask_national_id, mask_phone, normalize_phone, tracking_code_for
from core.views import _bound_ussd, _csv_safe


class PastnsCharacterisationTests(TestCase):
    def setUp(self):
        self.office = Office.objects.create(
            code="MGC",
            name="Mangochi Immigration Office",
            district="Mangochi",
            phone="+265 1 594 300",
            address="Mangochi Immigration Office",
            collection_hours="Monday–Friday, 08:00–16:00",
            collection_hours_ny="Lolemba–Lachisanu, 08:00–16:00",
        )
        stage_rows = [
            ("received", 10, "Received", "Application received.", "Pempho lalandiridwa.", "grey", True, False),
            ("under_review", 20, "Under review", "Under review.", "Likuwunikidwa.", "blue", True, False),
            ("approved", 30, "Approved", "Approved.", "Lavomerezedwa.", "green", True, False),
            ("printed", 40, "Printed", "Printed.", "Lasindikizidwa.", "teal", True, False),
            ("ready", 50, "Ready for collection", "Ready.", "Lakonzeka.", "amber", True, False),
            ("collected", 60, "Collected", "Collected.", "Latengedwa.", "dark", False, True),
            ("on_hold", 70, "On hold", "On hold.", "Layimitsidwa.", "red", True, False),
            ("rejected", 80, "Rejected", "Rejected.", "Lakanidwa.", "red", True, True),
        ]
        self.stages = {}
        for key, order, name, en, ny, colour, notify_flag, terminal in stage_rows:
            self.stages[key] = Stage.objects.create(
                key=key, order=order, name=name,
                applicant_text_en=en, applicant_text_ny=ny,
                colour=colour, notify=notify_flag, is_terminal=terminal,
            )

        self.officer = User.objects.create_user("officer", password="long-enough-test-pass")
        self.officer.profile.office = self.office
        self.officer.profile.role = "officer"
        self.officer.profile.save()
        self.officer_token = Token.objects.create(user=self.officer)

        self.supervisor = User.objects.create_user("supervisor", password="long-enough-test-pass")
        self.supervisor.profile.office = self.office
        self.supervisor.profile.role = "supervisor"
        self.supervisor.profile.save()
        self.supervisor_token = Token.objects.create(user=self.supervisor)

        self.admin_user = User.objects.create_user("adminuser", password="long-enough-test-pass")
        self.admin_user.profile.office = self.office
        self.admin_user.profile.role = "admin"
        self.admin_user.profile.save()

        self.applicant = Applicant.objects.create(
            national_id="1234567890123",
            first_name="Chisomo",
            surname="Banda",
            phone="+265991234567",
            language="ny",
        )
        self.year = timezone.localdate().year
        self.application = Application.objects.create(
            tracking_code=f"MW-MGC-{self.year}-00001",
            applicant=self.applicant,
            office=self.office,
            current_stage=self.stages["received"],
        )
        StageChange.objects.create(
            application=self.application,
            from_stage=None,
            to_stage=self.stages["received"],
            by_user=self.officer,
            reason="Registered",
        )

    def test_phone_normalization_masking_and_national_id_masking(self):
        self.assertEqual(normalize_phone("0991234567"), "+265991234567")
        self.assertEqual(normalize_phone("265881234567"), "+265881234567")
        self.assertEqual(mask_phone("+265991234567"), "+265 99* *** 567")
        self.assertEqual(mask_phone("12345"), "••••")
        self.assertEqual(mask_national_id("1234567890123"), "••••0123")
        self.assertEqual(mask_national_id("1234"), "••••")
        self.assertEqual(self.applicant.masked_national_id, "••••0123")
        self.assertEqual(self.applicant.masked_phone, "+265 99* *** 567")

    def test_tracking_code_for_increments_sequence_per_office_and_year(self):
        next_code = tracking_code_for(self.office)
        self.assertEqual(next_code, f"MW-MGC-{self.year}-00002")

    def test_audit_log_is_immutable_on_save_and_delete(self):
        entry = AuditLog.objects.create(user=self.officer, action="test_event", details={"k": "v"})
        entry.action = "tampered"
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()

    def test_hash_sensitive_normalizes_whitespace_and_case(self):
        digest_a = hash_sensitive("  ABC12345 ")
        digest_b = hash_sensitive("abc12345")
        self.assertEqual(digest_a, digest_b)
        self.assertEqual(len(digest_a), 64)

    def test_public_status_requires_verified_session_and_rejects_direct_get(self):
        denied = self.client.get(f"/status/?code={self.application.tracking_code}")
        self.assertEqual(denied.status_code, 403)
        self.assertContains(denied, "We could not match those details", status_code=403)

    def test_public_lookup_accepts_local_phone_number(self):
        response = self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": "0991234567"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.application.tracking_code, response["Location"])
        self.assertTrue(LookupAttempt.objects.filter(success=True).exists())

    def test_public_lookup_rate_limit_blocks_sixth_attempt(self):
        for _ in range(5):
            self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": "wrong-code"})
        blocked = self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": self.application.tracking_code})
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "We could not match those details")
        self.assertEqual(LookupAttempt.objects.count(), 6)

    def test_language_switch_sets_cookie_and_blocks_external_redirect(self):
        safe = self.client.get("/language/?lang=ny&next=/ussd-demo/")
        self.assertEqual(safe.status_code, 302)
        self.assertEqual(safe["Location"], "/ussd-demo/")
        self.assertEqual(safe.cookies["django_language"].value, "ny")

        unsafe = self.client.get("/language/?lang=en&next=https://evil.example.com/phish")
        self.assertEqual(unsafe.status_code, 302)
        self.assertEqual(unsafe["Location"], "/")

    def test_officer_login_lockout_after_five_failures(self):
        for _ in range(5):
            self.client.post("/officer/login/", {"username": "officer", "password": "wrong-password"})
        locked = self.client.post("/officer/login/", {"username": "officer", "password": "long-enough-test-pass"})
        self.assertEqual(locked.status_code, 200)
        self.assertContains(locked, "Sign-in is temporarily locked")
        self.assertTrue(AuditLog.objects.filter(action="login_locked").exists())

    def test_role_based_access_control_on_officer_pages(self):
        self.assertEqual(self.client.get("/officer/").status_code, 302)

        self.client.force_login(self.officer)
        self.assertEqual(self.client.get("/officer/").status_code, 200)
        self.assertEqual(self.client.get("/officer/reports/").status_code, 403)
        self.assertEqual(self.client.get("/officer/admin/").status_code, 403)

        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get("/officer/reports/").status_code, 200)
        self.assertEqual(self.client.get("/officer/admin/").status_code, 403)

        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get("/officer/admin/").status_code, 200)

    def test_register_application_creates_record_stage_and_notification(self):
        self.client.force_login(self.officer)
        response = self.client.post("/officer/applications/new/", {
            "national_id": "9876543210987",
            "first_name": "Tadala",
            "surname": "Phiri",
            "phone": "0881234567",
            "email": "",
            "language": "en",
            "application_type": "renewal",
        })
        self.assertEqual(response.status_code, 200)
        created_app = Application.objects.get(applicant__national_id="9876543210987")
        self.assertEqual(created_app.applicant.phone, "+265881234567")
        self.assertEqual(created_app.current_stage.key, "received")
        self.assertTrue(Notification.objects.filter(application=created_app).exists())
        self.assertTrue(AuditLog.objects.filter(action="application_registered", object_id=str(created_app.pk)).exists())

    def test_hold_and_resume_preserve_previous_stage(self):
        self.client.force_login(self.officer)
        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {"action": "advance"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_stage.key, "under_review")

        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {"action": "hold", "reason": "Missing photo"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "on_hold")
        self.assertEqual(self.application.current_stage.key, "on_hold")
        self.assertEqual(self.application.previous_stage.key, "under_review")

        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {"action": "resume"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, "active")
        self.assertEqual(self.application.current_stage.key, "under_review")
        self.assertIsNone(self.application.previous_stage)

    def test_officer_cannot_skip_or_reject_but_supervisor_can(self):
        self.client.force_login(self.officer)
        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {
            "action": "move", "target_stage": "ready", "reason": "Shortcut",
        })
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_stage.key, "received")

        self.client.force_login(self.supervisor)
        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {
            "action": "move", "target_stage": "approved", "reason": "Supervisor override",
        })
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_stage.key, "approved")

    def test_contact_correction_requires_id_check_and_audits_masked_numbers(self):
        self.client.force_login(self.officer)
        self.client.post(f"/officer/applications/{self.application.tracking_code}/", {
            "action": "correct_contact",
            "phone": "0887654321",
            "email": "chisomo@example.mw",
            "reason": "Changed SIM",
            "id_checked": "on",
        })
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.phone, "+265887654321")
        log = AuditLog.objects.filter(action="contact_corrected", object_id=str(self.application.pk)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details["new_phone"], "+265 88* *** 321")

    def test_bulk_update_only_advances_eligible_stage_and_csv_escapes_formulas(self):
        formula_applicant = Applicant.objects.create(
            national_id="5555555555555", first_name="=CMD()", surname="Tester", phone="+265991112233", language="en",
        )
        approved_app = Application.objects.create(
            tracking_code=f"MW-MGC-{self.year}-00002",
            applicant=formula_applicant,
            office=self.office,
            current_stage=self.stages["approved"],
        )
        self.client.force_login(self.officer)
        self.client.post("/officer/applications/bulk/", {
            "action": "printed",
            "selected": [self.application.tracking_code, approved_app.tracking_code],
        })
        self.application.refresh_from_db()
        approved_app.refresh_from_db()
        self.assertEqual(self.application.current_stage.key, "received")
        self.assertEqual(approved_app.current_stage.key, "printed")

        self.assertEqual(_csv_safe("=SUM(A1)"), "'=SUM(A1)")
        csv_resp = self.client.get("/officer/?export=csv")
        self.assertEqual(csv_resp.status_code, 200)
        csv_body = csv_resp.content.decode("utf-8")
        self.assertIn("'=CMD() Tester", csv_body)
        self.assertNotIn("5555555555555", csv_body)

    def test_render_message_uses_active_template_and_email_channel(self):
        SmsTemplate.objects.create(
            key="received",
            name="Received",
            body_en="EN {code} at {office}",
            body_ny="NY {code} ku {office}",
            is_active=True,
        )
        self.assertIn("NY MW-MGC-", render_message(self.application, "received"))
        self.assertIsNone(notify(self.application, "received", channel="email"))

        self.applicant.email = "chisomo@example.mw"
        self.applicant.save()
        email_row = notify(self.application, "received", channel="email", actor=self.officer)
        self.assertEqual(email_row.status, "sent")
        self.assertEqual(len(mail.outbox), 1)

        failed = Notification.objects.create(
            application=self.application, channel="sms", to=self.applicant.phone,
            template_key="received", body="Test", status="failed", error="Network error",
        )
        retry_notification(failed, actor=self.officer)
        failed.refresh_from_db()
        self.assertEqual(failed.status, "sent")
        self.assertEqual(failed.error, "")
        self.assertEqual(AfricasTalkingGateway().send(failed).status, "failed")

    @override_settings(SMS_CALLBACK_TOKEN="callback-secret")
    def test_api_office_scoping_and_sms_delivery_callback(self):
        other_office = Office.objects.create(code="LLW", name="Lilongwe", district="Lilongwe")
        llw_user = User.objects.create_user("llw_officer", password="long-enough-test-pass")
        llw_user.profile.office = other_office
        llw_user.profile.role = "officer"
        llw_user.profile.save()
        llw_token = Token.objects.create(user=llw_user)

        self.assertEqual(
            self.client.get(f"/api/applications/{self.application.tracking_code}/", HTTP_AUTHORIZATION=f"Token {llw_token.key}").status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                f"/api/applications/{self.application.tracking_code}/stage/",
                {"stage": "under_review"},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Token {llw_token.key}",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/applications/{self.application.tracking_code}/stage/",
                {"stage": "rejected", "reason": "No"},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Token {self.officer_token.key}",
            ).status_code,
            403,
        )

        notif = Notification.objects.create(
            application=self.application, channel="sms", to=self.applicant.phone,
            template_key="received", body="Msg", status="sent", provider_ref="at-msg-1",
        )
        unauth = self.client.post("/api/sms/delivery/", {"provider_ref": "at-msg-1", "status": "Success"}, content_type="application/json")
        self.assertEqual(unauth.status_code, 403)

        ok = self.client.post(
            "/api/sms/delivery/",
            {"provider_ref": "at-msg-1", "status": "Delivered"},
            content_type="application/json",
            HTTP_X_CALLBACK_TOKEN="callback-secret",
        )
        self.assertEqual(ok.status_code, 200)
        notif.refresh_from_db()
        self.assertEqual(notif.status, "delivered")

    def test_ussd_phone_shortcut_invalid_option_and_truncation(self):
        matched = self.client.post("/api/ussd/", {
            "sessionId": "ussd-phone-0",
            "phoneNumber": "0991234567",
            "text": f"1*{self.applicant.national_id}*0",
        })
        self.assertTrue(matched.content.decode().startswith(f"END {self.application.tracking_code}"))

        invalid = self.client.post("/api/ussd/", {"sessionId": "ussd-bad", "phoneNumber": "+265991234567", "text": "9"})
        self.assertTrue(invalid.content.decode().startswith("END Invalid option"))
        self.assertEqual(self.client.get("/api/ussd/").status_code, 405)

        long_reply = _bound_ussd("END " + ("word " * 40))
        self.assertLessEqual(len(long_reply), 160)
        self.assertTrue(long_reply.endswith("…"))
