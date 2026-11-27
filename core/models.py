import hashlib
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Office(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=100)
    district = models.CharField(max_length=80, default="Mangochi")
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=240, blank=True)
    collection_hours = models.CharField(max_length=120, default="Monday–Friday, 08:00–16:00")
    collection_hours_ny = models.CharField(max_length=120, default="Lolemba–Lachisanu, 08:00–16:00")

    def collection_hours_for(self, language="en"):
        return self.collection_hours_ny if language == "ny" else self.collection_hours

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Profile(models.Model):
    ROLE_CHOICES = [("officer", _("Officer")), ("supervisor", _("Supervisor")), ("admin", _("Administrator"))]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="officer")

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"


class Applicant(models.Model):
    LANGUAGE_CHOICES = [("en", _("English")), ("ny", _("Chichewa"))]
    national_id = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=80)
    surname = models.CharField(max_length=80)
    phone = models.CharField(
        max_length=24,
        validators=[RegexValidator(r"^\+265[0-9]{9}$", "Use an E.164 Malawi number, e.g. +265991234567.")],
    )
    email = models.EmailField(blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["surname", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.surname}"

    @property
    def masked_national_id(self):
        value = self.national_id or ""
        return "••••" + value[-4:] if len(value) > 4 else "••••"

    @property
    def masked_phone(self):
        digits = self.phone or ""
        if digits.startswith("+265") and len(digits) == 13:
            return f"+265 {digits[4:6]}* *** {digits[-3:]}"
        return f"{digits[:4]} *** {digits[-3:]}" if len(digits) >= 10 else "••••"


class Stage(models.Model):
    key = models.SlugField(max_length=32, unique=True)
    order = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=60)
    applicant_text_en = models.CharField(max_length=280)
    applicant_text_ny = models.CharField(max_length=280)
    colour = models.CharField(max_length=20, default="grey")
    notify = models.BooleanField(default=True)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    def applicant_text(self, language="en"):
        return self.applicant_text_ny if language == "ny" else self.applicant_text_en


class Application(models.Model):
    TYPE_CHOICES = [("new", _("New passport")), ("renewal", _("Renewal")), ("replacement", _("Replacement"))]
    STATUS_CHOICES = [
        ("active", _("Active")), ("on_hold", _("On hold")),
        ("collected", _("Collected")), ("rejected", _("Rejected")),
    ]
    tracking_code = models.CharField(max_length=40, unique=True)
    applicant = models.ForeignKey(Applicant, on_delete=models.PROTECT, related_name="applications")
    office = models.ForeignKey(Office, on_delete=models.PROTECT, related_name="applications")
    application_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default="new")
    current_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="applications")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    received_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    previous_stage = models.ForeignKey(
        Stage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="held_applications",
    )

    class Meta:
        ordering = ["-updated_at", "tracking_code"]
        indexes = [models.Index(fields=["office", "status", "current_stage"]), models.Index(fields=["received_at"])]

    def __str__(self):
        return self.tracking_code

    @property
    def days_in_stage(self):
        last = self.stage_changes.filter(to_stage=self.current_stage).order_by("-at").first()
        start = last.at if last else self.received_at
        return max(0, (timezone.now().date() - start.date()).days)

    @property
    def next_stage(self):
        if self.status != "active":
            return None
        return Stage.objects.filter(
            order__gt=self.current_stage.order,
            key__in=["under_review", "approved", "printed", "ready"],
        ).order_by("order").first()

    @property
    def last_notification(self):
        return self.notifications.order_by("-created_at").first()

    def get_absolute_url(self):
        return f"/officer/applications/{self.tracking_code}/"


class StageChange(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="stage_changes")
    from_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, null=True, blank=True, related_name="changes_from")
    to_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="changes_to")
    by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=240, blank=True)
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["at", "id"]


class Notification(models.Model):
    CHANNEL_CHOICES = [("sms", _("SMS")), ("email", _("Email")), ("ussd", _("USSD"))]
    STATUS_CHOICES = [
        ("queued", _("Queued")), ("sent", _("Sent")),
        ("delivered", _("Delivered")), ("failed", _("Failed")),
    ]
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES, default="sms")
    to = models.CharField(max_length=254)
    template_key = models.CharField(max_length=48)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="queued")
    provider_ref = models.CharField(max_length=160, blank=True)
    error = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=5)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.channel} {self.status} for {self.application.tracking_code}"


class SmsTemplate(models.Model):
    key = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=80)
    body_en = models.CharField(max_length=320)
    body_ny = models.CharField(max_length=320)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def body_for(self, language="en"):
        return self.body_ny if language == "ny" else self.body_en

    def __str__(self):
        return self.name


class UssdSession(models.Model):
    session_id = models.CharField(max_length=120, primary_key=True)
    phone = models.CharField(max_length=32)
    state = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    reason = models.CharField(max_length=240, blank=True)
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    entry_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-at", "-id"]

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit log entries are immutable.")
        if not self.pk:
            from .audit_chain import compute_entry_hash
            self.prev_hash, self.entry_hash = compute_entry_hash(self)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log entries are immutable.")


class LookupOtp(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="lookup_otps")
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"OTP for {self.application.tracking_code}"


class LookupAttempt(models.Model):
    national_id_hash = models.CharField(max_length=64, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    success = models.BooleanField(default=False)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["national_id_hash", "at"]),
            models.Index(fields=["ip", "at"]),
        ]


class LoginAttempt(models.Model):
    username_hash = models.CharField(max_length=64, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    success = models.BooleanField(default=False)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["username_hash", "at"])]


def hash_sensitive(value):
    """One-way SHA-256 helper for lookup/audit identifiers (never log raw IDs)."""
    return hashlib.sha256((settings.SECRET_KEY + str(value).strip().lower()).encode("utf-8")).hexdigest()


class OfficerNote(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.CharField(max_length=600)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
