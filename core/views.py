import calendar
import mimetypes
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationDocumentForm, ApplicationForm, DeadlineForm, DocumentForm, ProfileForm, RegistrationForm, RequirementForm
from .models import Activity, Application, ApplicationDocument, Deadline, Document, Notification, Requirement
from .services import log_activity, refresh_user_notifications


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "core/landing.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your private workspace is ready.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


def _day_label(days):
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    if days < 0:
        return f"{abs(days)}d overdue"
    return f"{days}d left"


@login_required
def dashboard(request):
    user = request.user
    refresh_user_notifications(user)
    today = timezone.localdate()
    deadlines = Deadline.objects.filter(user=user)
    applications = Application.objects.filter(user=user)
    expiring_documents_count = sum(1 for document in Document.objects.filter(user=user, expiry_date__isnull=False) if document.expiry_status == "expiring_soon")
    context = {
        "today": today,
        "documents_count": Document.objects.filter(user=user).count(),
        "applications_count": applications.count(),
        "pending_deadlines_count": deadlines.filter(status=Deadline.Status.PENDING).count(),
        "completed_deadlines_count": deadlines.filter(status=Deadline.Status.COMPLETED).count(),
        "overdue_deadlines_count": deadlines.filter(status=Deadline.Status.PENDING, due_date__lt=today).count(),
        "expiring_documents_count": expiring_documents_count,
        "upcoming_deadlines": deadlines.filter(status=Deadline.Status.PENDING, due_date__gte=today).select_related("application")[:6],
        "overdue_deadlines": deadlines.filter(status=Deadline.Status.PENDING, due_date__lt=today).select_related("application")[:4],
        "upcoming_applications": applications.filter(deadline__gte=today).exclude(status__in=[Application.Status.ACCEPTED, Application.Status.REJECTED, Application.Status.WITHDRAWN])[:5],
        "recent_documents": Document.objects.filter(user=user)[:5],
        "recent_activity": Activity.objects.filter(user=user)[:6],
    }
    return render(request, "core/dashboard.html", context)


@login_required
def document_list(request):
    documents = Document.objects.filter(user=request.user)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    expiry = request.GET.get("expiry", "")
    sort = request.GET.get("sort", "-uploaded_at")
    if query:
        documents = documents.filter(title__icontains=query) | documents.filter(description__icontains=query)
    if category:
        documents = documents.filter(category=category)
    today = timezone.localdate()
    if expiry == "expired":
        documents = documents.filter(expiry_date__lt=today)
    elif expiry == "expiring":
        documents = documents.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
    elif expiry == "active":
        documents = documents.filter(expiry_date__gt=today + timedelta(days=30))
    if sort not in {"-uploaded_at", "uploaded_at", "expiry_date", "-expiry_date", "title"}:
        sort = "-uploaded_at"
    documents = documents.order_by(sort)
    return render(request, "core/documents/list.html", {"documents": documents, "query": query, "category": category, "expiry": expiry, "sort": sort, "categories": Document.Category.choices})


@login_required
def document_create(request):
    form = DocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.user = request.user
        document.save()
        log_activity(request.user, "Document uploaded", f"Uploaded {document.title}.")
        messages.success(request, "Document added to your vault.")
        return redirect("document_detail", pk=document.pk)
    return render(request, "core/documents/form.html", {"form": form, "heading": "Add document", "submit_label": "Upload document"})


@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    return render(request, "core/documents/detail.html", {"document": document})


@login_required
def document_edit(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    form = DocumentForm(request.POST or None, request.FILES or None, instance=document)
    form.fields["file"].required = False
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "Document updated", f"Updated {document.title}.")
        messages.success(request, "Document details updated.")
        return redirect("document_detail", pk=document.pk)
    return render(request, "core/documents/form.html", {"form": form, "heading": "Edit document", "submit_label": "Save changes", "document": document})


@login_required
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == "POST":
        title = document.title
        document.file.delete(save=False)
        document.delete()
        log_activity(request.user, "Document deleted", f"Deleted {title}.")
        messages.success(request, "Document deleted.")
        return redirect("document_list")
    return render(request, "core/confirm_delete.html", {"object": document, "object_type": "document", "cancel_url": reverse("document_detail", args=[document.pk])})


@login_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    content_type, _ = mimetypes.guess_type(document.file.name)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.rsplit("/", 1)[-1], content_type=content_type or "application/octet-stream")


@login_required
def deadline_list(request):
    deadlines = Deadline.objects.filter(user=request.user).select_related("application")
    status = request.GET.get("status", "all")
    priority = request.GET.get("priority", "")
    sort = request.GET.get("sort", "due_date")
    if status == "pending":
        deadlines = deadlines.filter(status=Deadline.Status.PENDING)
    elif status == "completed":
        deadlines = deadlines.filter(status=Deadline.Status.COMPLETED)
    elif status == "overdue":
        deadlines = deadlines.filter(status=Deadline.Status.PENDING, due_date__lt=timezone.localdate())
    if priority == "high":
        deadlines = deadlines.filter(priority=Deadline.Priority.HIGH)
    if sort not in {"due_date", "-due_date", "priority", "-created_at"}:
        sort = "due_date"
    deadlines = deadlines.order_by(sort)
    return render(request, "core/deadlines/list.html", {"deadlines": deadlines, "status": status, "priority": priority, "sort": sort})


@login_required
def deadline_create(request):
    initial = {}
    if request.method == "GET":
        if request.GET.get("due_date"):
            initial["due_date"] = request.GET["due_date"]
        if request.GET.get("application") and Application.objects.filter(pk=request.GET["application"], user=request.user).exists():
            initial["application"] = request.GET["application"]
    form = DeadlineForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        deadline = form.save(commit=False)
        deadline.user = request.user
        deadline.full_clean()
        deadline.save()
        log_activity(request.user, "Deadline created", f"Created {deadline.title}.")
        messages.success(request, "Deadline created.")
        return redirect("deadline_detail", pk=deadline.pk)
    return render(request, "core/deadlines/form.html", {"form": form, "heading": "Create deadline", "submit_label": "Create deadline"})


@login_required
def deadline_detail(request, pk):
    deadline = get_object_or_404(Deadline.objects.select_related("application"), pk=pk, user=request.user)
    return render(request, "core/deadlines/detail.html", {"deadline": deadline, "day_label": _day_label(deadline.days_remaining)})


@login_required
def deadline_edit(request, pk):
    deadline = get_object_or_404(Deadline, pk=pk, user=request.user)
    form = DeadlineForm(request.POST or None, instance=deadline, user=request.user)
    if request.method == "POST" and form.is_valid():
        deadline = form.save(commit=False)
        deadline.user = request.user
        deadline.full_clean()
        deadline.save()
        log_activity(request.user, "Deadline updated", f"Updated {deadline.title}.")
        messages.success(request, "Deadline updated.")
        return redirect("deadline_detail", pk=deadline.pk)
    return render(request, "core/deadlines/form.html", {"form": form, "heading": "Edit deadline", "submit_label": "Save changes", "deadline": deadline})


@login_required
def deadline_toggle_complete(request, pk):
    deadline = get_object_or_404(Deadline, pk=pk, user=request.user)
    if request.method == "POST":
        deadline.status = Deadline.Status.COMPLETED if deadline.status == Deadline.Status.PENDING else Deadline.Status.PENDING
        deadline.save(update_fields=["status", "updated_at"])
        action = "Deadline completed" if deadline.status == Deadline.Status.COMPLETED else "Deadline reopened"
        log_activity(request.user, action, f"{action}: {deadline.title}.")
        messages.success(request, f"Deadline marked {deadline.status}.")
    if request.POST.get("next") == "deadline_list":
        return redirect("deadline_list")
    return redirect("deadline_detail", pk=deadline.pk)


@login_required
def deadline_delete(request, pk):
    deadline = get_object_or_404(Deadline, pk=pk, user=request.user)
    if request.method == "POST":
        title = deadline.title
        deadline.delete()
        log_activity(request.user, "Deadline deleted", f"Deleted {title}.")
        messages.success(request, "Deadline deleted.")
        return redirect("deadline_list")
    return render(request, "core/confirm_delete.html", {"object": deadline, "object_type": "deadline", "cancel_url": reverse("deadline_detail", args=[deadline.pk])})


@login_required
def application_list(request):
    applications = Application.objects.filter(user=request.user)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    sort = request.GET.get("sort", "deadline")
    if query:
        applications = applications.filter(title__icontains=query) | applications.filter(organization__icontains=query)
    if status != "all" and status in Application.Status.values:
        applications = applications.filter(status=status)
    if sort not in {"deadline", "-deadline", "-created_at", "title"}:
        sort = "deadline"
    applications = applications.order_by(sort)
    return render(request, "core/applications/list.html", {"applications": applications, "query": query, "status": status, "sort": sort, "statuses": Application.Status.choices})


@login_required
def application_create(request):
    form = ApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.user = request.user
        application.save()
        log_activity(request.user, "Application created", f"Created {application.title}.")
        messages.success(request, "Application created.")
        return redirect("application_detail", pk=application.pk)
    return render(request, "core/applications/form.html", {"form": form, "heading": "Add application", "submit_label": "Create application"})


@login_required
def application_detail(request, pk):
    application = get_object_or_404(Application, pk=pk, user=request.user)
    return render(request, "core/applications/detail.html", {"application": application, "readiness": application.readiness, "requirement_form": RequirementForm(), "link_form": ApplicationDocumentForm(user=request.user, application=application)})


@login_required
def application_edit(request, pk):
    application = get_object_or_404(Application, pk=pk, user=request.user)
    old_status = application.status
    form = ApplicationForm(request.POST or None, instance=application)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.user = request.user
        application.save()
        action = "Application status updated" if old_status != application.status else "Application updated"
        log_activity(request.user, action, f"Updated {application.title}.")
        messages.success(request, "Application updated.")
        return redirect("application_detail", pk=application.pk)
    return render(request, "core/applications/form.html", {"form": form, "heading": "Edit application", "submit_label": "Save changes", "application": application})


@login_required
def application_delete(request, pk):
    application = get_object_or_404(Application, pk=pk, user=request.user)
    if request.method == "POST":
        title = application.title
        application.delete()
        log_activity(request.user, "Application deleted", f"Deleted {title}.")
        messages.success(request, "Application deleted.")
        return redirect("application_list")
    return render(request, "core/confirm_delete.html", {"object": application, "object_type": "application", "cancel_url": reverse("application_detail", args=[application.pk])})


@login_required
def requirement_create(request, application_pk):
    application = get_object_or_404(Application, pk=application_pk, user=request.user)
    form = RequirementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        requirement = form.save(commit=False)
        requirement.application = application
        requirement.save()
        messages.success(request, "Requirement added.")
    return redirect("application_detail", pk=application.pk)


@login_required
def requirement_delete(request, application_pk, pk):
    application = get_object_or_404(Application, pk=application_pk, user=request.user)
    requirement = get_object_or_404(Requirement, pk=pk, application=application)
    if request.method == "POST":
        requirement.delete()
        messages.success(request, "Requirement removed.")
    return redirect("application_detail", pk=application.pk)


@login_required
def application_document_attach(request, application_pk):
    application = get_object_or_404(Application, pk=application_pk, user=request.user)
    form = ApplicationDocumentForm(request.POST or None, user=request.user, application=application)
    if request.method == "POST" and form.is_valid():
        link = form.save(commit=False)
        link.application = application
        if ApplicationDocument.objects.filter(application=application, document=link.document, requirement=link.requirement).exists():
            messages.error(request, "That document is already linked here.")
        else:
            link.full_clean()
            link.save()
            log_activity(request.user, "Document linked", f"Linked {link.document.title} to {application.title}.")
            messages.success(request, "Document linked to application.")
    else:
        messages.error(request, "Choose a valid document and requirement.")
    return redirect("application_detail", pk=application.pk)


@login_required
def application_document_unlink(request, application_pk, pk):
    application = get_object_or_404(Application, pk=application_pk, user=request.user)
    link = get_object_or_404(ApplicationDocument, pk=pk, application=application, document__user=request.user)
    if request.method == "POST":
        document_title = link.document.title
        link.delete()
        log_activity(request.user, "Document unlinked", f"Unlinked {document_title} from {application.title}.")
        messages.success(request, "Document unlinked. The original remains in your vault.")
    return redirect("application_detail", pk=application.pk)


@login_required
def calendar_view(request):
    raw_month = request.GET.get("month", "")
    try:
        current = datetime.strptime(raw_month, "%Y-%m").date().replace(day=1) if raw_month else timezone.localdate().replace(day=1)
    except ValueError:
        current = timezone.localdate().replace(day=1)
    previous_month = (current - timedelta(days=1)).replace(day=1)
    next_month = (current + timedelta(days=32)).replace(day=1)
    weeks = calendar.monthcalendar(current.year, current.month)
    return render(request, "core/calendar.html", {"month": current, "weeks": weeks, "previous_month": previous_month.strftime("%Y-%m"), "next_month": next_month.strftime("%Y-%m"), "today": timezone.localdate()})


@login_required
def calendar_events(request):
    try:
        month = datetime.strptime(request.GET.get("month", ""), "%Y-%m").date().replace(day=1)
    except ValueError:
        month = timezone.localdate().replace(day=1)
    start = month
    end = (month + timedelta(days=32)).replace(day=1)
    events = []
    for deadline in Deadline.objects.filter(user=request.user, due_date__gte=start, due_date__lt=end).select_related("application"):
        events.append({"id": f"deadline-{deadline.pk}", "title": deadline.title, "date": deadline.due_date.isoformat(), "type": "deadline", "status": deadline.status, "url": reverse("deadline_detail", args=[deadline.pk])})
    for application in Application.objects.filter(user=request.user).exclude(deadline__isnull=True).filter(deadline__gte=start, deadline__lt=end):
        events.append({"id": f"application-{application.pk}", "title": application.title, "date": application.deadline.isoformat(), "type": "application", "status": application.status, "url": reverse("application_detail", args=[application.pk])})
    return JsonResponse({"events": events})


@login_required
def notification_list(request):
    refresh_user_notifications(request.user)
    notifications = Notification.objects.filter(user=request.user)
    return render(request, "core/notifications.html", {"notifications": notifications})


@login_required
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if request.method == "POST":
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect("notification_list")


@login_required
def activity_list(request):
    return render(request, "core/activity.html", {"activities": Activity.objects.filter(user=request.user)})


@login_required
def settings_view(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings updated.")
        return redirect("settings")
    return render(request, "core/settings.html", {"form": form})
