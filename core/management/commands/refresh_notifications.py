from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.services import refresh_user_notifications


class Command(BaseCommand):
    help = "Create deduplicated in-app reminders for deadlines, applications, and expiring documents."

    def handle(self, *args, **options):
        for user in User.objects.filter(is_active=True):
            refresh_user_notifications(user)
        self.stdout.write(self.style.SUCCESS("Notification refresh complete."))
