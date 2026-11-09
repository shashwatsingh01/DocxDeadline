from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def document_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"documents/user_{instance.user_id}/{uuid4().hex}{suffix}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=160, blank=True)
    email_preferences = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name or self.user.get_username()


class Document(models.Model):
    class Category(models.TextChoices):
        IDENTITY = "identity", "Identity"
        ACADEMIC = "academic", "Academic"
        FINANCIAL = "financial", "Financial"
        EMPLOYMENT = "employment", "Employment"
        PERSONAL = "personal", "Personal"
        OTHER = "other", "Other"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    file = models.FileField(upload_to=document_upload_path)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    expiry_warning_days = models.PositiveSmallIntegerField(default=30)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-uploaded_at",)
        indexes = [models.Index(fields=("user", "expiry_date"))]

    def clean(self):
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise ValidationError({"expiry_date": "Expiry date cannot be before the issue date."})

    @property
    def expiry_status(self):
        if not self.expiry_date:
            return "no_expiry"
        today = timezone.localdate()
        if self.expiry_date < today:
            return "expired"
        if (self.expiry_date - today).days <= self.expiry_warning_days:
            return "expiring_soon"
        return "active"

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    def __str__(self):
        return self.title


class Application(models.Model):
    class ApplicationType(models.TextChoices):
        INTERNSHIP = "internship", "Internship"
        JOB = "job", "Job"
        SCHOLARSHIP = "scholarship", "Scholarship"
        COLLEGE = "college", "College"
        COMPETITION = "competition", "Competition"
        GOVERNMENT = "government", "Government scheme"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    title = models.CharField(max_length=180)
    organization = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    application_type = models.CharField(max_length=30, choices=ApplicationType.choices, default=ApplicationType.OTHER)
    application_url = models.URLField(blank=True)
    application_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NOT_STARTED)
    priority = models.CharField(max_length=15, choices=Priority.choices, default=Priority.MEDIUM)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("deadline", "-created_at")
        indexes = [models.Index(fields=("user", "deadline")), models.Index(fields=("user", "status"))]

    @property
    def days_remaining(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.localdate()).days

    @property
    def is_active(self):
        return self.status not in {self.Status.ACCEPTED, self.Status.REJECTED, self.Status.WITHDRAWN}

    @property
    def readiness(self):
        total = self.requirements.filter(is_mandatory=True).count()
        fulfilled = self.requirements.filter(is_mandatory=True, links__isnull=False).distinct().count()
        percentage = round((fulfilled / total) * 100) if total else 100
        return {"total": total, "fulfilled": fulfilled, "missing": total - fulfilled, "percentage": percentage}

    def __str__(self):
        return f"{self.title} — {self.organization}"


class Deadline(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        PERSONAL = "personal", "Personal"
        WORK = "work", "Work"
        FINANCIAL = "financial", "Financial"
        APPLICATION = "application", "Application"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deadlines")
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True, related_name="deadlines")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    due_time = models.TimeField(null=True, blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=15, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("due_date", "due_time", "-created_at")
        indexes = [models.Index(fields=("user", "due_date")), models.Index(fields=("user", "status"))]

    @property
    def days_remaining(self):
        return (self.due_date - timezone.localdate()).days

    @property
    def is_overdue(self):
        return self.status == self.Status.PENDING and self.due_date < timezone.localdate()

    def clean(self):
        if self.application_id and self.application.user_id != self.user_id:
            raise ValidationError({"application": "The application must belong to the same user."})

    def __str__(self):
        return self.title


class Requirement(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="requirements")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_mandatory", "title")

    def __str__(self):
        return self.title


class ApplicationDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="document_links")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="application_links")
    requirement = models.ForeignKey(Requirement, on_delete=models.SET_NULL, null=True, blank=True, related_name="links")
    document_role = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("application", "document", "requirement"), name="unique_application_document_requirement")]

    def clean(self):
        if not self.application_id or not self.document_id:
            return
        application_user_id = Application.objects.filter(pk=self.application_id).values_list("user_id", flat=True).first()
        document_user_id = Document.objects.filter(pk=self.document_id).values_list("user_id", flat=True).first()
        if application_user_id != document_user_id:
            raise ValidationError("The application and document must belong to the same user.")
        if self.requirement_id and not Requirement.objects.filter(pk=self.requirement_id, application_id=self.application_id).exists():
            raise ValidationError("The requirement must belong to the selected application.")

    def __str__(self):
        return f"{self.application} / {self.document}"


class Notification(models.Model):
    class Type(models.TextChoices):
        DEADLINE_SOON = "deadline_soon", "Deadline due soon"
        DEADLINE_OVERDUE = "deadline_overdue", "Deadline overdue"
        DOCUMENT_EXPIRING = "document_expiring", "Document expiring"
        APPLICATION_SOON = "application_soon", "Application due soon"
        STATUS_UPDATE = "status_update", "Application status update"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField()
    notification_type = models.CharField(max_length=40, choices=Type.choices)
    dedupe_key = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("user", "dedupe_key"), name="unique_user_notification_key")]


class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=80)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
