from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser
from rest_framework.renderers import BaseRenderer
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes
from .models import Applicant, Application, AuditLog, Notification, Office, Profile, Stage, StageChange
from .services import notify_stage
from .services import transition_application_stage
from .utils import audit, client_ip, mask_phone, normalize_phone, tracking_code_for


class ApplicationCreateSerializer(serializers.Serializer):
    national_id = serializers.CharField(max_length=32)
    first_name = serializers.CharField(max_length=80)
    surname = serializers.CharField(max_length=80)
    phone = serializers.CharField(max_length=24)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    language = serializers.ChoiceField(choices=["en", "ny"], default="en")
    application_type = serializers.ChoiceField(choices=["new", "renewal", "replacement"], default="new")

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not phone.startswith("+265") or len(phone) != 13 or not phone[4:].isdigit():
            raise serializers.ValidationError("Use a valid Malawi mobile number, e.g. +265991234567.")
        return phone


class ApplicationReadSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    phone_masked = serializers.SerializerMethodField()
    stage = serializers.CharField(source="current_stage.key")
    stage_name = serializers.CharField(source="current_stage.name")
    office = serializers.CharField(source="office.code")
    notifications = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ["tracking_code", "applicant_name", "phone_masked", "application_type", "stage", "stage_name", "status", "office", "received_at", "updated_at", "notifications"]

    def get_applicant_name(self, obj) -> str:
        return f"{obj.applicant.first_name} {obj.applicant.surname}"

    def get_phone_masked(self, obj) -> str:
        return mask_phone(obj.applicant.phone)

    def get_notifications(self, obj) -> list[dict]:
        return [{"channel": row.channel, "status": row.status, "created_at": row.created_at, "provider_ref": row.provider_ref} for row in obj.notifications.order_by("-created_at")[:10]]



class StageUpdateSerializer(serializers.Serializer):
    stage = serializers.CharField(max_length=32)
    reason = serializers.CharField(max_length=240, required=False, allow_blank=True)


class DeliveryCallbackSerializer(serializers.Serializer):
    notification_id = serializers.IntegerField(required=False)
    notificationId = serializers.IntegerField(required=False)
    provider_ref = serializers.CharField(required=False, allow_blank=True)
    messageId = serializers.CharField(required=False, allow_blank=True)
    id = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    deliveryStatus = serializers.CharField(required=False, allow_blank=True)
    failureReason = serializers.CharField(required=False, allow_blank=True)
    error = serializers.CharField(required=False, allow_blank=True)


class UssdRequestSerializer(serializers.Serializer):
    sessionId = serializers.CharField(max_length=120)
    serviceCode = serializers.CharField(max_length=32, required=False, allow_blank=True)
    phoneNumber = serializers.CharField(max_length=32)
    text = serializers.CharField(max_length=500, required=False, allow_blank=True)


def api_office_for(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return None
    if profile.office_id:
        return profile.office
    if profile.role == "admin":
        return Office.objects.first()
    return None


class ApplicationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ApplicationCreateSerializer, responses={201: ApplicationReadSerializer})
    def post(self, request):
        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        office = api_office_for(request.user)
        if not office:
            return Response({"detail": "Your account is not assigned to an office."}, status=403)
        data = serializer.validated_data
        with transaction.atomic():
            applicant, created = Applicant.objects.get_or_create(national_id=data["national_id"].strip().upper(), defaults={
                "first_name": data["first_name"], "surname": data["surname"], "phone": data["phone"], "email": data.get("email", ""), "language": data["language"], "date_of_birth": data.get("date_of_birth"),
            })
            if not created:
                applicant.first_name = data["first_name"]
                applicant.surname = data["surname"]
                applicant.phone = data["phone"]
                applicant.email = data.get("email", "")
                applicant.language = data["language"]
                applicant.date_of_birth = data.get("date_of_birth")
                applicant.save()
            stage = Stage.objects.get(key="received")
            app = Application.objects.create(tracking_code=tracking_code_for(office), applicant=applicant, office=office, application_type=data["application_type"], current_stage=stage)
            StageChange.objects.create(application=app, from_stage=None, to_stage=stage, by_user=request.user, reason="Registered through API")
            notify_stage(app, stage, actor=request.user, ip=client_ip(request._request))
            audit(request._request, "application_registered_api", app, {"stage": stage.key})
        return Response(ApplicationReadSerializer(app).data, status=status.HTTP_201_CREATED)


class ApplicationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        qs = Application.objects.select_related("applicant", "office", "current_stage")
        profile = getattr(request.user, "profile", None)
        if profile and profile.role == "admin" and not profile.office_id:
            return qs
        if profile and profile.office_id:
            return qs.filter(office_id=profile.office_id)
        return qs.none()

    @extend_schema(responses={200: ApplicationReadSerializer})
    def get(self, request, code):
        app = get_object_or_404(self.get_queryset(request), tracking_code=code)
        return Response(ApplicationReadSerializer(app).data)


class ApplicationStageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=StageUpdateSerializer, responses={200: ApplicationReadSerializer})
    def put(self, request, code):
        app = get_object_or_404(Application.objects.select_related("current_stage", "office"), tracking_code=code)
        profile = getattr(request.user, "profile", None)
        if not _api_can_access(profile, app):
            return Response({"detail": "Application is outside your office."}, status=403)
        target = Stage.objects.filter(key=request.data.get("stage")).first()
        if not target:
            return Response({"stage": "Unknown stage."}, status=400)
        reason = str(request.data.get("reason", "")).strip()
        validation_error = _api_validate_transition(app, target, profile, reason)
        if validation_error is not None:
            return validation_error
        old_key = app.current_stage.key
        transition_application_stage(
            app, target, actor=request.user, reason=reason or "Updated through API",
            ip=client_ip(request._request),
        )
        audit(request._request, "stage_changed_api", app, {"from": old_key, "to": target.key, "reason": reason[:160]})
        return Response(ApplicationReadSerializer(app).data)


def _api_can_access(profile, app):
    if not profile:
        return False
    if profile.office_id and profile.office_id != app.office_id:
        return False
    if not profile.office_id and profile.role != "admin":
        return False
    return True


def _api_validate_transition(app, target, profile, reason):
    if target.key == "on_hold" and not reason:
        return Response({"reason": "A reason is required to put an application on hold."}, status=400)
    if target.key == "rejected":
        if profile.role not in ("supervisor", "admin"):
            return Response({"detail": "A supervisor role is required to reject an application."}, status=403)
        if not reason:
            return Response({"reason": "A reason is required."}, status=400)
    if target.key == "collected":
        if app.current_stage.key != "ready" and profile.role not in ("supervisor", "admin"):
            return Response({"detail": "A passport must be ready before it can be collected."}, status=403)
    next_stage = app.next_stage
    is_next = bool(next_stage and target.pk == next_stage.pk)
    if target.key != "on_hold" and not is_next:
        if profile.role not in ("supervisor", "admin"):
            return Response({"detail": "A supervisor role is required to skip or move back."}, status=403)
        if not reason:
            return Response({"reason": "A reason is required."}, status=400)
    return None


class SmsDeliveryAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=DeliveryCallbackSerializer, responses={200: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Delivery status recorded.")})
    def post(self, request):
        secret = settings.SMS_CALLBACK_TOKEN
        if secret and request.headers.get("X-Callback-Token") != secret:
            return Response({"detail": "Invalid callback token."}, status=403)
        provider_ref = _callback_provider_ref(request)
        raw_status = _callback_raw_status(request)
        row = _callback_find_notification(request, provider_ref)
        if not row:
            return Response({"detail": "Notification not found."}, status=404)
        _callback_apply_status(row, raw_status, request)
        row.save(update_fields=["status", "error", "updated_at"])
        AuditLog.objects.create(
            user=None, action="sms_delivery_callback", object_type="Notification",
            object_id=str(row.pk), details={"provider_ref": provider_ref, "status": row.status},
            ip=client_ip(request._request),
        )
        return Response({"ok": True, "notification_id": row.pk, "status": row.status})


def _callback_provider_ref(request):
    return str(request.data.get("provider_ref") or request.data.get("messageId") or request.data.get("id") or "")


def _callback_raw_status(request):
    return str(request.data.get("status") or request.data.get("deliveryStatus") or "").lower()


def _callback_find_notification(request, provider_ref):
    row = None
    if request.data.get("notification_id") or request.data.get("notificationId"):
        row = Notification.objects.filter(pk=request.data.get("notification_id") or request.data.get("notificationId")).first()
    if not row and provider_ref:
        row = Notification.objects.filter(provider_ref=provider_ref).first()
    return row


def _callback_apply_status(row, raw_status, request):
    if any(word in raw_status for word in ("deliver", "success", "sent")):
        row.status = "delivered"
        row.error = ""
    elif any(word in raw_status for word in ("fail", "undeliver", "reject", "error")):
        row.status = "failed"
        row.error = str(request.data.get("failureReason") or request.data.get("error") or "Delivery failed")[:500]
    else:
        row.status = "queued"


class PlainTextRenderer(BaseRenderer):
    media_type = "text/plain"
    format = "txt"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data.encode(self.charset) if isinstance(data, str) else data


class UssdAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser]
    renderer_classes = [PlainTextRenderer]
    serializer_class = UssdRequestSerializer

    @extend_schema(
        request=UssdRequestSerializer,
        responses={200: OpenApiResponse(response=OpenApiTypes.STR, description="Plain-text CON or END response, at most 160 characters.")},
    )
    def get(self, request):
        from django.http import HttpResponse
        return HttpResponse("END Invalid request", content_type="text/plain; charset=utf-8", status=405)

    def post(self, request):
        # Reuse the exact callback implementation used by the browser simulator.
        from .views import ussd_endpoint
        return ussd_endpoint(request._request)
