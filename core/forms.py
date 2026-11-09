from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Application, ApplicationDocument, Deadline, Document, Profile, Requirement


DATE_INPUT = {"type": "date"}
TIME_INPUT = {"type": "time"}


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True, label="Full name")

    class Meta:
        model = User
        fields = ("first_name", "email", "username", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("full_name", "email_preferences", "timezone")


class DocumentForm(forms.ModelForm):
    MAX_FILE_SIZE = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}

    class Meta:
        model = Document
        fields = ("title", "description", "category", "file", "issue_date", "expiry_date", "expiry_warning_days")
        widgets = {"issue_date": forms.DateInput(attrs=DATE_INPUT), "expiry_date": forms.DateInput(attrs=DATE_INPUT)}

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            return uploaded_file
        extension = "." + uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
        if extension not in self.ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Upload a PDF, DOC, DOCX, JPG, JPEG, or PNG file.")
        if uploaded_file.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError("Files must be 10 MB or smaller.")
        return uploaded_file


class DeadlineForm(forms.ModelForm):
    class Meta:
        model = Deadline
        fields = ("title", "description", "due_date", "due_time", "category", "priority", "application")
        widgets = {"due_date": forms.DateInput(attrs=DATE_INPUT), "due_time": forms.TimeInput(attrs=TIME_INPUT)}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["application"].queryset = Application.objects.filter(user=user) if user else Application.objects.none()


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("title", "organization", "application_type", "application_url", "description", "deadline", "application_date", "priority", "status", "notes")
        widgets = {"deadline": forms.DateInput(attrs=DATE_INPUT), "application_date": forms.DateInput(attrs=DATE_INPUT)}


class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = ("title", "description", "is_mandatory")


class ApplicationDocumentForm(forms.ModelForm):
    class Meta:
        model = ApplicationDocument
        fields = ("document", "requirement", "document_role")

    def __init__(self, *args, user=None, application=None, **kwargs):
        super().__init__(*args, **kwargs)
        if application:
            self.instance.application = application
        self.fields["document"].queryset = Document.objects.filter(user=user) if user else Document.objects.none()
        self.fields["requirement"].queryset = application.requirements.all() if application else Requirement.objects.none()
