import hashlib
import json

from django.db import migrations


def _canonical(entry):
    at_value = entry.at
    if hasattr(at_value, "isoformat"):
        at_value = at_value.isoformat()
    payload = {
        "user_id": entry.user_id,
        "action": entry.action,
        "object_type": entry.object_type,
        "object_id": entry.object_id,
        "details": entry.details or {},
        "ip": str(entry.ip) if entry.ip is not None else None,
        "at": at_value,
        "reason": entry.reason,
        "prev_hash": entry.prev_hash,
    }
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def backfill(apps, schema_editor):
    AuditLog = apps.get_model("core", "AuditLog")
    previous_hash = "GENESIS"
    for entry in AuditLog.objects.order_by("at", "id"):
        if entry.entry_hash:
            previous_hash = entry.entry_hash
            continue
        entry.prev_hash = previous_hash
        entry.entry_hash = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
        entry.save(update_fields=["prev_hash", "entry_hash"])
        previous_hash = entry.entry_hash


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_loginattempt_core_logina_usernam_b4c7bb_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_backfill),
    ]