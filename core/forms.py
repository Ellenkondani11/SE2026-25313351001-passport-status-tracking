from django import forms
from django.contrib.auth.models import User
from .models import Office, Stage, SmsTemplate, Profile
from .utils import normalize_phone


class RegisterApplicationForm(forms.Form):
    national_id = forms.CharField(max_length=32, label="National ID")
    first_name = forms.CharField(max_length=80, label="First name")
    surname = forms.CharField(max_length=80, label="Surname")
    phone = forms.CharField(max_length=24, label="Phone number", help_text="Use +265 followed by 9 digits, or a local 09/08 number.")
    email = forms.EmailField(required=False, label="Email (optional)")
    date_of_birth = forms.DateField(required=False, label="Date of birth (optional)")
    language = forms.ChoiceField(choices=[("en", "English"), ("ny", "Chichewa")], label="Preferred language")
    application_type = forms.ChoiceField(choices=[("new", "New passport"), ("renewal", "Renewal"), ("replacement", "Replacement")], label="Application type")

    def clean_national_id(self):
        value = self.cleaned_data["national_id"].strip().upper()
        if len(value) < 5:
            raise forms.ValidationError("Enter the full National ID.")
        return value

    def clean_phone(self):
        value = normalize_phone(self.cleaned_data["phone"])
        if not value.startswith("+265") or len(value) != 13 or not value[4:].isdigit():
            raise forms.ValidationError("Enter a valid Malawi mobile number, for example +265991234567.")
        return value


class ContactCorrectionForm(forms.Form):
    phone = forms.CharField(max_length=24, label="New phone number")
    email = forms.EmailField(required=False, label="Email")
    reason = forms.CharField(max_length=240, label="Reason for correction")
    id_checked = forms.BooleanField(label="I checked the applicant's National ID in person", required=True)

    def clean_phone(self):
        value = normalize_phone(self.cleaned_data["phone"])
        if not value.startswith("+265") or len(value) != 13 or not value[4:].isdigit():
            raise forms.ValidationError("Enter a valid Malawi mobile number, for example +265991234567.")
        return value


class StageEditForm(forms.ModelForm):
    class Meta:
        model = Stage
        fields = ["name", "applicant_text_en", "applicant_text_ny", "colour", "notify"]
        widgets = {"applicant_text_en": forms.Textarea(attrs={"rows": 2}), "applicant_text_ny": forms.Textarea(attrs={"rows": 2})}


class SmsTemplateForm(forms.ModelForm):
    class Meta:
        model = SmsTemplate
        fields = ["name", "body_en", "body_ny", "is_active"]
        widgets = {"body_en": forms.Textarea(attrs={"rows": 2}), "body_ny": forms.Textarea(attrs={"rows": 2})}


class StaffCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=80)
    surname = forms.CharField(max_length=80)
    password = forms.CharField(widget=forms.PasswordInput, min_length=10)
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already in use.")
        return username
