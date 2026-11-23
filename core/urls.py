from django.urls import path
from . import api, views

urlpatterns = [
    path("", views.public_home, name="public_home"),
    path("status/", views.public_status, name="public_status"),
    path("lookup/otp/", views.request_otp, name="request_otp"),
    path("language/", views.language_switch, name="language_switch"),
    path("ussd-demo/", views.ussd_demo, name="ussd_demo"),
    path("api/ussd/", api.UssdAPIView.as_view(), name="api_ussd"),
    path("api/applications/", api.ApplicationCreateAPIView.as_view(), name="api_applications"),
    path("api/applications/<str:code>/", api.ApplicationDetailAPIView.as_view(), name="api_application_detail"),
    path("api/applications/<str:code>/stage/", api.ApplicationStageAPIView.as_view(), name="api_application_stage"),
    path("api/sms/delivery/", api.SmsDeliveryAPIView.as_view(), name="api_sms_delivery"),
    path("officer/login/", views.officer_login, name="officer_login"),
    path("officer/logout/", views.officer_logout, name="officer_logout"),
    path("officer/", views.officer_home, name="officer_home"),
    path("officer/applications/new/", views.register_application, name="register_application"),
    path("officer/applications/bulk/", views.bulk_update, name="bulk_update"),
    path("officer/applications/<str:code>/", views.application_detail, name="application_detail"),
    path("officer/notifications/", views.notification_outbox, name="notification_outbox"),
    path("officer/reports/", views.reports, name="reports"),
    path("officer/admin/", views.admin_console, name="admin_console"),
    path("officer/audit/", views.audit_log, name="audit_log"),
    path("officer/ussd-sim/", views.officer_ussd_sim, name="officer_ussd_sim"),
]
