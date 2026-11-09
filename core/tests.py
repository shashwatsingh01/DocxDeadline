from datetime import date, timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Activity, Application, ApplicationDocument, Deadline, Document, Notification, Requirement
from .services import create_notification


class DocxDeadlineTestCase(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.user = User.objects.create_user(username="asha", email="asha@example.com", password="A secure password 123", first_name="Asha")
        self.other_user = User.objects.create_user(username="other", password="A secure password 123")
        self.client.login(username="asha", password="A secure password 123")

    def upload(self, name="passport.pdf", content=b"%PDF-1.4 test"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")


class AuthenticationTests(DocxDeadlineTestCase):
    def test_registration_creates_user_profile_and_logs_in(self):
        self.client.logout()
        response = self.client.post(reverse("register"), {
            "first_name": "Neha", "email": "neha@example.com", "username": "neha",
            "password1": "A secure password 123", "password2": "A secure password 123",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(User.objects.get(username="neha").profile.full_name, "Neha")

    def test_protected_pages_require_login(self):
        self.client.logout()
        for route in ("dashboard", "document_list", "deadline_list", "application_list", "calendar", "notification_list", "activity", "settings"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 302, route)


class DeadlineTests(DocxDeadlineTestCase):
    def test_create_complete_and_delete_deadline(self):
        response = self.client.post(reverse("deadline_create"), {"title": "Submit form", "description": "Details", "due_date": (date.today() + timedelta(days=2)).isoformat(), "due_time": "10:30", "category": "academic", "priority": "high", "application": ""})
        deadline = Deadline.objects.get(title="Submit form")
        self.assertRedirects(response, reverse("deadline_detail", args=[deadline.pk]))
        self.assertEqual(deadline.user, self.user)
        response = self.client.post(reverse("deadline_toggle_complete", args=[deadline.pk]), {"next": "deadline_list"})
        deadline.refresh_from_db()
        self.assertEqual(deadline.status, Deadline.Status.COMPLETED)
        self.assertRedirects(response, reverse("deadline_list"))
        response = self.client.post(reverse("deadline_delete", args=[deadline.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Deadline.objects.filter(pk=deadline.pk).exists())

    def test_deadline_filters_and_owner_isolation(self):
        deadline = Deadline.objects.create(user=self.other_user, title="Private", due_date=date.today())
        self.assertEqual(self.client.get(reverse("deadline_detail", args=[deadline.pk])).status_code, 404)
        Deadline.objects.create(user=self.user, title="Overdue", due_date=date.today() - timedelta(days=1))
        response = self.client.get(reverse("deadline_list") + "?status=overdue")
        self.assertContains(response, "Overdue")
        self.assertNotContains(response, "Private")


class DocumentTests(DocxDeadlineTestCase):
    def test_upload_download_expiry_and_delete(self):
        response = self.client.post(reverse("document_create"), {"title": "Passport", "description": "Identity", "category": "identity", "file": self.upload(), "issue_date": date.today().isoformat(), "expiry_date": (date.today() + timedelta(days=5)).isoformat(), "expiry_warning_days": 30})
        document = Document.objects.get(title="Passport")
        self.assertRedirects(response, reverse("document_detail", args=[document.pk]))
        self.assertEqual(document.expiry_status, "expiring_soon")
        download = self.client.get(reverse("document_download", args=[document.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download["Content-Disposition"].startswith("attachment"))
        self.assertEqual(self.client.post(reverse("document_delete", args=[document.pk])).status_code, 302)
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())

    def test_rejects_invalid_file_and_blocks_cross_user_access(self):
        response = self.client.post(reverse("document_create"), {"title": "Executable", "category": "other", "file": self.upload("virus.exe")})
        self.assertContains(response, "Upload a PDF", status_code=200)
        private_document = Document.objects.create(user=self.other_user, title="Other", category=Document.Category.OTHER, file=self.upload("other.pdf"))
        self.assertEqual(self.client.get(reverse("document_download", args=[private_document.pk])).status_code, 404)


class ApplicationTests(DocxDeadlineTestCase):
    def test_application_requirements_and_document_readiness(self):
        application = Application.objects.create(user=self.user, title="Research internship", organization="Lab", deadline=date.today() + timedelta(days=10))
        document = Document.objects.create(user=self.user, title="Resume", category=Document.Category.EMPLOYMENT, file=self.upload("resume.pdf"))
        requirement = Requirement.objects.create(application=application, title="Resume")
        response = self.client.post(reverse("application_document_attach", args=[application.pk]), {"document": document.pk, "requirement": requirement.pk, "document_role": "Resume"})
        self.assertRedirects(response, reverse("application_detail", args=[application.pk]))
        self.assertEqual(application.readiness["percentage"], 100)
        link = ApplicationDocument.objects.get(application=application, document=document)
        self.client.post(reverse("application_document_unlink", args=[application.pk, link.pk]))
        self.assertFalse(ApplicationDocument.objects.filter(pk=link.pk).exists())
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())

    def test_application_deadline_appears_in_calendar_and_updates(self):
        application = Application.objects.create(user=self.user, title="Scholarship", organization="Foundation", deadline=date.today() + timedelta(days=4))
        response = self.client.get(reverse("calendar_events") + f"?month={date.today():%Y-%m}")
        self.assertEqual(response.json()["events"][0]["id"], f"application-{application.pk}")
        application.deadline = date.today() + timedelta(days=20)
        application.save()
        self.assertEqual(self.client.get(reverse("calendar_events") + f"?month={(date.today() + timedelta(days=1)):%Y-%m}").status_code, 200)


class DashboardAndNotificationTests(DocxDeadlineTestCase):
    def test_private_pages_render(self):
        document = Document.objects.create(user=self.user, title="Identity", category=Document.Category.IDENTITY, file=self.upload())
        application = Application.objects.create(user=self.user, title="Opportunity", organization="Org", deadline=date.today() + timedelta(days=5))
        deadline = Deadline.objects.create(user=self.user, title="Follow up", due_date=date.today(), application=application)
        for route, kwargs in (
            ("dashboard", {}), ("document_list", {}), ("document_detail", {"pk": document.pk}),
            ("deadline_list", {}), ("deadline_detail", {"pk": deadline.pk}), ("application_list", {}),
            ("application_detail", {"pk": application.pk}), ("calendar", {}), ("notification_list", {}), ("activity", {}),
        ):
            response = self.client.get(reverse(route, kwargs=kwargs))
            self.assertEqual(response.status_code, 200, route)

    def test_dashboard_statistics_use_real_records(self):
        Deadline.objects.create(user=self.user, title="Pending", due_date=date.today())
        Deadline.objects.create(user=self.user, title="Done", due_date=date.today(), status=Deadline.Status.COMPLETED)
        Document.objects.create(user=self.user, title="ID", category=Document.Category.IDENTITY, file=self.upload())
        Application.objects.create(user=self.user, title="Job", organization="Company")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["documents_count"], 1)
        self.assertEqual(response.context["applications_count"], 1)
        self.assertEqual(response.context["pending_deadlines_count"], 1)
        self.assertEqual(response.context["completed_deadlines_count"], 1)

    def test_notification_deduplication(self):
        first = create_notification(self.user, "Title", "Message", Notification.Type.DEADLINE_SOON, "deadline-1")
        second = create_notification(self.user, "Changed", "Changed", Notification.Type.DEADLINE_SOON, "deadline-1")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.filter(user=self.user, dedupe_key="deadline-1").count(), 1)

    def test_activity_is_owned_by_user(self):
        Activity.objects.create(user=self.other_user, action="Private", description="Not mine")
        response = self.client.get(reverse("activity"))
        self.assertNotContains(response, "Not mine")
