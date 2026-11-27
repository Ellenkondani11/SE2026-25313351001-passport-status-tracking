from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.audit_chain import verify_audit_chain
from core.models import Applicant, Application, AuditLog, LookupAttempt, LookupOtp, hash_sensitive


class SignatureChallengeTests(TestCase):
    def setUp(self):
        from core.models import Office, Stage

        self.office = Office.objects.create(code="MGC", name="Mangochi", district="Mangochi")
        self.stage = Stage.objects.create(
            key="received", order=10, name="Received",
            applicant_text_en="Received.", applicant_text_ny="Lalandiridwa.",
        )
        self.year = timezone.localdate().year
        self.applicant = Applicant.objects.create(
            national_id="1234567890123", first_name="Chisomo", surname="Banda",
            phone="+265991234567", language="ny", date_of_birth="1995-04-12",
        )
        self.application = Application.objects.create(
            tracking_code=f"MW-MGC-{self.year}-00001", applicant=self.applicant,
            office=self.office, current_stage=self.stage,
        )
        self.officer = User.objects.create_user("officer", password="long-enough-test-pass")
        self.officer.profile.office = self.office
        self.officer.profile.role = "officer"
        self.officer.profile.save()

    def test_tracking_code_and_dob_lookup_succeeds(self):
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "date_of_birth": "1995-04-12"})  # noqa: E501
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.application.tracking_code, response["Location"])

    def test_tracking_code_and_dob_lookup_wrong_dob_fails(self):
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "date_of_birth": "1990-01-01"})  # noqa: E501
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We could not match those details")

    def test_missing_dob_on_applicant_fails(self):
        self.applicant.date_of_birth = None
        self.applicant.save()
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "date_of_birth": "1995-04-12"})  # noqa: E501
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We could not match those details")

    def test_otp_request_creates_hashed_lookup_otp_and_dispatches(self):
        with override_settings(PASTNS_SMS_GATEWAY="console"):
            response = self.client.post("/lookup/otp/", {"tracking_code": self.application.tracking_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LookupOtp.objects.count(), 1)
        created_otp = LookupOtp.objects.first()
        self.assertEqual(len(created_otp.code_hash), 64)
        self.assertIsNotNone(created_otp.expires_at)
        self.assertTrue(created_otp.expires_at > timezone.now())

    def test_otp_submission_succeeds_and_marks_used(self):
        otp_code = "123456"
        LookupOtp.objects.create(
            application=self.application, code_hash=hash_sensitive(otp_code),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "otp_code": otp_code})
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.application.tracking_code, response["Location"])
        self.assertIsNotNone(LookupOtp.objects.first().used_at)

    def test_otp_reuse_fails(self):
        otp_code = "123456"
        LookupOtp.objects.create(
            application=self.application, code_hash=hash_sensitive(otp_code),
            expires_at=timezone.now() + timedelta(minutes=10), used_at=timezone.now(),
        )
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "otp_code": otp_code})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We could not match those details")

    def test_expired_otp_fails(self):
        otp_code = "123456"
        LookupOtp.objects.create(
            application=self.application, code_hash=hash_sensitive(otp_code),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.post("/", {"tracking_code": self.application.tracking_code, "otp_code": otp_code})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We could not match those details")

    def test_ip_rate_limit_across_different_identifiers(self):
        codes = [f"MW-MGC-{self.year}-{i:05d}" for i in range(2, 8)]
        for code in codes[:5]:
            self.client.post("/", {"tracking_code": code, "date_of_birth": "1990-01-01"})
        blocked = self.client.post("/", {"tracking_code": self.application.tracking_code, "date_of_birth": "1995-04-12"})  # noqa: E501
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "We could not match those details")
        self.assertEqual(LookupAttempt.objects.count(), 6)

    def test_verified_status_session_expires_after_15_minutes(self):
        self.client.post("/", {"tracking_code": self.application.tracking_code, "date_of_birth": "1995-04-12"})
        expired_at = timezone.now() - timedelta(minutes=16)
        session = self.client.session
        session["verified_status_at"] = expired_at.isoformat()
        session.save()
        response = self.client.get(f"/status/?code={self.application.tracking_code}")
        self.assertEqual(response.status_code, 403)

    def test_audit_chain_intact(self):
        AuditLog.objects.create(action="first", details={"k": 1})
        AuditLog.objects.create(action="second", details={"k": 2})
        ok, count, tampered = verify_audit_chain()
        self.assertTrue(ok)
        self.assertEqual(tampered, [])
        self.assertGreaterEqual(count, 2)

    def test_audit_chain_detects_tampering(self):
        first = AuditLog.objects.create(action="first", details={"k": 1})
        AuditLog.objects.create(action="second", details={"k": 2})
        AuditLog.objects.filter(pk=first.pk).update(action="tampered")
        ok, count, tampered = verify_audit_chain()
        self.assertFalse(ok)
        self.assertIn(first.pk, tampered)

    def test_verify_audit_command_and_badge(self):
        AuditLog.objects.create(action="first", details={"k": 1})
        call_command("verify_audit")
        first = AuditLog.objects.first()
        AuditLog.objects.filter(pk=first.pk).update(action="tampered")
        with self.assertRaises(CommandError):
            call_command("verify_audit")
        self.client.force_login(self.officer)
        response = self.client.get("/officer/audit/")
        self.assertContains(response, "Tamper alert")


class BackwardCompatTests(TestCase):
    def setUp(self):
        from core.models import Office, Stage

        self.office = Office.objects.create(code="MGC", name="Mangochi", district="Mangochi")
        self.stage = Stage.objects.create(key="received", order=10, name="Received", applicant_text_en="Received.", applicant_text_ny="Lalandiridwa.")  # noqa: E501
        self.year = timezone.localdate().year
        self.applicant = Applicant.objects.create(
            national_id="1234567890123", first_name="Chisomo", surname="Banda",
            phone="+265991234567", language="ny",
        )
        self.application = Application.objects.create(
            tracking_code=f"MW-MGC-{self.year}-00001", applicant=self.applicant,
            office=self.office, current_stage=self.stage,
        )

    def test_existing_national_id_lookup_still_works(self):
        response = self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": "0991234567"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.application.tracking_code, response["Location"])
