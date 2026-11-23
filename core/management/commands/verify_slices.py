from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import Client
from django.utils import timezone

from core.models import Applicant, Application, Notification, Office, Stage


class Command(BaseCommand):
    help = "Run the three PassTrack vertical slices end to end."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Use existing demo data instead of a temporary dataset.")

    def handle(self, *args, **options):
        results = []
        with transaction.atomic():
            try:
                office, stage_received, stage_review, application, user = self._seed()
                client = Client()
                client.force_login(user)
                # VS1: officer advances stage; public web reflects it.
                vs1 = self._vs1(client, application, stage_review)
                results.append(("VS1", vs1))
                # VS2: idempotent SMS outbox + delivery callback stored.
                vs2 = self._vs2(application)
                results.append(("VS2", vs2))
                # VS3: USSD returns matching status within 160 chars.
                vs3 = self._vs3(client, application)
                results.append(("VS3", vs3))
            finally:
                transaction.set_rollback(True)
        for name, ok in results:
            if ok:
                self.stdout.write(self.style.SUCCESS(f"{name}: PASS"))
            else:
                self.stdout.write(self.style.ERROR(f"{name}: FAIL"))
        if not all(ok for _, ok in results):
            raise CommandError("One or more vertical slices failed.")

    def _seed(self):
        office, _ = Office.objects.get_or_create(code="VSL", defaults={"name": "Vertical Slice Office", "district": "Mangochi"})
        stage_received, _ = Stage.objects.get_or_create(key="vs_received", defaults={"order": 10, "name": "Received", "applicant_text_en": "Received.", "applicant_text_ny": "Lalandiridwa.", "notify": True})
        stage_review, _ = Stage.objects.get_or_create(key="vs_under_review", defaults={"order": 20, "name": "Under review", "applicant_text_en": "Under review.", "applicant_text_ny": "Likuwunikidwa.", "notify": True})
        applicant, _ = Applicant.objects.get_or_create(national_id="9999999999999", defaults={"first_name": "Slice", "surname": "Tester", "phone": "+265991234567"})
        application, _ = Application.objects.get_or_create(tracking_code="MW-VSL-2026-00001", defaults={"applicant": applicant, "office": office, "current_stage": stage_received})
        user, created = User.objects.get_or_create(username="vs_officer", defaults={"is_active": True})
        if created:
            user.set_password("long-enough-test-pass")
            user.save()
        user.profile.office = office
        user.profile.role = "officer"
        user.profile.save()
        return office, stage_received, stage_review, application, user

    def _vs1(self, client, application, stage_review):
        from core.services import transition_application_stage
        transition_application_stage(application, stage_review, actor=None, reason="VS1", ip="127.0.0.1")
        application.refresh_from_db()
        session = client.session
        session["verified_status_code"] = application.tracking_code
        session["verified_status_at"] = timezone.now().isoformat()
        session.save()
        response = client.get(f"/status/?code={application.tracking_code}")
        return response.status_code == 200 and "Under review" in response.content.decode()

    def _vs2(self, application):
        row = Notification.objects.filter(application=application).first()
        if row is None:
            return False
        row.provider_ref = "vs-ref-1"
        row.save(update_fields=["provider_ref"])
        from django.test import Client
        c = Client()
        # callback without auth token allowed when SMS_CALLBACK_TOKEN empty (default test env)
        response = c.post("/api/sms/delivery/", {"provider_ref": "vs-ref-1", "status": "Delivered"}, content_type="application/json")
        row.refresh_from_db()
        return response.status_code == 200 and row.status == "delivered"

    def _vs3(self, client, application):
        response = client.post("/api/ussd/", {"sessionId": "vs-session", "phoneNumber": "+265991234567", "text": f"1*{application.applicant.national_id}*{application.tracking_code}"})
        body = response.content.decode()
        return response.status_code == 200 and "Under review" in body and len(body) <= 160