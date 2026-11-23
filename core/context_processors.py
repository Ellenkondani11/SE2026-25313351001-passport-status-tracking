from django.utils.translation import get_language


def pastns_context(request):
    return {"current_language": (get_language() or "en")[:2]}
