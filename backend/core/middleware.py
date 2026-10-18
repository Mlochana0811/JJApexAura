from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """New logins issued by Jay's HR must set their own password first."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if request.path.startswith("/api/") or request.path.startswith("/app/"):
            return self.get_response(request)
        if u and u.is_authenticated and u.must_change_password:
            allowed = (reverse("password_change"), reverse("logout"), "/static/", "/admin/")
            if not request.path.startswith(allowed):
                return redirect("password_change")
        return self.get_response(request)
