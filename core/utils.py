from django.utils import timezone
from .models import AuditLog


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    ip = forwarded or request.META.get("REMOTE_ADDR")
    return ip or None


def audit(request, action, obj=None, details=None, user=None):
    if obj is not None:
        object_type = obj.__class__.__name__
        object_id = str(getattr(obj, "pk", ""))
    else:
        object_type, object_id = "", ""
    return AuditLog.objects.create(
        user=user or getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=details or {},
        ip=client_ip(request) if request else None,
        at=timezone.now(),
    )


def normalize_phone(value):
    raw = "".join(ch for ch in (value or "") if ch.isdigit() or ch == "+")
    if raw.startswith("0") and len(raw) == 10:
        return "+265" + raw[1:]
    if raw.startswith("265"):
        return "+" + raw
    if raw and not raw.startswith("+"):
        return "+" + raw
    return raw


def mask_phone(value):
    value = value or ""
    if value.startswith("+265") and len(value) == 13:
        return f"+265 {value[4:6]}* *** {value[-3:]}"
    return f"{value[:4]} *** {value[-3:]}" if len(value) >= 10 else "••••"


def mask_national_id(value):
    value = value or ""
    return "••••" + value[-4:] if len(value) > 4 else "••••"


def tracking_code_for(office):
    from .models import Application
    year = timezone.localdate().year
    prefix = f"MW-{office.code}-{year}-"
    last = Application.objects.filter(tracking_code__startswith=prefix).order_by("-tracking_code").first()
    sequence = int(last.tracking_code.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{sequence:05d}"
