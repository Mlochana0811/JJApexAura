from django import forms

from leave.models import HRRequest, LeaveRequest, LeaveType

from .access import ScopedCompanyMixin
from .models import Company, Employee

DATE = forms.DateInput(attrs={"type": "date"})


class EmployeeForm(ScopedCompanyMixin, forms.ModelForm):
    class Meta:
        model = Employee
        exclude = []
        widgets = {
            "join_date": DATE, "leave_date": DATE, "date_of_birth": DATE,
            "address": forms.Textarea(attrs={"rows": 2}), "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit_company(user)


class LeaveApplyForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "half_day", "reason"]
        widgets = {"start_date": DATE, "end_date": DATE, "reason": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        self.fields["leave_type"].queryset = LeaveType.objects.filter(company=employee.company)
        self.fields["end_date"].required = False

    def clean(self):
        d = super().clean()
        s, e = d.get("start_date"), d.get("end_date") or d.get("start_date")
        d["end_date"] = e
        if s and e and e < s:
            raise forms.ValidationError("End date cannot be before start date.")
        if s and e:
            overlap = LeaveRequest.objects.filter(
                employee=self.employee, status__in=[LeaveRequest.PENDING, LeaveRequest.APPROVED],
                start_date__lte=e, end_date__gte=s,
            )
            if overlap.exists():
                raise forms.ValidationError("You already have leave booked on these dates.")
        return d


class HRRequestForm(forms.ModelForm):
    class Meta:
        model = HRRequest
        fields = ["category", "subject", "details", "amount"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3})}


class HRResponseForm(forms.ModelForm):
    class Meta:
        model = HRRequest
        fields = ["status", "response"]
        widgets = {"response": forms.Textarea(attrs={"rows": 2})}


from .branding import STYLES  # noqa: E402
from .models import SiteTheme  # noqa: E402


class StyleOptionalMixin:
    """Page design is optional on submit – fall back to the current or 'soft' design."""

    def clean_style(self):
        return self.cleaned_data.get("style") or getattr(self.instance, "style", None) or "soft"


def hex_field(label):
    return forms.RegexField(regex=r"^#[0-9a-fA-F]{6}$", required=False, label=label,
                            widget=forms.TextInput(attrs={"type": "color"}))


class BrandingForm(StyleOptionalMixin, forms.ModelForm):
    brand_color = hex_field("Main colour")
    accent_color = hex_field("Second colour")

    def __init__(self, *args, **kwargs):
        from .branding import DEFAULT_ACCENT, DEFAULT_BRAND
        super().__init__(*args, **kwargs)
        self.fields["style"].required = False
        # Colour pickers can't be blank, so start them on the Jay's HR defaults
        self.initial.setdefault("brand_color", None)
        self.initial["brand_color"] = self.initial["brand_color"] or DEFAULT_BRAND
        self.initial["accent_color"] = self.initial.get("accent_color") or DEFAULT_ACCENT

    class Meta:
        model = Company
        fields = ["logo", "use_own_theme", "brand_color", "accent_color", "style"]
        labels = {"use_own_theme": "Use our own colours (untick for the standard Jay's HR look)"}
        widgets = {"logo": forms.FileInput(attrs={"accept": "image/png,image/jpeg"}),
                   "style": forms.RadioSelect(choices=[(k, n) for k, n, _ in STYLES])}

    def clean_logo(self):
        f = self.cleaned_data.get("logo")
        if f and hasattr(f, "size") and f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Please upload a logo under 2 MB.")
        return f


class SiteThemeForm(StyleOptionalMixin, forms.ModelForm):
    brand_color = hex_field("Main colour")
    accent_color = hex_field("Second colour")

    class Meta:
        model = SiteTheme
        fields = ["brand_color", "accent_color", "style"]
        widgets = {"style": forms.RadioSelect(choices=[(k, n) for k, n, _ in STYLES])}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["style"].required = False
