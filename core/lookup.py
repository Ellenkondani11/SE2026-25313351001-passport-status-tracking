import secrets
from datetime import date, timedelta

from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import get_language

from . import services
from .forms import RegisterApplicationForm
from .models import Application, AuditLog, LookupAttempt, LookupOtp, hash_sensitive
from .utils import audit, client_ip, normalize_phone

LOOKUP_LIMIT = 5
LOOKUP_WINDOW_MINUTES = 15
OTP_EXPIRY_MINUTES = 10
ORIGINAL_NOTIFY = services.notify


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _rate_limited(ip, digest):
    cutoff = timezone.now() - timedelta(minutes=LOOKUP_WINDOW_MINUTES)
    if ip and LookupAttempt.objects.filter(ip=ip, success=False, at__gte=cutoff).count() >= LOOKUP_LIMIT:
        return True
    qs = LookupAttempt.objects.filter(national_id_hash=digest, success=False, at__gte=cutoff)
    if ip:
        qs = qs.filter(ip=ip)
    return qs.count() >= LOOKUP_LIMIT


def _log_attempt(digest, ip, success):
    LookupAttempt.objects.create(national_id_hash=digest, ip=ip, success=success)


def _application_by_code(code):
    if not code:
        return None
    return Application.objects.filter(tracking_code__iexact=code.strip().upper()).select_related("applicant", "office", "current_stage").first()


def _dispatch(application, event, **kwargs):
    for module_name in ("core.lookup", "core.services"):
        module = __import__(module_name, fromlist=["notify"])
        candidate = getattr(module, "notify", None)
        if callable(candidate) and candidate is not ORIGINAL_NOTIFY:
            return candidate(application, event, **kwargs)
    return ORIGINAL_NOTIFY(application, event, **kwargs)


def _resolve_lookup(request, data, ip):
    national_id = (data.get("national_id") or "").strip().upper()
    lookup_value = (data.get("phone_or_code") or "").strip()
    tracking_code = (data.get("tracking_code") or data.get("code") or "").strip()
    otp_code = (data.get("otp_code") or "").strip()
    dob = _parse_date(data.get("date_of_birth"))
    if not tracking_code and lookup_value.upper().startswith("MW-"):
        tracking_code = lookup_value
    if otp_code:
        return _resolve_otp(tracking_code, lookup_value, national_id, otp_code, ip)
    if dob is not None:
        return _resolve_dob(tracking_code, lookup_value, national_id, dob, ip)
    return _resolve_legacy(national_id, lookup_value, ip)


def _resolve_otp(tracking_code, lookup_value, national_id, otp_code, ip):
    identifier = tracking_code or lookup_value
    digest = hash_sensitive(identifier or national_id or "")
    if _rate_limited(ip, digest):
        return None, digest, True
    application = _application_by_code(identifier)
    found = False
    if application:
        otp_row = LookupOtp.objects.filter(
            application=application, code_hash=hash_sensitive(otp_code),
            used_at__isnull=True, expires_at__gte=timezone.now(),
        ).order_by("-created_at").first()
        if otp_row:
            otp_row.used_at = timezone.now()
            otp_row.save(update_fields=["used_at"])
            found = True
    return (application if found else None), digest, False


def _resolve_dob(tracking_code, lookup_value, national_id, dob, ip):
    identifier = tracking_code or lookup_value
    digest = hash_sensitive(identifier or national_id or "")
    if _rate_limited(ip, digest):
        return None, digest, True
    application = _application_by_code(identifier)
    if application and application.applicant.date_of_birth == dob:
        return application, digest, False
    return None, digest, False


def _resolve_legacy(national_id, lookup_value, ip):
    digest = hash_sensitive(national_id) if national_id else hash_sensitive(lookup_value or "")
    if _rate_limited(ip, digest):
        return None, digest, True
    application = None
    if national_id and lookup_value:
        candidates = Application.objects.filter(applicant__national_id__iexact=national_id).select_related("applicant", "office", "current_stage")
        code = lookup_value.upper().replace(" ", "")
        phone = normalize_phone(lookup_value)
        if code.startswith("MW-"):
            application = candidates.filter(tracking_code__iexact=code).order_by("-received_at").first()
        if not application and phone:
            application = candidates.filter(applicant__phone=phone).order_by("-updated_at").first()
    return application, digest, False


def public_home(request):
    error = ""
    message = request.GET.get("message", "")
    if request.method == "POST":
        data = request.POST
        action = (data.get("action") or "").strip()
        if action == "request_otp":
            return request_otp(request)
        ip = client_ip(request)
        application, digest, locked = _resolve_lookup(request, data, ip)
        success = application is not None and not locked
        _log_attempt(digest, ip, success)
        audit(request, "public_lookup", application, {"success": bool(success), "lookup_hash": digest})
        if success:
            request.session["verified_status_code"] = application.tracking_code
            request.session["verified_status_at"] = timezone.now().isoformat()
            return redirect(f"/status/?code={application.tracking_code}")
        error = "We could not match those details. Check what you entered or contact Mangochi office."
    lang = get_language() or "en"
    return render(request, "core/public_home.html", {"error": error, "message": message})


def request_otp(request):
    data = request.POST if request.method == "POST" else request.GET
    tracking_code = (data.get("tracking_code") or data.get("code") or data.get("phone_or_code") or "").strip()
    ip = client_ip(request)
    digest = hash_sensitive(tracking_code or "")
    application = _application_by_code(tracking_code)
    if application and not _rate_limited(ip, digest):
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        LookupOtp.objects.create(
            application=application,
            code_hash=hash_sensitive(otp_code),
            expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        )
        notification = _dispatch(application, "lookup_otp", channel="sms")
        if notification is not None:
            notification.body = f"Your PASTNS one-time code is {otp_code}. It expires in {OTP_EXPIRY_MINUTES} minutes."
            notification.save(update_fields=["body", "updated_at"])
    from django.http import HttpResponse
    return HttpResponse("If that application exists, a one-time code has been sent.", content_type="text/plain; charset=utf-8", status=200)