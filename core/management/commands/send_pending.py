from django.core.management.base import BaseCommand
from django.db.models import F, Q
from django.utils import timezone
from core.models import Notification
from core.services import retry_notification

class Command(BaseCommand):
    help = "Retry queued or failed PASTNS notifications through the configured gateway."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        now = timezone.now()
        rows = Notification.objects.filter(status__in=["queued", "failed"]).filter(
            retry_count__lt=F("max_retries")
        ).filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now)).order_by("created_at")[:options["limit"]]
        sent = failed = 0
        for row in rows:
            retry_notification(row)
            if row.status in ("sent", "delivered"):
                sent += 1
            else:
                failed += 1
        self.stdout.write(self.style.SUCCESS(f"Retried {sent + failed} notification(s): {sent} sent, {failed} failed."))
