from http.cookies import Morsel
from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class QueryLanguageMiddleware(MiddlewareMixin):
    """Support the service-design convention `?lang=ny` and remember the choice."""
    def process_request(self, request):
        code = request.GET.get("lang")
        if code and code in dict(settings.LANGUAGES):
            translation.activate(code)
            request.LANGUAGE_CODE = code

    def process_response(self, request, response):
        code = request.GET.get("lang")
        if code and code in dict(settings.LANGUAGES):
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME, code,
                max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", 60 * 60 * 24 * 365),
                path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
                secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
                httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
                samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax"),
            )
        return response


class SessionTouchMiddleware(MiddlewareMixin):
    """Save the session for authenticated users to preserve idle timeout."""

    def process_request(self, request):
        if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
            request.session.modified = True


class PartitionedMorsel(Morsel):
    """Cookie serializer extension for Partitioned, supported by modern browsers."""
    def OutputString(self, attrs=None):
        rendered = super().OutputString(attrs)
        if getattr(self, "_pastns_partitioned", False) and "Partitioned" not in rendered:
            rendered += "; Partitioned"
        return rendered


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Security headers plus HTTPS-only third-party iframe cookie attributes."""
    COOKIE_NAMES = {"sessionid", "csrftoken", "django_language"}

    def process_response(self, request, response):
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault(
            "Content-Security-Policy",
            "frame-ancestors 'self' https://arena.ai https://*.arena.ai https://*.e2b.app",
        )
        # Modern browsers require Secure for SameSite=None and Partitioned cookies.
        # Some preview proxies terminate TLS without forwarding the scheme header;
        # the public preview host is HTTPS even if Django sees its internal hop.
        host = request.META.get("HTTP_HOST", "").split(":", 1)[0].lower()
        forwarded_proto = request.META.get("HTTP_X_FORWARDED_PROTO", "").split(",", 1)[0].strip().lower()
        embedded_https = request.is_secure() or forwarded_proto == "https" or host.endswith(".e2b.app")
        if embedded_https:
            for name in self.COOKIE_NAMES:
                morsel = response.cookies.get(name)
                if morsel:
                    upgraded = PartitionedMorsel()
                    upgraded.set(morsel.key, morsel.value, morsel.coded_value)
                    for attr, value in morsel.items():
                        upgraded[attr] = value
                    upgraded["secure"] = True
                    upgraded["samesite"] = "None"
                    upgraded._pastns_partitioned = True
                    response.cookies[name] = upgraded
        return response
