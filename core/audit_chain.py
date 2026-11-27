import hashlib
import json
from django.utils import timezone

from .models import AuditLog


def _canonical(entry):
    user_id = getattr(entry.user, "pk", None)
    if entry.user is None:
        user_id = None
    at_value = entry.at
    if at_value is None:
        at_value = timezone.now()
    if hasattr(at_value, "isoformat"):
        at_value = at_value.isoformat()
    payload = {
        "user_id": user_id,
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


def compute_entry_hash(entry):
    previous = AuditLog.objects.order_by("at", "id").last()
    prev_hash = "GENESIS"
    if previous is not None and previous.entry_hash:
        prev_hash = previous.entry_hash
    entry.prev_hash = prev_hash
    # prev_hash is included in canonical payload; compute final hash.
    entry.entry_hash = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
    return entry.prev_hash, entry.entry_hash


def verify_audit_chain():
    entries = list(AuditLog.objects.order_by("at", "id"))
    previous_hash = "GENESIS"
    intact = True
    tampered = []
    for entry in entries:
        if entry.prev_hash != previous_hash:
            intact = False
            tampered.append(entry.pk)
            previous_hash = entry.entry_hash or previous_hash
            continue
        expected = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
        if expected != entry.entry_hash:
            intact = False
            tampered.append(entry.pk)
        previous_hash = entry.entry_hash or previous_hash
    return intact, len(entries), tampered
