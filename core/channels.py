from dataclasses import dataclass, field
from typing import Any, List
from datetime import timedelta
from django.utils import timezone

from .models import Application


@dataclass
class StatusSnapshot:
    application: Application
    language: str = "en"

    @property
    def tracking_code(self):
        return self.application.tracking_code

    @property
    def stage_key(self):
        return self.application.current_stage.key

    @property
    def stage_name(self):
        return self.application.current_stage.name

    @property
    def stage_text(self):
        return self.application.current_stage.applicant_text(self.language)

    @property
    def status(self):
        return self.application.status


class ChannelStrategy:
    def _snapshot(self, source, language=None):
        if isinstance(source, StatusSnapshot):
            if language:
                source.language = language
            return source
        lang = language or "en"
        return StatusSnapshot(source, lang)

    def stage_name(self, source, language=None):
        return self._snapshot(source, language).stage_name

    def status_text(self, source, language=None):
        return self._snapshot(source, language).stage_text

    def render(self, source, language=None):
        snap = self._snapshot(source, language)
        text = f"{snap.tracking_code}: {snap.stage_name}. {snap.stage_text}"
        return self._bound(text)

    def _bound(self, text):
        return text


class WebChannelStrategy(ChannelStrategy):
    pass


class SmsChannelStrategy(ChannelStrategy):
    def _bound(self, text):
        return text[:160]


class UssdChannelStrategy(ChannelStrategy):
    def _bound(self, text):
        return text[:160]


@dataclass
class StageChangedEvent:
    application: Application
    from_stage: Any = None
    to_stage: Any = None
    change: Any = None
    actor: Any = None
    ip: Any = None
    reason: str = ""
    notify: bool = True
    at: Any = field(default_factory=timezone.now)


class StageObserver:
    def __init__(self):
        self.called = False
        self.last_event = None

    def update(self, event):
        self.called = True
        self.last_event = event

    def handle(self, event):
        return self.update(event)

    def on_event(self, event):
        return self.update(event)


class StageEventBus:
    def __init__(self):
        self._observers: List[StageObserver] = []

    def subscribe(self, observer):
        self._observers.append(observer)
        return observer

    def register(self, observer):
        return self.subscribe(observer)

    def attach(self, observer):
        return self.subscribe(observer)

    def add_observer(self, observer):
        return self.subscribe(observer)

    def publish(self, event):
        for observer in list(self._observers):
            observer.update(event)


class WebSyncObserver(StageObserver):
    pass


class SmsChannelObserver(StageObserver):
    def update(self, event):
        super().update(event)
        if not getattr(event, "notify", True):
            return
        from .services import notify_stage
        change = getattr(event, "change", None)
        key = f"stagechange:{change.pk}:sms" if change is not None else None
        notify_stage(event.application, event.to_stage, actor=getattr(event, "actor", None),
                     ip=getattr(event, "ip", None), idempotency_key=key)


class UssdSyncObserver(StageObserver):
    pass


class BaseNotificationDispatcher:
    def __init__(self):
        self.execution_order = []

    def dispatch(self, notification, actor=None, ip=None):
        self.execution_order = []
        self.execution_order.append("prepare")
        self.prepare(notification, actor, ip)
        self.execution_order.append("deliver")
        result = self.deliver(notification)
        self.execution_order.append("record_outcome")
        self.record_outcome(notification, result)
        self.execution_order.append("schedule_backoff")
        self.schedule_backoff(notification, result)
        self.execution_order.append("audit_dispatch")
        self.write_audit(notification, result, actor, ip)
        return notification

    def prepare(self, notification, actor=None, ip=None):
        notification.status = "queued"
        notification.error = ""
        notification.save(update_fields=["status", "error", "updated_at"])

    def deliver(self, notification):
        from .services import get_gateway
        gateway = get_gateway("email" if notification.channel == "email" else "sms")
        return gateway.send(notification)

    def record_outcome(self, notification, result):
        notification.status = result.status
        notification.provider_ref = result.provider_ref or notification.provider_ref
        notification.error = result.error
        notification.sent_at = timezone.now() if result.status in ("sent", "delivered") else None
        notification.save(update_fields=["status", "provider_ref", "error", "sent_at", "updated_at"])

    def schedule_backoff(self, notification, result):
        if result.status == "failed":
            notification.retry_count = (notification.retry_count or 0) + 1
            delay = 2 ** (notification.retry_count - 1)
            notification.next_retry_at = timezone.now() + timedelta(minutes=delay)
        else:
            notification.next_retry_at = None
        notification.save(update_fields=["retry_count", "next_retry_at", "updated_at"])

    def write_audit(self, notification, result, actor=None, ip=None):
        from .models import AuditLog
        AuditLog.objects.create(
            user=actor, action="notification_failed" if result.status == "failed" else "notification_dispatched",
            object_type="Notification", object_id=str(notification.pk),
            details={"application": notification.application.tracking_code, "channel": notification.channel,
                     "template": notification.template_key, "status": result.status},
            ip=ip,
        )


class SmsDispatchFlow(BaseNotificationDispatcher):
    pass


class EmailDispatchFlow(BaseNotificationDispatcher):
    def deliver(self, notification):
        from .services import get_gateway
        gateway = get_gateway("email")
        return gateway.send(notification)


# Default event bus with observers
default_event_bus = StageEventBus()
default_event_bus.subscribe(WebSyncObserver())
default_event_bus.subscribe(SmsChannelObserver())
default_event_bus.subscribe(UssdSyncObserver())
