from .models import SiteTheme


def theme(request):
    """Clients and their staff see their company's theme; Jay's HR admins see the default."""
    u = getattr(request, "user", None)
    company = getattr(u, "company", None) if u and u.is_authenticated and not u.is_hr_admin else None
    return {
        "theme": company.theme() if company else SiteTheme.current().theme(),
        "brand_company": company,
    }
