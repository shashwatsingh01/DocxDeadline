from django.db import IntegrityError
from django.utils import timezone

from .models import Activity, Application, Deadline, Document, Notification


def log_activity(user, action, description):
    return Activity.objects.create(user=user, action=action, description=description)


def create_notification(user, title, message, notification_type, dedupe_key):
    try:
        notification, _ = Notification.objects.get_or_create(
            user=user,
            dedupe_key=dedupe_key,
            defaults={"title": title, "message": message, "notification_type": notification_type},
        )
    except IntegrityError:
        notification = Notification.objects.get(user=user, dedupe_key=dedupe_key)
    return notification


def refresh_user_notifications(user):
    for deadline in Deadline.objects.filter(user=user, status=Deadline.Status.PENDING):
        days = deadline.days_remaining
        if days < 0:
            create_notification(user, "Deadline overdue", f"{deadline.title} is {abs(days)} day(s) overdue.", Notification.Type.DEADLINE_OVERDUE, f"deadline-overdue-{deadline.pk}-{deadline.due_date}")
        elif days <= 7:
            create_notification(user, "Deadline due soon", f"{deadline.title} is due in {days} day(s).", Notification.Type.DEADLINE_SOON, f"deadline-soon-{deadline.pk}-{deadline.due_date}")
    for document in Document.objects.filter(user=user, expiry_date__isnull=False):
        days = document.days_until_expiry
        if days is not None and 0 <= days <= document.expiry_warning_days:
            create_notification(user, "Document expiring soon", f"{document.title} expires in {days} day(s).", Notification.Type.DOCUMENT_EXPIRING, f"document-expiring-{document.pk}-{document.expiry_date}")
    for application in Application.objects.filter(user=user, deadline__isnull=False).exclude(status__in=[Application.Status.ACCEPTED, Application.Status.REJECTED, Application.Status.WITHDRAWN]):
        days = application.days_remaining
        if days is not None and 0 <= days <= 7:
            create_notification(user, "Application deadline approaching", f"{application.title} is due in {days} day(s).", Notification.Type.APPLICATION_SOON, f"application-soon-{application.pk}-{application.deadline}")
