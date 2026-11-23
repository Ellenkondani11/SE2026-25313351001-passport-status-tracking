from django.core.management.base import BaseCommand, CommandError

from core.audit_chain import verify_audit_chain


class Command(BaseCommand):
    help = "Verify the PASTNS tamper-evident audit log hash chain."

    def handle(self, *args, **options):
        intact, count, tampered = verify_audit_chain()
        if intact:
            self.stdout.write(self.style.SUCCESS(f"Verified: {count} audit log entries intact."))
            return
        raise CommandError(f"Tamper alert: {len(tampered)} of {count} audit log entries failed verification.")