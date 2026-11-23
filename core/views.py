import csv
from datetime import timedelta
from functools import wraps
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone, translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language, gettext as _
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from .forms import RegisterApplicationForm, ContactCorrectionForm, StaffCreateForm
from .models import (Application, Applicant, AuditLog, LoginAttempt, Notification,
                     OfficerNote, Office, Profile, SmsTemplate, Stage, StageChange, UssdSession, hash_sensitive)
from .services import notify_stage, resend_last_notification, retry_notification, transition_application_stage
from .utils import audit, client_ip, mask_national_id, mask_phone, normalize_phone, tracking_code_for

LOOKUP_LIMIT = 5
LOOKUP_WINDOW_MINUTES = 15


def public_language(request):
    return (get_language() or "en")[:2]


def language_switch(request):
    code = request.GET.get("lang", "en")
    if code not in ("en", "ny"):
        code = "en"
    translation.activate(code)
    next_url = request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = "/"
    response = redirect(next_url)
    response.set_cookie("django_language", code, max_age=60 * 60 * 24 * 365, samesite="Lax")
    request.session["django_language"] = code
    return response


def public_home(request):
    from .lookup import public_home as _public_home
    return _public_home(request)


def public_status(request):
    code = (request.GET.get("code") or "").strip().upper()
    allowed = request.session.get("verified_status_code") == code and bool(code)
    if allowed:
        verified_at = request.session.get("verified_status_at")
        parsed = None
        if verified_at:
            try:
                parsed = timezone.datetime.fromisoformat(str(verified_at))
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            except ValueError:
                parsed = None
        if parsed is not None and (timezone.now() - parsed).total_seconds() > 15 * 60:
            allowed = False
            request.session.pop("verified_status_code", None)
            request.session.pop("verified_status_at", None)
    if not allowed:
        return render(request, "core/status_denied.html", status=403)
    application = get_object_or_404(
        Application.objects.select_related("applicant", "office", "current_stage").prefetch_related("notifications"),
        tracking_code__iexact=code,
    )
    language = public_language(request)
    changes = list(application.stage_changes.select_related("from_stage", "to_stage", "by_user").order_by("at"))
    notification_rows = application.notifications.order_by("-created_at")[:20]
    with translation.override(language):
        template_labels = {key: _(label) for key, label in {
            "received": "Received", "under_review": "Under review", "approved": "Approved",
            "printed": "Printed", "ready": "Ready for collection", "collected": "Collected",
            "on_hold": "On hold", "rejected": "Rejected",
        }.items()}
        histories = [{
            "row": n,
            "label": template_labels.get(n.template_key, n.template_key),
            "destination": mask_phone(n.to) if n.channel == "sms" else (n.to[:2] + "•••" + n.to[n.to.find("@"):] if "@" in n.to else "••••"),
        } for n in notification_rows]
    context = {
        "application": application,
        "language": language,
        "stage_text": application.current_stage.applicant_text(language),
        "collection_hours": application.office.collection_hours_for(language),
        "stage_steps": list(Stage.objects.filter(key__in=["received", "under_review", "approved", "printed", "ready"]).order_by("order")),
        "histories": histories,
        "timeline": changes,
    }
    return render(request, "core/public_status.html", context)


def request_otp(request):
    from .lookup import request_otp as _request_otp
    return _request_otp(request)


def ussd_demo(request):
    return render(request, "core/ussd_demo.html", {"simulator": "public"})


@require_http_methods(["GET", "POST"])
def officer_login(request):
    if request.user.is_authenticated:
        return redirect("officer_home")
    error = ""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        ip = client_ip(request)
        user_hash = hash_sensitive(username)
        cutoff = timezone.now() - timedelta(minutes=15)
        failures = LoginAttempt.objects.filter(username_hash=user_hash, success=False, at__gte=cutoff)
        if ip:
            failures = failures.filter(ip=ip)
        if failures.count() >= 5:
            audit(request, "login_locked", details={"username_hash": user_hash, "success": False})
            error = _("Sign-in is temporarily locked. Try again in 15 minutes.")
        else:
            user = authenticate(request, username=username, password=password)
            ok = bool(user and user.is_active)
            LoginAttempt.objects.create(username_hash=user_hash, ip=ip, success=ok)
            if not ok:
                audit(request, "login_failed", details={"username_hash": user_hash, "success": False})
            if ok:
                login(request, user)
                request.session.set_expiry(1800)
                audit(request, "login", user, {"username": user.get_username()})
                next_url = request.GET.get("next") or "/officer/"
                if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    next_url = "/officer/"
                return redirect(next_url)
            error = _("Sign-in details do not match.")
    return render(request, "core/login.html", {"error": error})


@require_POST
def officer_logout(request):
    if request.user.is_authenticated:
        audit(request, "logout", request.user, {"username": request.user.get_username()})
    logout(request)
    return redirect("officer_login")


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"/officer/login/?next={request.path}")
            profile = getattr(request.user, "profile", None)
            if not profile or (roles and profile.role not in roles):
                return render(request, "core/forbidden.html", status=403)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def office_queryset(request):
    profile = request.user.profile
    qs = Application.objects.select_related("applicant", "office", "current_stage")
    if profile.office_id:
        return qs.filter(office_id=profile.office_id)
    if profile.role == "admin":
        return qs
    return qs.none()


def get_office(request):
    profile = request.user.profile
    if profile.office_id:
        return profile.office
    if profile.role == "admin":
        return Office.objects.first()
    return None


@role_required("officer", "supervisor", "admin")
def officer_home(request):
    qs = office_queryset(request)
    office = get_office(request)
    stages = list(Stage.objects.all())
    counts = {stage.key: qs.filter(current_stage=stage).count() for stage in stages}
    query = (request.GET.get("q") or "").strip()
    stage_filter = request.GET.get("stage", "")
    status_filter = request.GET.get("status", "active")
    if query:
        qs = qs.filter(
            Q(tracking_code__icontains=query)
            | Q(applicant__national_id__icontains=query)
            | Q(applicant__phone__icontains=query)
            | Q(applicant__first_name__icontains=query)
            | Q(applicant__surname__icontains=query)
        )
    if stage_filter:
        qs = qs.filter(current_stage__key=stage_filter)
    if status_filter and status_filter != "all":
        qs = qs.filter(status=status_filter)
    ordering = request.GET.get("sort", "-updated_at")
    allowed_sort = {"-updated_at", "updated_at", "tracking_code", "-received_at", "applicant__surname"}
    if ordering not in allowed_sort:
        ordering = "-updated_at"
    qs = qs.order_by(ordering)
    if request.GET.get("export") == "csv":
        return _applications_csv(qs)
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "core/officer_home.html", {
        "office": office, "stages": stages, "counts": counts, "page_obj": page_obj,
        "applications": page_obj.object_list, "query": query, "stage_filter": stage_filter,
        "status_filter": status_filter, "sort": ordering,
    })


@role_required("officer", "supervisor", "admin")
@require_http_methods(["GET", "POST"])
def register_application(request):
    form = RegisterApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        office = get_office(request)
        if not office:
            messages.error(request, "This account is not assigned to an office.")
            return redirect("officer_home")
        data = form.cleaned_data
        with transaction.atomic():
            applicant, created = Applicant.objects.get_or_create(
                national_id=data["national_id"],
                defaults={key: data[key] for key in ("first_name", "surname", "phone", "email", "language", "date_of_birth")},
            )
            if not created:
                applicant.first_name = data["first_name"]
                applicant.surname = data["surname"]
                applicant.phone = data["phone"]
                applicant.email = data["email"]
                applicant.language = data["language"]
                applicant.date_of_birth = data.get("date_of_birth")
                applicant.save()
            received = Stage.objects.get(key="received")
            application = Application.objects.create(
                tracking_code=tracking_code_for(office), applicant=applicant, office=office,
                application_type=data["application_type"], current_stage=received,
            )
            StageChange.objects.create(application=application, from_stage=None, to_stage=received, by_user=request.user, reason="Application registered")
            audit(request, "application_registered", application, {"stage": received.key})
            notification = notify_stage(application, received, actor=request.user, ip=client_ip(request))
        if notification and notification.status == "failed":
            messages.warning(request, "Application registered; the SMS failed and is available in the outbox.")
        return render(request, "core/registration_complete.html", {"application": application, "notification": notification})
    return render(request, "core/register.html", {"form": form})


@role_required("officer", "supervisor", "admin")
def _handle_advance(request, application):
    next_stage = application.next_stage
    if not next_stage:
        messages.error(request, "This application has no next stage to advance to.")
        return
    transition_application_stage(application, next_stage, actor=request.user, reason="Advanced one stage", ip=client_ip(request))
    messages.success(request, f"Advanced to {next_stage.name}.")


def _handle_move(request, application):
    stages = {stage.key: stage for stage in Stage.objects.all()}
    target = stages.get(request.POST.get("target_stage"))
    reason = (request.POST.get("reason") or "").strip()
    if request.user.profile.role not in ("supervisor", "admin"):
        messages.error(request, "A supervisor must approve a backward move or skipped stage.")
        return
    if not target or not reason:
        messages.error(request, "Choose a stage and enter a reason.")
        return
    transition_application_stage(application, target, actor=request.user, reason=reason, ip=client_ip(request))
    messages.success(request, f"Moved to {target.name}.")


def _handle_hold(request, application):
    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Enter a reason for putting this application on hold.")
        return
    hold_stage = Stage.objects.get(key="on_hold")
    transition_application_stage(application, hold_stage, actor=request.user, reason=reason, new_status="on_hold", ip=client_ip(request))
    messages.success(request, "Application put on hold.")


def _handle_resume(request, application):
    if application.status != "on_hold":
        messages.error(request, "This application is not on hold.")
        return
    prior = application.previous_stage
    if prior is None:
        prior = Stage.objects.get(key="received")
    transition_application_stage(application, prior, actor=request.user, reason="Resumed from hold", new_status="active", ip=client_ip(request))
    messages.success(request, "Application resumed.")


def _handle_collect(request, application):
    stages = {stage.key: stage for stage in Stage.objects.all()}
    if application.current_stage.key != "ready" and request.user.profile.role not in ("supervisor", "admin"):
        messages.error(request, "Only a supervisor can mark an application collected before it is ready.")
        return
    reason = request.POST.get("reason") or "Passport collected"
    transition_application_stage(application, stages["collected"], actor=request.user, reason=reason, new_status="collected", ip=client_ip(request))
    messages.success(request, "Application marked as collected.")


def _handle_reject(request, application):
    stages = {stage.key: stage for stage in Stage.objects.all()}
    reason = (request.POST.get("reason") or "").strip()
    if request.user.profile.role not in ("supervisor", "admin") or not reason:
        messages.error(request, "A supervisor and a reason are required to reject an application.")
        return
    transition_application_stage(application, stages["rejected"], actor=request.user, reason=reason, new_status="rejected", ip=client_ip(request))
    messages.success(request, "Application marked as rejected.")


def _handle_note(request, application):
    body = (request.POST.get("note") or "").strip()
    if body:
        OfficerNote.objects.create(application=application, user=request.user, body=body[:600])
        audit(request, "officer_note_added", application, {"note_length": len(body)})
        messages.success(request, "Note added.")


def _handle_correct_contact(request, application):
    form = ContactCorrectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid new phone number and reason.")
        return
    old_phone = application.applicant.phone
    application.applicant.phone = form.cleaned_data["phone"]
    application.applicant.email = form.cleaned_data["email"]
    application.applicant.save(update_fields=["phone", "email"])
    audit(request, "contact_corrected", application, {
        "old_phone": mask_phone(old_phone), "new_phone": mask_phone(application.applicant.phone),
        "reason": form.cleaned_data["reason"][:160],
    })
    messages.success(request, "Contact details updated. The correction was recorded in the audit log.")


def _handle_resend(request, application):
    resent = resend_last_notification(application, actor=request.user, ip=client_ip(request))
    if resent:
        audit(request, "notification_resent", resent, {"status": resent.status})
        messages.success(request, f"Notification resent to the current contact: {resent.get_status_display()}.")
    else:
        messages.error(request, "There is no notification or current contact to resend to.")


APPLICATION_ACTION_HANDLERS = {
    "advance": _handle_advance,
    "move": _handle_move,
    "hold": _handle_hold,
    "resume": _handle_resume,
    "collect": _handle_collect,
    "reject": _handle_reject,
    "note": _handle_note,
    "correct_contact": _handle_correct_contact,
    "resend": _handle_resend,
}


def application_detail(request, code):
    application = get_object_or_404(office_queryset(request), tracking_code=code)
    if request.method == "POST":
        action = request.POST.get("action")
        handler = APPLICATION_ACTION_HANDLERS.get(action)
        if handler is None:
            messages.error(request, "Unknown action.")
        else:
            handler(request, application)
        return redirect("application_detail", code=code)
    changes = list(application.stage_changes.select_related("from_stage", "to_stage", "by_user").order_by("-at"))
    notes = list(application.notes.select_related("user"))
    notifications = list(application.notifications.all())
    timeline_items = ([{"kind": "stage", "at": row.at, "row": row} for row in changes]
                      + [{"kind": "note", "at": row.created_at, "row": row} for row in notes]
                      + [{"kind": "notification", "at": row.created_at, "row": row} for row in notifications])
    timeline_items.sort(key=lambda item: item["at"], reverse=True)
    return render(request, "core/application_detail.html", {
        "application": application,
        "stage_steps": list(Stage.objects.filter(key__in=["received", "under_review", "approved", "printed", "ready"]).order_by("order")),
        "timeline_items": timeline_items,
        "stages": Stage.objects.all(),
        "correction_form": ContactCorrectionForm(initial={"phone": application.applicant.phone, "email": application.applicant.email}),
    })


def _change_stage(request, application, stage, reason="", new_status=None, notify_override=True):
    transition_application_stage(
        application, stage, actor=request.user, reason=reason, new_status=new_status,
        ip=client_ip(request), notify=notify_override,
    )


@role_required("officer", "supervisor", "admin")
@require_POST
def bulk_update(request):
    codes = request.POST.getlist("selected")
    action = request.POST.get("action")
    queryset = office_queryset(request).filter(tracking_code__in=codes)
    if action == "export":
        return _applications_csv(queryset.order_by("tracking_code"))
    destination_key = {"printed": "printed", "ready": "ready"}.get(action)
    if not destination_key:
        messages.error(request, "Choose a valid bulk action.")
        return redirect("officer_home")
    target = Stage.objects.get(key=destination_key)
    changed, queued, failed = 0, 0, 0
    for application in queryset:
        if action == "printed" and application.current_stage.key != "approved":
            continue
        if action == "ready" and application.current_stage.key != "printed":
            continue
        _change_stage(request, application, target, reason=f"Bulk marked {target.name}")
        changed += 1
        notification = application.notifications.order_by("-created_at").first()
        if notification:
            if notification.status == "failed":
                failed += 1
            else:
                queued += 1
    audit(request, "bulk_stage_update", details={"stage": target.key, "updated": changed})
    messages.success(request, f"{changed} updated · {queued} SMS sent/queued · {failed} failed.")
    return redirect("officer_home")


def _csv_safe(value):
    text = str(value or "")
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _applications_csv(queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="pastns-applications.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Tracking code", "Applicant", "National ID", "Phone", "Type", "Stage", "Status", "Received", "Office"])
    for app in queryset.select_related("applicant", "office", "current_stage"):
        writer.writerow([_csv_safe(app.tracking_code), _csv_safe(f"{app.applicant.first_name} {app.applicant.surname}"), _csv_safe(mask_national_id(app.applicant.national_id)), _csv_safe(mask_phone(app.applicant.phone)), _csv_safe(app.get_application_type_display()), _csv_safe(app.current_stage.name), _csv_safe(app.get_status_display()), app.received_at.isoformat(), _csv_safe(app.office.name)])
    return response


@role_required("officer", "supervisor", "admin")
def notification_outbox(request):
    qs = Notification.objects.filter(application__in=office_queryset(request)).select_related("application", "application__applicant", "application__office")
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)
    if request.method == "POST":
        row = get_object_or_404(qs, pk=request.POST.get("notification_id"))
        retry_notification(row, actor=request.user, ip=client_ip(request))
        audit(request, "notification_retried", row, {"status": row.status})
        messages.success(request, f"Message retried: {row.get_status_display()}.")
        return redirect("notification_outbox")
    page_obj = Paginator(qs.order_by("-created_at"), 50).get_page(request.GET.get("page"))
    return render(request, "core/outbox.html", {"page_obj": page_obj, "notifications": page_obj.object_list, "status_filter": status_filter})


@role_required("supervisor", "admin")
def reports(request):
    apps = office_queryset(request)
    if request.GET.get("export"):
        kind = request.GET.get("export")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="pastns-{kind}.csv"'
        writer = csv.writer(response)
        if kind == "monthly":
            writer.writerow(["Month", "Applications"])
            for row in _monthly_counts(apps):
                writer.writerow([row["label"], row["count"]])
        elif kind == "delivery":
            writer.writerow(["Status", "Count"])
            notifications = Notification.objects.filter(application__in=apps)
            for status, label in Notification.STATUS_CHOICES:
                writer.writerow([label, notifications.filter(status=status).count()])
        else:
            writer.writerow(["Stage", "Applications", "Average days in stage"])
            for row in _stage_metrics(apps):
                writer.writerow([row["stage"].name, row["count"], row["average_days"]])
        return response
    stage_metrics = _stage_metrics(apps)
    monthly = _monthly_counts(apps)
    max_count = max([r["count"] for r in monthly] or [1]) or 1
    chart_bars = []
    for i, row in enumerate(monthly):
        height = int((row["count"] / max_count) * 110)
        chart_bars.append({"x": 58 + i * 76, "y": 145 - height, "height": height, "label": row["short"], "count": row["count"]})
    notifications = Notification.objects.filter(application__in=apps)
    total_notifications = notifications.count()
    successful = notifications.filter(status__in=["sent", "delivered"]).count()
    delivery_rate = round(successful * 100 / total_notifications) if total_notifications else 0
    context = {"stage_metrics": stage_metrics, "monthly": monthly, "chart_bars": chart_bars,
               "delivery_rate": delivery_rate, "total_notifications": total_notifications,
               "successful_notifications": successful, "application_count": apps.count()}
    return render(request, "core/reports.html", context)


def _stage_metrics(apps):
    rows = []
    stages = list(Stage.objects.all())
    current_time = timezone.now()
    app_ids = list(apps.values_list("id", flat=True))
    for stage in stages:
        durations = []
        changes = list(StageChange.objects.filter(application_id__in=app_ids, to_stage=stage).order_by("application_id", "at"))
        by_app = {}
        for change in changes:
            by_app.setdefault(change.application_id, []).append(change)
        for app_id, entries in by_app.items():
            for index, entry in enumerate(entries):
                next_entry = StageChange.objects.filter(application_id=app_id, at__gt=entry.at).order_by("at").first()
                end = next_entry.at if next_entry else current_time
                durations.append(max(0, (end - entry.at).total_seconds() / 86400))
        rows.append({"stage": stage, "count": apps.filter(current_stage=stage).count(),
                     "average_days": round(sum(durations) / len(durations), 1) if durations else 0})
    return rows


def _monthly_counts(apps):
    today = timezone.localdate()
    months = []
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = timezone.datetime(year, month, 1, tzinfo=timezone.get_current_timezone())
        if month == 12:
            end = timezone.datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            end = timezone.datetime(year, month + 1, 1, tzinfo=timezone.get_current_timezone())
        count = apps.filter(received_at__gte=start, received_at__lt=end).count()
        months.append({"label": start.strftime("%B %Y"), "short": start.strftime("%b"), "count": count})
    return months


@role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_console(request):
    if request.method == "POST":
        action = request.POST.get("action")
        handler = ADMIN_ACTION_HANDLERS.get(action)
        if handler is None:
            messages.error(request, "Unknown action.")
        else:
            handler(request)
        return redirect("admin_console")
    return render(request, "core/admin_console.html", {
        "staff": User.objects.select_related("profile", "profile__office").order_by("username"),
        "stages": Stage.objects.all(), "templates": SmsTemplate.objects.all(), "offices": Office.objects.all(),
        "staff_form": StaffCreateForm(),
    })


def _admin_create_user(request):
    form = StaffCreateForm(request.POST)
    if form.is_valid():
        user = User.objects.create_user(username=form.cleaned_data["username"], password=form.cleaned_data["password"], first_name=form.cleaned_data["first_name"], last_name=form.cleaned_data["surname"])
        profile = user.profile
        profile.role = form.cleaned_data["role"]
        profile.office = get_office(request)
        profile.save()
        audit(request, "staff_user_created", user, {"role": profile.role})
        messages.success(request, "Staff account created.")
    else:
        messages.error(request, "Review the user form and try again.")


def _admin_set_role(request):
    target_user = get_object_or_404(User, pk=request.POST.get("user_id"))
    role = request.POST.get("role")
    if role in dict(Profile.ROLE_CHOICES):
        target_user.profile.role = role
        target_user.profile.office = get_office(request)
        target_user.profile.save()
        audit(request, "staff_role_changed", target_user, {"role": role})
        messages.success(request, "Staff role updated.")


def _admin_save_stage(request):
    stage = get_object_or_404(Stage, pk=request.POST.get("stage_id"))
    stage.name = request.POST.get("name", stage.name)[:60]
    stage.applicant_text_en = request.POST.get("applicant_text_en", stage.applicant_text_en)[:280]
    stage.applicant_text_ny = request.POST.get("applicant_text_ny", stage.applicant_text_ny)[:280]
    stage.colour = request.POST.get("colour", stage.colour)[:20]
    stage.notify = request.POST.get("notify") == "on"
    stage.save()
    audit(request, "stage_definition_updated", stage, {"key": stage.key})
    messages.success(request, "Stage definition saved.")


def _admin_save_template(request):
    template = get_object_or_404(SmsTemplate, pk=request.POST.get("template_id"))
    body_en = request.POST.get("body_en", template.body_en)
    body_ny = request.POST.get("body_ny", template.body_ny)
    if len(body_en) > 160 or len(body_ny) > 160:
        messages.error(request, "SMS templates must be 160 characters or fewer. Unicode messages may use multiple SMS segments.")
        return
    template.name = request.POST.get("name", template.name)[:80]
    template.body_en = body_en
    template.body_ny = body_ny
    template.is_active = request.POST.get("is_active") == "on"
    template.save()
    audit(request, "sms_template_updated", template, {"key": template.key})
    messages.success(request, "SMS template saved.")


def _admin_update_office(request):
    office = get_object_or_404(Office, pk=request.POST.get("office_id"))
    office.name = request.POST.get("name", office.name)[:100]
    office.district = request.POST.get("district", office.district)[:80]
    office.phone = request.POST.get("phone", office.phone)[:40]
    office.address = request.POST.get("address", office.address)[:240]
    office.collection_hours = request.POST.get("collection_hours", office.collection_hours)[:120]
    office.collection_hours_ny = request.POST.get("collection_hours_ny", office.collection_hours_ny)[:120]
    office.save()
    audit(request, "office_updated", office)
    messages.success(request, "Office details saved.")


def _admin_create_office(request):
    code = (request.POST.get("code") or "").strip().upper()
    name = (request.POST.get("name") or "").strip()
    if code and name:
        office, created = Office.objects.get_or_create(code=code, defaults={
            "name": name, "district": request.POST.get("district", "")[:80],
            "phone": request.POST.get("phone", "")[:40], "address": request.POST.get("address", "")[:240],
            "collection_hours": request.POST.get("collection_hours", "")[:120],
            "collection_hours_ny": request.POST.get("collection_hours_ny", "")[:120],
        })
        if created:
            audit(request, "office_created", office)
            messages.success(request, "Office added.")
        else:
            messages.error(request, "An office with that code already exists.")


ADMIN_ACTION_HANDLERS = {
    "create_user": _admin_create_user,
    "set_role": _admin_set_role,
    "save_stage": _admin_save_stage,
    "save_template": _admin_save_template,
    "update_office": _admin_update_office,
    "create_office": _admin_create_office,
}


@role_required("officer", "supervisor", "admin")
def audit_log(request):
    from .audit_chain import verify_audit_chain
    qs = AuditLog.objects.select_related("user")
    action = request.GET.get("action", "")
    if action:
        qs = qs.filter(action__icontains=action)
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page"))
    intact, count, tampered = verify_audit_chain()
    return render(request, "core/audit_log.html", {
        "page_obj": page_obj, "entries": page_obj.object_list, "action_filter": action,
        "audit_chain_ok": intact, "audit_chain_count": count, "audit_tampered": tampered,
        "audit_badge": "Verified" if intact else "Tamper alert",
    })


@role_required("officer", "supervisor", "admin")
def officer_ussd_sim(request):
    return render(request, "core/ussd_demo.html", {"simulator": "officer"})


@csrf_exempt
def _ussd_find_application(parts, phone):
    national_id = parts[1].strip().upper()[:32] if len(parts) > 1 else ""
    choice = "*".join(parts[2:]).strip() if len(parts) > 2 else ""
    apps = Application.objects.filter(applicant__national_id__iexact=national_id).select_related("applicant", "current_stage", "office").order_by("-updated_at")
    if choice == "0":
        return apps.filter(applicant__phone=phone).first(), national_id
    if choice:
        return apps.filter(tracking_code__iexact=choice.upper()).first(), national_id
    return None, national_id


def _ussd_status_response(parts, phone, lang, state):
    if len(parts) == 1:
        state["screen"] = "national_id"
        text = "CON Enter your National ID:" if lang == "en" else "CON Lowetsani nambala ya ID yanu:"
        return text, state
    if len(parts) == 2:
        state["national_id"] = parts[1][:32]
        state["screen"] = "lookup_method"
        text = "CON Enter tracking code, or 0 to use this phone:" if lang == "en" else "CON Lowetsani tracking code, kapena 0 kugwiritsa ntchito foniyi:"
        return text, state
    application, national_id = _ussd_find_application(parts, phone)
    state["screen"] = "done"
    if application:
        with translation.override(lang):
            stage_name = _(application.current_stage.name)
            stage_text = application.current_stage.applicant_text(lang)
        response = f"END {application.tracking_code}: {stage_name}. {stage_text}"
        audit(None, "ussd_lookup", application, {"success": True, "national_id_hash": hash_sensitive(national_id)})
        return response, state
    response = "END We could not match those details. Contact Mangochi office." if lang == "en" else "END Sitinapeze zambiri zimenezi. Lumikizanani ndi ofesi ya Mangochi."
    audit(None, "ussd_lookup", details={"success": False, "national_id_hash": hash_sensitive(national_id)})
    return response, state


def _ussd_language_response(parts, lang, state):
    if len(parts) == 1:
        state["screen"] = "language"
        text = "CON Choose language\n1 English\n2 Chichewa" if lang == "en" else "CON Sankhani chinenero\n1 Chingelezi\n2 Chichewa"
        return text, lang, state
    if len(parts) == 2 and parts[1] in ("1", "2"):
        lang = "en" if parts[1] == "1" else "ny"
        state["language"] = lang
        response = "END Language set to English." if lang == "en" else "END Chinenero chasankhidwa: Chichewa."
        return response, lang, state
    return "END Invalid option.", lang, state


def _ussd_handle_status(parts, phone, lang, state):
    response, state = _ussd_status_response(parts, phone, lang, state)
    return response, lang, state


def _ussd_handle_collection(parts, phone, lang, state):
    office = Office.objects.filter(code="MGC").first() or Office.objects.first()
    if office:
        response = _ussd_collection_response(office, lang)
    else:
        fallback = "Mangochi Immigration Office. Mon-Fri 08:00-16:00." if lang == "en" else "Ofesi ya Mangochi. Lolemba-Lachisanu, 08:00-16:00."
        response = "END " + fallback
    state["screen"] = "done"
    return response, lang, state


def _ussd_handle_language(parts, phone, lang, state):
    response, lang, state = _ussd_language_response(parts, lang, state)
    return response, lang, state


_USSD_HANDLERS = {
    "1": _ussd_handle_status,
    "2": _ussd_handle_collection,
    "3": _ussd_handle_language,
}


def ussd_endpoint(request):
    """Africa's Talking USSD callback: form fields sessionId, phoneNumber, text."""
    from django.http import HttpResponse
    if request.method != "POST":
        return HttpResponse("END Invalid request", content_type="text/plain", status=405)
    data = request.POST
    session_id = (data.get("sessionId") or data.get("session_id") or "demo").strip()[:120]
    phone = normalize_phone(data.get("phoneNumber") or data.get("phone") or "")
    text = (data.get("text") or "").strip()
    session, _ = UssdSession.objects.get_or_create(session_id=session_id, defaults={"phone": phone, "state": {"language": "en"}})
    if phone:
        session.phone = phone
    state = session.state or {"language": "en"}
    lang = state.get("language", "en")
    parts = text.split("*") if text else []
    if not parts:
        response = _ussd_menu(lang)
        state["screen"] = "menu"
    else:
        handler = _USSD_HANDLERS.get(parts[0])
        if handler is None:
            response = "END Invalid option. Dial again to start."
        else:
            response, lang, state = handler(parts, phone, lang, state)
    response = _bound_ussd(response)
    session.state = state
    session.save()
    return HttpResponse(response, content_type="text/plain; charset=utf-8")


def _ussd_collection_fields(office, lang):
    is_chichewa = lang == "ny"
    hours = (office.collection_hours_for(lang) or "").strip()
    if not hours:
        hours = "Maola sanayikidwe" if is_chichewa else "Hours not set"
    hours_text = ("Maola: " if is_chichewa else "Hours: ") + hours
    phone = (office.phone or "").strip()
    phone_text = (("Foni: " if is_chichewa else "Tel: ") + phone) if phone else ""
    if is_chichewa:
        with translation.override(lang):
            name = _(office.name)
    else:
        name = office.name
    address = (office.address or "").strip().rstrip(".,")
    verbose_prefix = "Immigration Office, along the "
    if address.startswith(verbose_prefix):
        address = address[len(verbose_prefix):]
    fields = {"name": name.strip(), "address": address, "hours": hours_text, "phone": phone_text}
    keys = [key for key in ("name", "address", "hours", "phone") if fields[key]]
    return fields, keys


def _render_ussd_collection(fields, keys):
    return "END " + ". ".join(fields[key] for key in keys) + "."


def _trim_ussd_collection_keys(fields, keys):
    for optional in ("address", "name", "phone"):
        if len(_render_ussd_collection(fields, keys)) <= 160:
            break
        if optional in keys:
            keys.remove(optional)
    return keys


def _ussd_collection_response(office, lang):
    fields, keys = _ussd_collection_fields(office, lang)
    keys = _trim_ussd_collection_keys(fields, keys)
    return _render_ussd_collection(fields, keys)


def _ussd_menu(lang):
    if lang == "ny":
        return "CON PASTNS pasipoti\n1 Fufuzani momwe ilili\n2 Zokhudza kutenga\n3 Sankhani chinenero"
    return "CON PASTNS passport\n1 Check status\n2 Collection information\n3 Change language"


def _bound_ussd(response):
    if len(response) <= 160:
        return response
    prefix = "END " if response.startswith("END ") else "CON "
    body = response[len(prefix):]
    clipped = body[:155]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return prefix + clipped.rstrip(" ,.;:") + "…"


def forbidden(request):
    return render(request, "core/forbidden.html", status=403)
