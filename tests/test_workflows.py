from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from core.models import Applicant, Application, AuditLog, Notification, Office, Stage, StageChange


class PastnsWorkflowTests(TestCase):
    def setUp(self):
        self.office = Office.objects.create(code="MGC", name="Mangochi Immigration Office", district="Mangochi", phone="+265 1 594 300", address="Mangochi Immigration Office", collection_hours="Monday–Friday 08:00–16:00")  # noqa: E501
        stage_rows = [
            ("received", 10, "Received", "Application received.", "Pempho lalandiridwa.", "grey", True),
            ("under_review", 20, "Under review", "Under review.", "Likuwunikidwa.", "blue", True),
            ("approved", 30, "Approved", "Approved.", "Lavomerezedwa.", "green", True),
            ("printed", 40, "Printed", "Printed.", "Lasindikizidwa.", "teal", True),
            ("ready", 50, "Ready for collection", "Ready.", "Lakonzeka.", "amber", True),
            ("collected", 60, "Collected", "Collected.", "Latengedwa.", "dark", False),
            ("on_hold", 70, "On hold", "On hold.", "Layimitsidwa.", "red", True),
            ("rejected", 80, "Rejected", "Rejected.", "Lakanidwa.", "red", True),
        ]
        self.stages = {}
        for key, order, name, en, ny, colour, notify in stage_rows:
            self.stages[key] = Stage.objects.create(key=key, order=order, name=name, applicant_text_en=en, applicant_text_ny=ny, colour=colour, notify=notify)  # noqa: E501
        user = User.objects.create_user("officer", password="long-enough-test-pass")
        profile = user.profile
        profile.office = self.office
        profile.role = "officer"
        profile.save()
        self.user = user
        self.token = Token.objects.create(user=user)
        self.applicant = Applicant.objects.create(national_id="1234567890123", first_name="Chisomo", surname="Banda", phone="+265991234567", language="ny")  # noqa: E501
        self.application = Application.objects.create(tracking_code="MW-MGC-2026-00001", applicant=self.applicant, office=self.office, current_stage=self.stages["received"])  # noqa: E501
        StageChange.objects.create(application=self.application, from_stage=None, to_stage=self.stages["received"], by_user=user, reason="Registered")  # noqa: E501

    def test_public_lookup_requires_both_factors_and_masks_phone(self):
        response = self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": self.application.tracking_code})  # noqa: E501
        self.assertEqual(response.status_code, 302)
        status_response = self.client.get(response["Location"])
        self.assertEqual(status_response.status_code, 200)
        self.assertContains(status_response, "+265 99* *** 567")
        self.client.get("/", follow=True)
        bad = self.client.post("/", {"national_id": self.applicant.national_id, "phone_or_code": "+265991234568"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "We could not match those details")

    def test_ussd_flow_uses_id_and_tracking_code(self):
        root = self.client.post("/api/ussd/", {"sessionId": "test-session", "serviceCode": "*384*123#", "phoneNumber": self.applicant.phone, "text": ""})  # noqa: E501
        self.assertTrue(root.content.decode().startswith("CON"))
        id_prompt = self.client.post("/api/ussd/", {"sessionId": "test-session", "phoneNumber": self.applicant.phone, "text": "1"})  # noqa: E501
        self.assertIn("National ID", id_prompt.content.decode())
        code_prompt = self.client.post("/api/ussd/", {"sessionId": "test-session", "phoneNumber": self.applicant.phone, "text": f"1*{self.applicant.national_id}"})  # noqa: E501
        self.assertTrue(code_prompt.content.decode().startswith("CON"))
        result = self.client.post("/api/ussd/", {"sessionId": "test-session", "phoneNumber": self.applicant.phone, "text": f"1*{self.applicant.national_id}*{self.application.tracking_code}"})  # noqa: E501
        self.assertTrue(result.content.decode().startswith("END"))
        self.assertIn(self.application.tracking_code, result.content.decode())
        self.assertLessEqual(len(result.content.decode()), 160)

    def test_chichewa_ussd_collection_keeps_full_hours_under_screen_limit(self):
        session_id = "chichewa-collection-test"
        self.client.post("/api/ussd/", {"sessionId": session_id, "phoneNumber": self.applicant.phone, "text": "3"})
        language = self.client.post("/api/ussd/", {"sessionId": session_id, "phoneNumber": self.applicant.phone, "text": "3*2"})  # noqa: E501
        self.assertIn("END", language.content.decode())
        self.client.post("/api/ussd/", {"sessionId": session_id, "phoneNumber": self.applicant.phone, "text": ""})
        response = self.client.post("/api/ussd/", {"sessionId": session_id, "phoneNumber": self.applicant.phone, "text": "2"})  # noqa: E501
        screen = response.content.decode()
        self.assertTrue(screen.startswith("END"))
        self.assertIn(self.office.collection_hours_for("ny"), screen)
        self.assertIn("Foni:", screen)
        self.assertLessEqual(len(screen), 160)

    def test_authenticated_stage_update_sends_sms_and_audits(self):
        self.client.force_login(self.user)
        response = self.client.post(f"/officer/applications/{self.application.tracking_code}/", {"action": "advance"})
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.current_stage.key, "under_review")
        notification = Notification.objects.get(application=self.application)
        self.assertEqual(notification.status, "sent")
        self.assertTrue(AuditLog.objects.filter(action="notification_dispatched", object_id=str(notification.pk)).exists())  # noqa: E501

    def test_authenticated_api_is_office_scoped(self):
        response = self.client.get(f"/api/applications/{self.application.tracking_code}/", HTTP_AUTHORIZATION=f"Token {self.token.key}")  # noqa: E501
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["phone_masked"], "+265 99* *** 567")

    def test_api_create_stage_and_openapi_schema(self):
        response = self.client.post("/api/applications/", {
            "national_id": "7654321098765", "first_name": "API", "surname": "Applicant",
            "phone": "0991234567", "language": "en", "application_type": "new",
        }, content_type="application/json", HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.assertEqual(response.status_code, 201)
        code = response.json()["tracking_code"]
        update = self.client.put(f"/api/applications/{code}/stage/", {"stage": "under_review"}, content_type="application/json", HTTP_AUTHORIZATION=f"Token {self.token.key}")  # noqa: E501
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["stage"], "under_review")
        schema = self.client.get("/api/schema/")
        self.assertEqual(schema.status_code, 200)
        self.assertContains(schema, "/api/ussd/")
        self.assertContains(schema, "text/plain")
