import logging
from dataclasses import dataclass
from django.conf import settings
from django.core.mail import send_mail
import requests
from . import channels
from .models import AuditLog, Notification, SmsTemplate, StageChange

logger = logging.getLogger("pastns.notifications")


@dataclass
class GatewayResult:
    status: str
    provider_ref: str = ""
    error: str = ""


class NotificationGateway:
    """Dispatcher seam: replace this class with an asynchronous dispatcher in production."""
    def send(self, notification: Notification) -> GatewayResult:
        raise NotImplementedError


class ConsoleGateway(NotificationGateway):
    """Safe demo gateway: stores the exact message and marks it simulated-sent."""
    def send(self, notification):
        logger.info("PASTNS DEMO SMS to %s: %s", notification.to, notification.body)
        return GatewayResult("sent", provider_ref="console-demo")


class AfricasTalkingGateway(NotificationGateway):
    def _endpoint(self):
        base = settings.AT_BASE_URL
        if settings.AT_USERNAME == "sandbox" and base == "https://api.africastalking.com/version1/messaging":
            return "https://api.sandbox.africastalking.com/version1/messaging"
        return base

    def send(self, notification):
        if not settings.AT_USERNAME or not settings.AT_API_KEY:
            return GatewayResult("failed", error="Africa's Talking credentials are not configured.")
        headers = {"apiKey": settings.AT_API_KEY, "Accept": "application/json"}
        data = {"username": settings.AT_USERNAME, "to": notification.to, "message": notification.body}
        if settings.AT_SENDER_ID:
            data["from"] = settings.AT_SENDER_ID
        try:
            response = requests.post(self._endpoint(), headers=headers, data=data, timeout=12)
            response.raise_for_status()
            payload = response.json()
            recipients = payload.get("SMSMessageData", {}).get("Recipients", [])
            if recipients and recipients[0].get("statusCode") in (100, 101, 102):
                return GatewayResult("sent", provider_ref=recipients[0].get("messageId", ""))
            detail = (
                recipients[0].get("status", "Provider did not accept the message")
                if recipients else "Provider returned no recipient result"
            )
            return GatewayResult("failed", error=str(detail))
        except (requests.RequestException, ValueError) as exc:
            return GatewayResult("failed", error=str(exc)[:500])


class SMTPGateway(NotificationGateway):
    def send(self, notification):
        try:
            send_mail(
                subject=f"Passport application update: {notification.application.tracking_code}",
                message=notification.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.to],
                fail_silently=False,
            )
            return GatewayResult("sent", provider_ref="smtp")
        except Exception as exc:  # noqa: BLE001 - record and show provider errors in outbox
            return GatewayResult("failed", error=str(exc)[:500])


def get_gateway(channel="sms"):
    if channel == "email":
        return SMTPGateway()
    if settings.PASTNS_SMS_GATEWAY == "africastalking":
        return AfricasTalkingGateway()
    return ConsoleGateway()


def render_message(application, event):
    key = getattr(event, "key", None) or str(event)
    template = SmsTemplate.objects.filter(key=key, is_active=True).first()
    language = application.applicant.language or "en"
    if template:
        text = template.body_for(language)
    else:
        text = "Immigration: {code} status updated at {office}. Check *384*123#."
    data = {
        "code": application.tracking_code,
        "office": application.office.name,
        "url": "pastns.gov.mw",
        "hours": application.office.collection_hours_for(language),
    }
    try:
        return text.format_map(data)
    except (KeyError, ValueError):
        return text


def send_notification(notification, actor=None, ip=None):
    """Send an existing outbox row, persist provider outcome, and audit it."""
    if notification.channel == "email":
        flow = channels.EmailDispatchFlow()
    else:
        flow = channels.SmsDispatchFlow()
    return flow.dispatch(notification, actor=actor, ip=ip)


def notify(application, event, channel="sms", actor=None, ip=None, idempotency_key=None):
    """Synchronous notification: create outbox row, then call the selected gateway."""
    key = getattr(event, "key", None) or str(event)
    if idempotency_key:
        existing = Notification.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing
    if channel == "email":
        destination = application.applicant.email
        if not destination:
            return None
    else:
        destination = application.applicant.phone
    row = Notification.objects.create(
        application=application,
        channel=channel,
        to=destination,
        template_key=key,
        body=render_message(application, key),
        status="queued",
        idempotency_key=idempotency_key,
    )
    return send_notification(row, actor=actor, ip=ip)


def retry_notification(notification, actor=None, ip=None):
    return send_notification(notification, actor=actor, ip=ip)


def transition_application_stage(
    application, target_stage, actor=None, reason="", new_status=None, ip=None, notify=True,
):
    old = application.current_stage
    application.current_stage = target_stage
    if new_status:
        application.status = new_status
    elif target_stage.key == "collected":
        application.status = "collected"
    elif target_stage.key == "rejected":
        application.status = "rejected"
    elif target_stage.key == "on_hold":
        application.status = "on_hold"
    else:
        application.status = "active"
    if target_stage.key == "on_hold":
        if application.previous_stage is None:
            application.previous_stage = old
    else:
        application.previous_stage = None
    application.save()
    change = StageChange.objects.create(
        application=application, from_stage=old, to_stage=target_stage,
        by_user=actor, reason=(reason or "")[:240],
    )
    AuditLog.objects.create(
        user=actor, action="stage_changed", object_type="Application",
        object_id=str(application.pk),
        details={"from": getattr(old, "key", None), "to": target_stage.key, "reason": (reason or "")[:160]},
        ip=ip, reason=(reason or "")[:240],
    )
    event = channels.StageChangedEvent(
        application=application, from_stage=old, to_stage=target_stage,
        change=change, actor=actor, ip=ip, reason=reason, notify=notify,
    )
    channels.default_event_bus.publish(event)
    return application, change


def resend_last_notification(application, actor=None, ip=None):
    last = application.notifications.order_by("-created_at").first()
    if not last:
        return None
    destination = application.applicant.email if last.channel == "email" else application.applicant.phone
    if not destination:
        return None
    row = Notification.objects.create(
        application=application, channel=last.channel, to=destination,
        template_key=last.template_key, body=render_message(application, last.template_key), status="queued",
    )
    return send_notification(row, actor=actor, ip=ip)


def notify_stage(application, stage, actor=None, ip=None, idempotency_key=None):
    if not stage.notify:
        return None
    return notify(application, stage.key, actor=actor, ip=ip, idempotency_key=idempotency_key)
